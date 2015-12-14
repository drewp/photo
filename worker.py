"""
Note that this worker will only use one proc, so run multiple workers
"""

import boot
import logging
import os
import socket
import re
import time
import subprocess
import celeryconfig
from celery import Celery
from db import getGraph, getProgressCollection
import pymongo

log = logging.getLogger('worker')
graph = getGraph()

app = Celery('photo')
progressColl = getProgressCollection()

# don't know why client side needs this
import celeryconfig
app.conf.update(dict((k,v) for k,v in celeryconfig.__dict__.items()
                     if k.startswith(('B','C'))))

class Done(object):
    """video is done encoding"""

class FailedStatus(str):
    pass

def makeDirToThumb(path):
    try:
        os.makedirs(os.path.split(path)[0])
    except OSError:
        pass # if the dir can't be made (as opposed to exists
             # already), we'll get an error later

def _process():
    return '%s-%s' % (socket.gethostname(), os.getpid())

def _startTag():
    # This is for debugging and for separating multiple runs by one
    # worker pid.  Note we must not put a . in a mongo key name
    return 'start-%d' % int(time.time())
    
def _status(msg):
    return {'status': msg, 't': time.time()}
             
@app.task(name='videoEncode', bind=True, max_retries=10, track_started=True)
def videoEncode(self, sourcePath, thumbPath):
    key = 'worker.%s-%s' % (_startTag(), _process())
    def onProgress(msg):
        progressColl.update_one(
            {'_id': sourcePath}, {'$set': {key: _status(msg)}})
    try:
        _runVideoEncode(sourcePath, thumbPath, onProgress=onProgress)
    except Exception as e:
        log.warn("_runVideoEncode(%r, %r) -> %r", sourcePath, thumbPath, e)
        raise self.retry(exc=e)

def _runVideoEncode(sourcePath, thumbPath, onProgress):
    log.info("encodevideo %s %s" % (sourcePath, thumbPath))
    p = subprocess.Popen(['/my/site/photo/encode/encodevideo',
                          sourcePath, thumbPath],
                         stderr=subprocess.PIPE)
    buf = ""
    allStderr = ""
    while True:
        chunk = p.stderr.read(1)
        if not chunk:
            break
        buf += chunk
        allStderr += chunk
        if buf.endswith('\r'):
            if onProgress:
                m = re.search(
                    r'frame= *(\d+).*fps= *(\d+).*time= *([\d\.:]+)', buf)
                if m is None:
                    onProgress("running")
                else:
                    onProgress("encoded %s sec so far, %s fps" %
                               (m.group(3), m.group(2)))
            buf = ""
    log.info("encodevideo finished")
    if p.poll():
        log.warn("all the stderr output: %s" % allStderr)
        raise ValueError("process returned %s" % p.poll())

    onProgress('done')
    return thumbPath

def _latestStatus(doc):
    """
    returns (statusRow, anyoneSaidDone)
    """
    anyoneSaidDone = False
    latestTime = -1
    for worker, row in doc.get('worker', {}).items():
        if row['status'] == 'done':
            anyoneSaidDone = True
        if row['t'] > latestTime:
            latestTime = row['t']
            latestStatus = row
    return latestStatus, anyoneSaidDone

MAX_SEC_BETWEEN_UPDATES = 30

def _requeueDeadJob(sourcePath, key, taskKw):
    log.info('job for %r seems dead- requeuing', sourcePath)
    progressColl.update_one({'_id': sourcePath},
                            {'$set': {key: _status('beforeQueue')}})
    videoEncode.apply_async(kwargs=taskKw)
    progressColl.update_one({'_id': sourcePath},
                            {'$set': {key: _status('queued')}})
    return 'queued'

def _firstQueue(sourcePath, key, taskKw):
    progressColl.insert_one({'_id': sourcePath},
                            {key: _status('beforeQueue')})
    videoEncode.apply_async(kwargs=taskKw)
    progressColl.update_one({'_id': sourcePath},
                            {'$set': {key: _status('queued')}})
    
    
def videoProgress(sourcePath, thumbPath):
    """Done if we have the video, or a string explaining the status.
    If the string is a FailedStatus, the job is not progressing"""

    if not os.path.exists(sourcePath):
        return FailedStatus("source file %r not found" % sourcePath)
    if os.path.exists(thumbPath):
        return Done
    makeDirToThumb(thumbPath)

    key = 'worker.%s-%s-queuer' % (_startTag(), _process())
    
    taskKw = dict(sourcePath=sourcePath, thumbPath=thumbPath)
    try:
        _firstQueue(sourcePath, key, taskKw)
    except pymongo.errors.DuplicateKeyError:
        pass
        
    prog = progressColl.find_one(sourcePath)
    latestStatus, anyoneSaidDone = _latestStatus(prog)

    if latestStatus['t'] < time.time() - MAX_SEC_BETWEEN_UPDATES:
        return _requeueDeadJob(sourcePath, key, taskKw)
        
    if anyoneSaidDone and os.path.exists(thumbPath):
        # any worker can be done, and that should be good
        # enough (later finishers shouldn't break the file)
        return Done
    
    if latestStatus['status'] == 'beforeQueue':
        # failure earlier
        return FailedStatus('queueing failed- job is stuck')
    if latestStatus['status'] == 'failed':
        return FailedStatus(prog['error'])
    return latestStatus['status']

