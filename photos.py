"""
depends on exiftool program from libimage-exiftool-perl ubuntu package
"""
from __future__ import division
import os, hashlib, time, random, string, subprocess, urllib, re, logging
from twisted.python.util import sibpath
from StringIO import StringIO
import Image

log = logging.getLogger()

class Full(object): pass

sizes = {'thumb' : 75,
        'medium' : 250,
        'large' : 600,
        'screen' : 1000,
        'full' : Full}

tmpSuffix = ".tmp" + ''.join([random.choice(string.letters) for c in range(5)])

def thumb(localURL, maxSize=100):
    """returns jpeg data, mtime

    I forget what's 'local' about localURL. it's just the photo's main URI.
    """
    localPath = _localPath(localURL)
    
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


def justCache(url, sizes, grid=False, gridLogDir='/dev/null'):
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

def _safeSgeJobName(s):
    return re.sub(r'[^a-zA-Z0-9\.]+', '_', s)

def _localPath(url):
    # localURL like http://photo.bigasterisk.com/digicam/housewarm/00023.jpg
    #         means /my/pic/digicam/housewarm/00023.jpg
    assert url.startswith("http://photo.bigasterisk.com/")
    return "/my/pic/" + urllib.unquote(
        url[len("http://photo.bigasterisk.com/"):])
    

def _resizeAndSave(localPath, thumbPath, maxSize, localURL):

    print "resizing %s to %s in %s" % (localPath, maxSize, thumbPath)

    img = Image.open(localPath)

    # img.thumbnail is faster, but much lower quality
    w, h = img.size
    scl = min(maxSize / w, maxSize / h)
    img = img.resize((int(round(w * scl)), int(round(h * scl))),
                     Image.ANTIALIAS)

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
    return "/my/pic/~thumb/%s/%s" % (cksum[:2], cksum[2:])

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
