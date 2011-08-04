#!/usr/bin/python

"""
watch new files in photoIncoming mail folder; ingest them and move
them to photoIncoming.done
"""
import path, logging, cyclone.web, time
from twisted.internet import reactor, task
from ingestmail import ingest

logging.basicConfig(level=logging.DEBUG)

class Poller(object):
    def __init__(self):
        self.lastScan = 0
        
    def scan(self, mock=False):
        for f in (path.path("/my/mail/drewp/.photoIncoming/cur").files()+
                  path.path("/my/mail/drewp/.photoIncoming/new").files()):
            ingest(f.open(), mock=mock)
            if not mock:
                f.move("/my/mail/drewp/.photoIncoming.done/new")
        self.lastScan = time.time()

class Index(cyclone.web.RequestHandler):
    def get(self):
        dt = time.time() - self.settings.poller.lastScan
        if dt > 35:
            self.send_error(500, exception="last scan was %s sec ago" % dt)
            return
        self.write("watchmail")
    def get_error_html(self, status_code, **kwargs):
        return kwargs['exception']

if __name__ == '__main__':
    p = Poller()

    task.LoopingCall(p.scan).start(30)
    reactor.listenTCP(9082,
                      cyclone.web.Application(handlers=[(r"/", Index)],
                                              poller=p))
    reactor.run()

