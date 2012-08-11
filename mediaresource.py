u"""
depends on exiftool program from libimage-exiftool-perl ubuntu package
"""
from __future__ import division
import os, hashlib, time, random, string, subprocess, urllib, re, logging, tempfile
from twisted.python.util import sibpath
from StringIO import StringIO
import Image
from lib import print_timing
from ns import RDF, PHO
from scanFs import videoExtensions
from dims import fitSize
log = logging.getLogger()
from urls import photoUri

class StillEncoding(ValueError):
    pass

class Full(object): pass
class Video2(object): "half-size video"

sizes = {'thumb' : 75,
         'medium' : 250,
         'large' : 600,
         'screen' : 1000,
         'video2' : Video2,
         'full' : Full}

class MediaResource(object):
    def __init__(self, graph, uri):
        self.graph, self.uri = graph, uri

    def isVideo(self):
        return self.graph.contains((self.uri, RDF.type, PHO.Video))

    def videoProgress(self):
        """True if we have the video, or a string explaining the status"""

    def getSize(self, size):
        """pass photo size or thumb boundary size, get (w,h)

        videos can be requested at thumb size for a thumbnail, or else
        you can request the special size Video2 for the res-2 (320w) version
        """
        #no video support yet
        
        # this could probably get a ton faster if the sizes were in a db.
        jpg, mtime = self.getImageAndMtime(size)
        return Image.open(StringIO(jpg)).size

    def getImageAndMtime(self, size):
        """block and return an image fitting in this size square plus
        the mtime of the image data. If it's a video, raise
        StillEncoding (with videoProgress as an attr) if we don't have
        the data yet"""
        
        log.debug("need thumb for %r", self.uri)
        # this ought to return a redirect to a static error image when it breaks
        jpg, mtime = thumb(self.uri, size)
        return jpg, mtime

    def cacheResize(self):
        """block and prepare the standard sizes as needed, but don't
        return any. If this is a video, we make a thumbnail and
        startVideoEncode for a queued encode. """

    def startVideoEncode(self):
        """non-blocking. starts a video encoding if we don't have one"""



def getRequestedSize(ctx):
    return sizes.get(ctx.arg('size'), 250)


tmpSuffix = ".tmp" + ''.join([random.choice(string.letters) for c in range(5)])
"""
uses 'exiftool', from ubuntu package libimage-exiftool-perl

"""

def thumb(localURL, maxSize=100):
    """returns jpeg data, mtime

    if maxSize is Video, then you get webm data instead, or a
    StillEncoding exception with progress data (someday)

    I forget what's 'local' about localURL. it's just the photo's main URI.
    """
    localPath = _localPath(localURL)

    if localPath.lower().endswith(videoExtensions):
        if maxSize is Video2:
            return encodedVideo(localPath)
        elif maxSize is Full:
            raise NotImplementedError
        else:
            return videoThumbnail(localPath, maxSize)
    if maxSize is Video2:
        raise NotImplementedError("maxSize=Video2 on localPath %r" % localPath)
    
    if maxSize is Full:
        return jpgWithoutExif(localPath), os.path.getmtime(localPath)

    thumbPath = _thumbPath(localURL, maxSize)
    _makeDirToThumb(thumbPath)

    try:
        f = open(thumbPath)
    except IOError:
        pass
    else:
        return f.read(), os.path.getmtime(thumbPath)

    jpg = _resizeAndSave(localPath, thumbPath, maxSize, localURL)
    return jpg.getvalue(), time.time()

def encodedVideo(localPath, _returnContents=True):
    """returns full webm binary + time. does its own caching"""
    h = hashlib.md5(localPath + "?size=video2").hexdigest()
    videoOut = '/var/cache/photo/video/%s/%s.webm' % (h[:2], h[2:])
    try:
        f = open(videoOut)
    except IOError:
        pass
    else:
        if not _returnContents:
            return
        return f.read(), os.path.getmtime(videoOut)

    #check for existing job, maybe start oone, then raise

    # this could start a second conversion while the first is going on!
    _makeDirToThumb(videoOut)

    if _returnContents:
        # live site asking for a video
        
        # if existing job, figure out its progress and don't make a new one
        # else:

        import encode.worker
        encode.worker.justCache.delay(photoUri(localPath), sizes=[])
        raise StillEncoding("encoding") # this will be a progress message
    else:
        # worker asking to run an encoding (i hope)

        subprocess.check_call(['/my/site/photo/encode/encodevideo',
                               localPath, videoOut])

def videoThumbnail(localPath, maxSize):
    # this is not caching yet but it should
    tf = tempfile.NamedTemporaryFile()
    subprocess.check_call(['/usr/bin/ffmpegthumbnailer', '-i', localPath, '-o', tf.name, '-c', 'jpeg', '-s', str(maxSize)])
    return open(tf.name).read(), time.time() # todo

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

def _localPath(url):
    # localURL like http://photo.bigasterisk.com/digicam/housewarm/00023.jpg
    #         means /my/pic/digicam/housewarm/00023.jpg
    assert url.startswith("http://photo.bigasterisk.com/")
    return "/my/pic/" + urllib.unquote(
        url[len("http://photo.bigasterisk.com/"):])

_lastOpen = None, None
def _resizeAndSave(localPath, thumbPath, maxSize, localURL):
    global _lastOpen
    print "resizing %s to %s in %s" % (localPath, maxSize, thumbPath)

    # this is meant to reduce decompress calls when we're making
    # multiple resizes of a new image
    if _lastOpen[0] == localPath:
        img = _lastOpen[1]
    else:
        img = Image.open(localPath)
        _lastOpen = localPath, img

    # img.thumbnail is faster, but much lower quality
    w, h = img.size
    outW, outH = fitSize(w, h, maxSize, maxSize)
    img = img.resize((outW, outH), Image.ANTIALIAS)

    jpg = StringIO()
    jpg.name = localURL
    q = 80
    if maxSize <= 100:
        q = 60
    img.save(jpg, quality=q)
    open(thumbPath + tmpSuffix, "w").write(jpg.getvalue())
    os.rename(thumbPath + tmpSuffix, thumbPath)
    return jpg


def _thumbPath(localURL, maxSize):
    thumbUrl = localURL + "?size=%s" % maxSize
    cksum = hashlib.md5(thumbUrl).hexdigest()
    return "/var/cache/photo/%s/%s/%s" % (cksum[:2], cksum[2:4], cksum[4:])

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
