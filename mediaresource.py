u"""
depends on exiftool program from libimage-exiftool-perl ubuntu package
"""
from __future__ import division
import os, hashlib, time, random, string, subprocess, urllib, re, logging, tempfile
from twisted.python.util import sibpath
from pymongo import Connection
from StringIO import StringIO
import Image
from lib import print_timing
from ns import RDF, PHO
from scanFs import videoExtensions
from dims import fitSize, videoSize
log = logging.getLogger()
from urls import photoUri

class StillEncoding(ValueError):
    pass

class Done(object):
    """video is done encoding"""

class Full(object): pass
class Video2(object): "half-size video"

sizes = {'thumb' : 75,
         'medium' : 250,
         'large' : 600,
         'screen' : 1000,
         'video2' : Video2,
         'full' : Full}

def getRequestedSize(ctx):
    return sizes.get(ctx.arg('size'), 250)

_lastOpen = None, None

from celery import Celery
import celeryconfig
celery = Celery()
celery.config_from_object(celeryconfig)


class MediaResource(object):
    def __init__(self, graph, uri):
        self.graph, self.uri = graph, uri

    def isVideo(self):
        return self.graph.contains((self.uri, RDF.type, PHO.Video))

    def videoProgress(self):
        """Done if we have the video, or a string explaining the status"""

        log.info("progress on %s" % self.uri)
        if not os.path.exists(self._sourcePath()):
            return "source file %r not found" % self._sourcePath()
        if os.path.exists(self._thumbPath(Video2)):
            return Done

        self._videoJobStatus()

        # here we look at the pending jobs for the one that will
        # compress self._sourcePath(). if it's not there, return 'not
        # started'. Else see about a way to get the progress or at
        # least the honest runtime of the job
        
        return "still working"

    def _videoJobStatus(self):
        """look in celery for a job that is doing this video, return
        the string 'no job found' or some other status text about an
        existing job"""
        res = celery.AsyncResult(self._taskId())
        print "res %s %s" % (self._taskId(), res.state)
        return res.state

    def hasRunningJob(self):
        """is there a celery job already running or finished for this uri?"""
        s = self._videoJobStatus()
        print repr(s), s.__class__
        return self._videoJobStatus() != "PENDING"

    def getSize(self, size):
        """pass photo size or thumb boundary size, get (w,h)

        videos can be requested at thumb size for a thumbnail, or else
        you can request the special size Video2 for the res-2 (320w) version
        """
        # this could probably get a ton faster if the sizes were in a db.
        if size is Video2:
            return videoSize(self._thumbPath(size))

        jpg, mtime = self.getImageAndMtime(size)
        return Image.open(StringIO(jpg)).size

    def requestVideo(self):
        """client wants to render a <video> tag of this resource. It
        will next ask for videoProgress and decide what to do from
        there, but this method is where we trigger a job if needed"""
        if not os.path.exists(self._thumbPath(Video2)):
            # AND a job isn't already queued
            self.enqueueVideoEncode()

    def getImageAndMtime(self, size):
        """
        most important method.

        block and return an image or video fitting in this size square
        plus the mtime of the image data. If the response would be a
        full video, and we don't have the data yet, raise
        StillEncoding"""
        
        log.debug("getImageAndMtime %r", self.uri)
        # this ought to return a redirect to a static error image when it breaks

        if self.isVideo():
            if size == sizes['thumb']:
                return self._runVideoThumbnail()
            elif size is Video2:
                try:
                    return self._returnCached(size)
                except IOError:
                    self.enqueueVideoEncode()                
                    raise StillEncoding()
            else:
                raise NotImplementedError(
                    "only Video2 size is supported for video %r" % self.uri)
        else:
            if size is Video2:
                raise NotImplementedError("maxSize=Video2 on an image %r" %
                                          self.uri)
            elif size is Full:
                return self._strippedFullRes()
            else:
                try:
                    return self._returnCached(size)
                except IOError:
                    jpg = self._runPhotoResize(size)
                    return jpg.getvalue(), time.time()

    def _returnCached(self, size):
        thumbPath = self._thumbPath(size)
        f = open(thumbPath)
        return f.read(), os.path.getmtime(thumbPath)

    def cacheResize(self):
        """block and prepare the standard sizes as needed, but don't
        return any. If this is a video, we make a thumbnail and
        enqueueVideoEncode for a queued encode. """

    def _taskId(self):
        return "encode-"+self.uri

    def enqueueVideoEncode(self):
        """non-blocking. starts a video encoding if we don't have one"""
        thumbPath = self._thumbPath(Video2)
        if not os.path.exists(thumbPath):
            log.info("%r didn't exist; enqueuing a new encode job", thumbPath)
            # there may be one running, and we just started a second
            # one! look at the job list here.

            # this could start a second conversion while the first is going on!
            _makeDirToThumb(thumbPath)

            # live site asking for a video

            # if existing job, figure out its progress and don't make a new one
            # else:

            import worker
            worker.runVideoEncode.apply_async(args=(self.uri,),
                                              task_id=self._taskId())

    def runVideoEncode(self):
        """block for the whole encode process"""
        subprocess.check_call(['/my/site/photo/encode/encodevideo',
                               self._sourcePath(), self._thumbPath(Video2)])
        
    def _strippedFullRes(self):
        s = self._sourcePath()
        return jpgWithoutExif(s), os.path.getmtime(s)

    def _runVideoThumbnail(self):
        # this is not caching yet but it should
        tf = tempfile.NamedTemporaryFile()
        subprocess.check_call(['/usr/bin/ffmpegthumbnailer',
                               '-i', self._sourcePath(),
                               '-o', tf.name,
                               '-c', 'jpeg',
                               '-s', str(sizes['thumb'])])
        return open(tf.name).read(), time.time() # todo

    def _runPhotoResize(self, maxSize):
        """returns the jpeg result too"""
        global _lastOpen

        source = self._sourcePath()
        thumbPath = self._thumbPath(maxSize)
        _makeDirToThumb(thumbPath)
        
        log.info("resizing %s to %s in %s" % (source, maxSize, thumbPath))

        # this is meant to reduce decompress calls when we're making
        # multiple resizes of a new image
        if _lastOpen[0] == source:
            img = _lastOpen[1]
        else:
            img = Image.open(source)
            _lastOpen = source, img

        # img.thumbnail is faster, but much lower quality
        w, h = img.size
        outW, outH = fitSize(w, h, maxSize, maxSize)
        img = img.resize((outW, outH), Image.ANTIALIAS)

        jpg = StringIO()
        jpg.name = self.uri # just for the extension
        q = 80
        if maxSize <= 100:
            q = 60
        img.save(jpg, quality=q)
        open(thumbPath + tmpSuffix, "w").write(jpg.getvalue())
        os.rename(thumbPath + tmpSuffix, thumbPath)
        return jpg

    def _thumbPath(self, maxSize):
        if maxSize is Video2:
            h = hashlib.md5(self.uri + "?size=video2").hexdigest()
            return '/var/cache/photo/video/%s/%s.webm' % (h[:2], h[2:])
        else:
            thumbUrl = self.uri + "?size=%s" % maxSize
            cksum = hashlib.md5(thumbUrl).hexdigest()
            return "/var/cache/photo/%s/%s/%s" % (cksum[:2], cksum[2:4], cksum[4:])

    def _sourcePath(self):
        """filesystem path to the source image"""
        # uri like http://photo.bigasterisk.com/digicam/housewarm/00023.jpg
        #         means /my/pic/digicam/housewarm/00023.jpg
        assert self.uri.startswith("http://photo.bigasterisk.com/")
        return "/my/pic/" + urllib.unquote(
            self.uri[len("http://photo.bigasterisk.com/"):])

    def _sourceExists(self):
        return os.path.exists(self._sourcePath())


tmpSuffix = ".tmp" + ''.join([random.choice(string.letters) for c in range(5)])
"""
uses 'exiftool', from ubuntu package libimage-exiftool-perl
"""


def encodedVideo(localPath, _returnContents=True):
    """returns full webm binary + time. does its own caching"""
    try:
        f = open(videoOut)
    except IOError:
        pass
    else:
        if not _returnContents:
            return
        return f.read(), os.path.getmtime(videoOut)

    #check for existing job, maybe start oone, then raise

def justCache(url, sizes):
    """
    if it's a video, we automatically add video2 size
    """

    localPath = _localPath(url)
    if localPath.lower().endswith(videoExtensions):
        justCacheVideo(url)
    else:
        justCachePhoto(url, sizes)

def justCachePhoto(url, sizes):
    todo = []
    for size in sizes:
        thumbPath = _thumbPath(url, size)
        if os.path.exists(thumbPath):
            continue
        else:
            log.debug("%s doesn't exist for %s; will resize",
                      thumbPath, (url, size))
            todo.append(size)

    for size in todo:
            thumbPath = _thumbPath(url, size)
            _makeDirToThumb(thumbPath)
            localPath = _localPath(url)
            _resizeAndSave(localPath, thumbPath, size, url)

def justCacheVideo(url):
    localPath = _localPath(url)
    encodedVideo(localPath, _returnContents=False)

def _makeDirToThumb(path):
    try:
        os.makedirs(os.path.split(path)[0])
    except OSError:
        pass # if the dir can't be made (as opposed to exists
             # already), we'll get an error later
    

def jpgWithoutExif(filename):
    """this is meant to remove GPS data, and I'm just removing
    everything.

    But it might be cool to add an exif line that says the URI for
    this image, in case people want to come back to try for more
    metadata"""
    proc = subprocess.Popen(['exiftool', '-all=', '--jfif:all', '-'],
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE)
    out, err = proc.communicate(input=open(filename).read())
    return out
