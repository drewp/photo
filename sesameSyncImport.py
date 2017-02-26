#!bin/python
"""
listen http, run scanfs and scanexif on requested files
"""
import boot
from sparqlhttp.graph2 import SyncGraph
import os, time, cyclone.web, sys
from twisted.internet import reactor
from sparqlhttp.syncimport import SyncImport, IMP
from _xmlplus.utils import iso8601
from scanFs import ScanFs
from scanExif import ScanExif
from mediaresource import MediaResource
from fileschanged import allFiles
from picdirs import picSubDirs
import networking
from ns import PHO, FOAF, RDFS
from db import getGraph
import v2.imageset.client

log = boot.log

class SesameSync(SyncImport):
    def allInputFiles(self):
        # faster to cull files more, here
        for root, dirs, files in os.walk(self.inputDirectory):
	    for filename in files:
                # the dot hides emacs partial-save files, which i
                # didn't notice anyway
                if not filename.endswith(".n3") or filename.startswith('.'):
                    continue
                filename = os.path.join(root, filename)
                yield filename

    # method replaced for sesame
    def lastImportTimeSecs(self, context):
        """get the import time for a context, in unix seconds; or None
        if it was never imported"""
        time.sleep(.01) # for lower sesame cpu load
        importTime = self.graph.value(context, IMP['lastImportTime'])
        
        if importTime is None:
            log.debug("no imp:lastImportTime for %s" % context)
            return None
        return iso8601.parse(str(importTime))

    def someChange(self, filename, doubleCheckMtime=False):
        """this file was created, modified, or deleted"""
        if not filename.endswith(".n3") or filename.startswith('.'):
            return
        
        if not os.path.exists(filename):
            self.fileDisappeared(filename)
        else:
            if doubleCheckMtime and not self.fileIsUpdated(filename):
                return
            self.reloadContext(filename)

def fixSftpPerms():
    """files put in upload/ sometimes have the wrong perms, and
    they're owned by user picuploader. There's a setuid program in
    that dir that has picloader chmod a+r on the files

    http://www.tuxation.com/setuid-on-shell-scripts.html
    """
    os.system("/my/pic/upload/fixperms")


def onChange(filename):
    for root, sync in syncs.items():
        if filename.startswith(root):
            # this one reads .n3 files into sesame
            log.info("rdf data sync on %r", filename)
            sync.someChange(filename, doubleCheckMtime=True)
            break

    if filename.startswith('/my/pic') and '/.hide/' not in filename:
        # this one wants to hear about image files for path/exif data
        if filename.startswith('/my/pic/upload'):
            fixSftpPerms()
        log.info("scanFs and scanExif on %r", filename)
        picUri = scanFs.fileChanged(filename)
        log.info('picUri is %r', picUri)
        if picUri is not None:
            # this will fail on videos (though i wish i could get the Pre metadata out of them)
            scanExif.addPic(picUri, rerunScans=True)
            mr = MediaResource(graph, picUri)
            if mr.isVideo():
                mr.videoProgress()
            # todo: freshen thumbs here too? that should be on a lower
            # priority queue than getting the exif/file data
            v2.imageset.client.changed(picUri)

quick = False
  
graph = getGraph()

scanFs = ScanFs(graph, '/my/pic')
scanExif = ScanExif(graph)

syncs = {}
subdirs = picSubDirs(syncs, SesameSync, graph, quick) # root directories for fileschanged to watch underneath

if quick:
    onChange('/my/site/photo/input/local.n3')
    onChange('/my/pic/flickr/3716645105_27bca1ba5a_o.jpg')
    onChange('/my/pic/phonecam/dt-2009-07-16/CIMG0074.jpg')
    onChange('/my/pic/digicam/dl-2009-07-20/DSC_0092.JPG')

import httplib, cgi
class PrettyErrorHandler(object):
    """
    mix-in to improve cyclone.web.RequestHandler
    """
    def get_error_html(self, status_code, **kwargs):
        try:
            tb = kwargs['exception'].getTraceback()
        except AttributeError:
            tb = ""
        return "<html><title>%(code)d: %(message)s</title>" \
               "<body>%(code)d: %(message)s<pre>%(tb)s</pre></body></html>" % {
            "code": status_code,
            "message": httplib.responses[status_code],
            "tb" : cgi.escape(tb),
        }

class FileChanged(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        self.write('''<html><body>
        <form method="post" action="">Report a changed file: <input name="file" size="100"/> <input type="submit"/></form>
        <form method="post" action="all"><input type="submit" value="rescan all files (slow)"/></form>
        </body></html>
        ''')
        
    def post(self):
        fileArg = self.get_argument("file")
        if not fileArg:
            raise ValueError("missing file")
        log.info('post onChange(%r)' % fileArg)
        onChange(fileArg)
        self.write('ok\n')
        
class AllChanged(PrettyErrorHandler, cyclone.web.RequestHandler):
    def post(self):
        allFiles(subdirs, onChange)
        self.write('ok\n')

class Application(cyclone.web.Application):
    def __init__(self):
        handlers = [
            (r"/", FileChanged),
            (r"/all", AllChanged),
        ]
        cyclone.web.Application.__init__(self, handlers)

if __name__ == '__main__':
    from twisted.python import log as twlog
    twlog.startLogging(sys.stdout)

    reactor.listenTCP(9042, Application())
    reactor.run()
