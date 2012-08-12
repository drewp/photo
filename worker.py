# ../bin/celery -A worker worker --loglevel=info

from celery import Celery
from celery import current_task
import sys, traceback, logging

import boot
from db import getGraph
from mediaresource import MediaResource, Done

log = logging.getLogger('worker')
graph = getGraph()

import celeryconfig

celery = Celery('worker')
celery.config_from_object(celeryconfig)


@celery.task(ignore_result=True)
def runVideoEncode(uri):
    current_task.update_state(state='PROGRESS', meta={'current': 'x'})
    
    m = MediaResource(graph, uri)
    if m.hasRunningJob():
        log.info("dup job- skipping")
        return
    m.runVideoEncode()

if __name__ == '__main__':
    celery.worker_main()
