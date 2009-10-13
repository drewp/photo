"""
depends on exiftool program from libimage-exiftool-perl ubuntu package
"""
from __future__ import division
import os, md5, time, random, string, subprocess, urllib
from StringIO import StringIO
import Image

class Full(object): pass

tmpSuffix = ".tmp" + ''.join([random.choice(string.letters) for c in range(5)])

def thumb(localURL, maxSize=100, justCache=False):
    """returns jpeg data, mtime"""
    cksum = md5.new(localURL + "?size=%s" % maxSize).hexdigest()

    thumbPath = "/my/pic/~thumb/%s/%s" % (cksum[:2], cksum[2:])
    try:
        os.makedirs(os.path.split(thumbPath)[0])
    except OSError:
        pass # if the dir can't be made (as opposed to exists
             # already), we'll get an error later
    
    try:
        f = open(thumbPath)
    except IOError:
        pass
    else:
        if justCache:
            return
        return f.read(), os.path.getmtime(thumbPath)


    # localURL like http://photo.bigasterisk.com/digicam/housewarm/00023.jpg
    #         means /my/pic/digicam/housewarm/00023.jpg
    assert localURL.startswith("http://photo.bigasterisk.com/")
    localPath = "/my/pic/" + urllib.unquote(localURL[len("http://photo.bigasterisk.com/"):])

    if maxSize is Full:
        if justCache:
            return

        return jpgWithoutExif(localPath), os.path.getmtime(localPath)

    print "resizing %s to %s" % (localPath, thumbPath)

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
    if justCache:
        return
    return jpg.getvalue(), time.time()


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
