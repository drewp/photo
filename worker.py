"""
uses the fork at https://github.com/drewp/monque

Note that this worker will only use one proc, so run multiple workers
"""

import logging
import boot
from monque import job

from db import getGraph, getMonque
from mediaresource import MediaResource, Done

log = logging.getLogger('worker')
graph = getGraph()

monque = getMonque()

@job()
def runVideoEncode(uri):
    m = MediaResource(graph, uri)
    coll = monque.get_queue_collection(monque._workorder_defaults['queue'])
    def onProgress(msg):
        coll.update({"body.message.args" : uri}, {"$set" : {"progress" : msg}})
    m.runVideoEncode(onProgress=onProgress)

if __name__ == '__main__':
    worker = monque.new_worker(dispatcher='local')
    worker.work(interval=1)
