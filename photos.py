from __future__ import division
import os, md5, time, random, string
from StringIO import StringIO
import Image

class Full(object): pass

tmpSuffix = ".tmp" + ''.join([random.choice(string.letters) for c in range(5)])

def thumb(localURL, maxSize=100, justCache=False):
    """returns jpeg data, mtime"""
    cksum = md5.new(localURL + "?size=%s" % maxSize).hexdigest()

    thumbPath = "/my/pic/~thumb/%s/%s" % (cksum[:2], cksum[2:])
    if not os.path.isdir(os.path.split(thumbPath)[0]):
        os.makedirs(os.path.split(thumbPath)[0])
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
    localPath = "/my/pic/" + localURL[len("http://photo.bigasterisk.com/"):]

    if maxSize is Full:
        if justCache:
            return
        return open(localPath).read(), os.path.getmtime(localPath)

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
