from __future__ import division
import sys, os, md5, urllib, time, logging
from sets import Set
from StringIO import StringIO
from twisted.application import internet, service
from nevow import appserver, inevow
from nevow import loaders, rend, static, tags as T
import Image

class Full(object): pass

def thumb(localURL, maxSize=100):
    """returns jpeg data, mtime"""
    cksum = md5.new(localURL + "?size=%s" % maxSize).hexdigest()

    thumbPath = "/my/pic/~thumb/%s" % cksum
    try:
        f = open(thumbPath)
    except IOError:
        pass
    else:
        return f.read(), os.path.getmtime(thumbPath)


    # localURL like http://photo.bigasterisk.com/digicam/housewarm/00023.jpg
    #         means /my/pic/digicam/housewarm/00023.jpg
    assert localURL.startswith("http://photo.bigasterisk.com/")
    localPath = "/my/pic/" + localURL[len("http://photo.bigasterisk.com/"):]
    print localPath

    if maxSize is Full:
        return open(localPath).read(), os.path.getmtime(localPath)

    print "resizing %s" % localURL

    img = Image.open(localPath)
    img.thumbnail((maxSize, maxSize))
    jpg = StringIO()
    jpg.name = localURL
    q = 75
    if maxSize == 100:
        q = 20
    img.save(jpg, quality=q, optimize=True)
    open(thumbPath, "w").write(jpg.getvalue())
    return jpg.getvalue(), time.time()
