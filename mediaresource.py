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
from dims import fitSize, videoSize
log = logging.getLogger()
from urls import photoUri
import worker
from worker import makeDirToThumb

class Full(object): pass
class Video2(object): "half-size video"

class StillEncoding(ValueError):
    pass
    
sizes = {'thumb' : 75,
         'medium' : 250,
         'large' : 600,
         'screen' : 1000,
         'video2' : Video2,
         'full' : Full}

tmpSuffix = ".tmp" + ''.join([random.choice(string.letters) for c in range(5)])

def getRequestedSize(ctx):
    return sizes.get(ctx.arg('size'), 250)

_lastOpen = None, None


class MediaResource(object):
    """
    this is one pic or video which can be returned at various scales
    """
    def __init__(self, graph, uri):
        self.graph, self.uri = graph, uri

    def isVideo(self):
        if not hasattr(self, '_isVideo'):
            self._isVideo = self.graph.contains((self.uri, RDF.type, PHO.Video))
        return self._isVideo

    def getSize(self, size):
        """pass photo size or thumb boundary size, get (w,h)

        videos can be requested at thumb size for a thumbnail, or else
        you can request the special size Video2 for the res-2 (320w) version
        """
        # this could probably get a ton faster if the sizes were in a db.
        if size is Video2:
            return videoSize(self._thumbPath(size))

        # if it's Full, you can just get the size of the source file;
        # you don't have to strip the exif!

        
        jpg, mtime = self.getImageAndMtime(size)
        img = Image.open(StringIO(jpg))
        return img.size

    def getImageAndMtime(self, size, useMp4=False):
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
            elif size is Full:
                return self._fullVideoFile()
            elif size is Video2:
                try:
                    return self._returnCached(size)
                except IOError:
                    self.videoProgress()
                    raise StillEncoding()
            else:
                raise NotImplementedError(
                    "only Video2 size is supported for video %r" % self.uri)
        else:
            if size is Video2:
                raise NotImplementedError("maxSize=Video2 on an image %r" %
                                          self.uri)
            elif size is Full and not self.isAlt():
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

    def cacheAll(self):
        """block and prepare the standard sizes as needed, but don't
        return any. If this is a video, <s>we make a thumbnail</s> and
        enqueueVideoEncode for a queued encode. """

        if self.isVideo():
            self.videoProgress()
        else:
            for size in [75,250,600]:
                self.getImageAndMtime(size)

    def _fullVideoFile(self):
        # might be 100s of MBs!
        s = self.sourcePath()
        return open(s).read(), os.path.getmtime(s)

    def _strippedFullRes(self):
        """
        this is intended to be a faster version of
        _runPhotoResize(Full) since it doesn't do any recoding. It
        should probably be moved inside of _runPhotoResize to be more
        transparent of an optimization
        """
        s = self.sourcePath()
        return jpgWithoutExif(s), os.path.getmtime(s)

    def videoProgress(self):
        """
        client wants to render a <video> tag of this resource. Either
        we're ready for it to call feat.getSize(Video2) and serve a
        <video> tag, or we're mid-run (and we have a progress report).
        """
        return worker.videoProgress(self.sourcePath(), self._thumbPath(Video2))
                
    def _runVideoThumbnail(self):
        # this is not caching yet but it should
        tf = tempfile.NamedTemporaryFile()
        subprocess.check_call(['/usr/bin/ffmpegthumbnailer',
                               '-i', self.sourcePath(),
                               '-o', tf.name,
                               '-c', 'jpeg',
                               '-s', str(sizes['thumb'])])
        return open(tf.name).read(), time.time() # todo

    def _runPhotoResize(self, maxSize):
        """returns the jpeg result too"""
        global _lastOpen

        thumbPath = self._thumbPath(maxSize)
        makeDirToThumb(thumbPath)
        
        log.info("resizing %s to %s in %s" % (self.uri, maxSize, thumbPath))

        # this is meant to reduce decompress calls when we're making
        # multiple resizes of a new image
        if _lastOpen[0] == self.uri:
            img, ext, isAlt = _lastOpen[1], self.uri, _lastOpen[2]
        else:
            img, ext, isAlt = self._getSourceImage()
            _lastOpen = self.uri, img, isAlt

        if maxSize is not Full:
            # img.thumbnail is faster, but much lower quality
            w, h = img.size
            outW, outH = fitSize(w, h, maxSize, maxSize)
            img = img.resize((outW, outH), Image.ANTIALIAS)

        jpg = StringIO()
        jpg.name = ext # just for the extension
        q = 80
        if maxSize <= 100:
            q = 60
        img.save(jpg, quality=q)

        if maxSize is Full and not isAlt:
            # don't write copies of the full jpegs, but alts are
            # considered expensive, so we do cache those
            pass
        else:
            open(thumbPath + tmpSuffix, "w").write(jpg.getvalue())
            os.rename(thumbPath + tmpSuffix, thumbPath)
        return jpg

    def isAlt(self):
        return self.graph.queryd("ASK { ?source pho:alternate ?uri }",
                                 initBindings={'uri' : self.uri})
        
    def _getSourceImage(self):
        """get PIL image for the source. This is at full size still,
        but includes any alt processing. Also returns an extension for
        passing to Image.save, and also isAlt

        inefficient because we load full-res images just to get a
        smaller version of a face crop, for example. we should figure
        out the cheapest way to get the requested size
        """
        sources = self.graph.queryd(
            "SELECT ?source WHERE { ?source pho:alternate ?uri }",
            initBindings={'uri' : self.uri})
        if not sources:
            isAlt = False
            source = self.sourcePath()
            ext = self.uri
        else:
            isAlt = True
            up = MediaResource(self.graph, sources[0]['source'])
            # this could repeat- alts of alts. not handled yet.
            source = up.sourcePath()
            ext = up.uri
        
        img = Image.open(source)

        if isAlt:
            img = self._performAltProcess(img)
            
        return img, ext, isAlt

    def _performAltProcess(self, img):
        desc = {}
        types = []
        for row in self.graph.queryd(
            "SELECT ?k ?v WHERE { ?alt ?k ?v }",
            initBindings={'alt' : self.uri}):
            if row['k'] == RDF.type:
                types.append(row['v'])
            else:
                desc[row['k']] = row['v']
                
        if PHO.Crop in types:
            return self._altCrop(img, desc)
        else:
            raise NotImplementedError(
                "cannot process this alt description: %s" % desc)

    def _altCrop(self, source, desc):
        """PIL image for the described crop"""
        w, h = source.size
        return source.crop((int(w * desc[PHO.x1].toPython()),
                            int(h * desc[PHO.y1].toPython()),
                            int(w * desc[PHO.x2].toPython()),
                            int(h * desc[PHO.y2].toPython())))

    def _thumbPath(self, maxSize):
        if maxSize is Video2:
            h = hashlib.md5(self.uri + "?size=video2").hexdigest()
            return '/var/cache/photo/video/%s/%s.webm' % (h[:2], h[2:])
        else:
            thumbUrl = self.uri + "?size=%s" % maxSize
            cksum = hashlib.md5(thumbUrl).hexdigest()
            return "/var/cache/photo/%s/%s/%s" % (cksum[:2], cksum[2:4], cksum[4:])

    def sourcePath(self):
        """filesystem path to the source image"""
        # uri like http://photo.bigasterisk.com/digicam/housewarm/00023.jpg
        #         means /my/pic/digicam/housewarm/00023.jpg
        assert self.uri.startswith("http://photo.bigasterisk.com/")
        return "/my/pic/" + urllib.unquote(
            self.uri[len("http://photo.bigasterisk.com/"):])

    def _sourceExists(self):
        return os.path.exists(self.sourcePath())


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
