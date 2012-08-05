"""
depends on exiftool program from libimage-exiftool-perl ubuntu package
"""
from __future__ import division
import os, hashlib, time, random, string, subprocess, urllib, re, logging, tempfile
from twisted.python.util import sibpath
from StringIO import StringIO
import Image
from lib import print_timing
from scanFs import videoExtensions
log = logging.getLogger()

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


tmpSuffix = ".tmp" + ''.join([random.choice(string.letters) for c in range(5)])
"""
uses 'exiftool', from ubuntu package libimage-exiftool-perl

"""

def thumb(localURL, maxSize=100):
    """returns jpeg data, mtime

    if maxSize is Video, then you get webm data instead

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

def encodedVideo(localPath, _return=True):
    """returns full webm binary + time. does its own caching"""
    h = hashlib.md5(localPath + "?size=video2").hexdigest()
    videoOut = '/var/cache/photo/video/%s/%s.webm' % (h[:2], h[2:])
    try:
        f = open(videoOut)
    except IOError:
        pass
    else:
        if not _return:
            return
        return f.read(), os.path.getmtime(videoOut)

    # this could start a second conversion while the first is going on!
    _makeDirToThumb(videoOut)
    tmpOut = videoOut+tmpSuffix+'.webm'
    subprocess.check_call(['/my/site/photo/encode/encodevideo', localPath, tmpOut])
    os.rename(tmpOut, videoOut)
    if not _return:
        return
    return open(videoOut).read(), os.path.getmtime(videoOut)

def videoThumbnail(localPath, maxSize):
    # this is not caching yet but it should
    tf = tempfile.NamedTemporaryFile()
    subprocess.check_call(['/usr/bin/ffmpegthumbnailer', '-i', localPath, '-o', tf.name, '-c', 'jpeg', '-s', str(maxSize)])
    return open(tf.name).read(), time.time() # todo

def getSize(localURL, maxSize):
    # this could probably get a ton faster if the sizes were in a db.
    jpg, mtime = thumb(localURL, maxSize)
    return Image.open(StringIO(jpg)).size

def justCache(url, sizes, grid=False, gridLogDir='/dev/null'):
    """
    if it's a video, we automatically add video2 size
    """

    localPath = _localPath(url)
    if localPath.lower().endswith(videoExtensions):
        justCacheVideo(url)
    else:
        justCachePhoto(url, sizes, grid, gridLogDir)

def justCachePhoto(url, sizes, grid, gridLogDir):
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
        if grid:
            subprocess.check_call(
                ['qsub',
                 '-b', 'yes',
                 '-m', 'a',
                 '-N',  _safeSgeJobName('resize %s' % url),
                 '-o', gridLogDir, '-e', gridLogDir,
                 sibpath(__file__, 'resizeOne'), url] + map(str, sizes))
        else:
            thumbPath = _thumbPath(url, size)
            _makeDirToThumb(thumbPath)
            localPath = _localPath(url)
            _resizeAndSave(localPath, thumbPath, size, url)

def justCacheVideo(url):
    localPath = _localPath(url)
    encodedVideo(localPath, _return=False)

def _safeSgeJobName(s):
    return re.sub(r'[^a-zA-Z0-9\.]+', '_', s)

def _localPath(url):
    # localURL like http://photo.bigasterisk.com/digicam/housewarm/00023.jpg
    #         means /my/pic/digicam/housewarm/00023.jpg
    assert url.startswith("http://photo.bigasterisk.com/")
    return "/my/pic/" + urllib.unquote(
        url[len("http://photo.bigasterisk.com/"):])

def fitSize(w, h, maxW, maxH):
    scl = min(maxW / w, maxH / h)
    return int(round(w * scl)), int(round(h * scl))

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
