"""
compare images taken consecutively, when they're similar enough, make
a new set out of the similar images. Give it a type that draws as 1
image within a image set list. List one image as the preferred one
(last one? sharpest one?). Users can pick a different image to be the
preferred one in the set. Draw-as-1-img will also be the case for
crops and other refinements.

show the timeline of when the pics were taken. sometimes i take a series of pics to show how long something lasted.

sometimes the images aren't exactly consecutive. same-directory is
better than mixed directories, since those are probably from different
cameras

try to notice stereo-pair images.

record sharpness of every pic, especially for use in picking a set leader.

let the user break down a set according to a lower similarity
threshold, or breaking it apart entirely, or manually removing images
from it.

see http://xapian.wordpress.com/2009/03/11/xappy-now-supports-image-similarity-searching/

# next, get private access; walk through a bunch of imgs and see if there's a good threshold yet. Then try shrinking the size, blurring, etc.
        
other samples
# http://photo.bigasterisk.com/digicam/dl-2009-10-07/DSC_2015.JPG?size=small
# http://photo.bigasterisk.com/digicam/dl-2009-10-07/DSC_2016.JPG?size=small
# http://photo.bigasterisk.com/digicam/dl-2009-10-07/DSC_2012.JPG?size=small


"""
from __future__ import division
import datetime, sys
import restkit, Image, ImageOps, numpy
from StringIO import StringIO
from rdflib import Literal
import db
from ns import XS
from urls import absoluteSite

numpy.seterr(all='warn')

def hsv_from_rgb(image):
    # http://stackoverflow.com/questions/4890373/detecting-thresholds-in-hsv-color-space-from-rgb-using-python-pil
    r, g, b = image[:,:,0], image[:,:,1], image[:,:,2]
    m, M = numpy.min(image[:,:,:3], 2), numpy.max(image[:,:,:3], 2)
    d = M - m

    # Chroma and Value
    c = d
    v = M

    # Hue
    h = numpy.select([c == 0, r == M, g == M, b == M],
                     [0,
                      ((g - b) / c) % 6,
                      (2 + ((b - r) / c)),
                      (4 + ((r - g) / c))],
                     default=0) * 60

    # Saturation
    s = numpy.select([c == 0, c != 0], [0, c/v])

    return numpy.array([h, s, v]).transpose((1,2,0))

def arrayForImage(uri):
    res = 5
    hueStrength = 1.0
    satStrength = .5
    valStrength = .4

    au = absoluteSite(uri)
    jpg = restkit.Resource(au).get(size='thumb').body_string()
    i = Image.open(StringIO(jpg))
    i = Image.blend(i, ImageOps.autocontrast(i, cutoff=5), .8)
    i = i.resize((res ,int(res*3/4)), Image.ANTIALIAS)
    ar = numpy.asarray(i, dtype='f') / 255
    ar.shape = i.size[1], i.size[0], 3
    ar = hsv_from_rgb(ar) * [hueStrength/360, satStrength, valStrength]
    return ar

def inlineImage(img, cap):
    assert isinstance(img, Image.Image)
    out = StringIO()
    img.save(out, "jpeg")
    return '<img src="data:image/jpeg;base64,%s" width="60"><span>%s</span>' % (
        out.getvalue().encode('base64'), cap)

def prepImage(uri):
    img = arrayForImage(uri)

    process = Image.fromarray(numpy.uint8(img*255), 'RGB')
    h,s,v = process.split()
    processImgs = (inlineImage(h, "hue") +
                   inlineImage(s, "sat") +
                   inlineImage(v, "val"))
    return img, processImgs

def compare(uri1, uri2, img1, img2, processImgs1, processImgs2):
    abs1 = absoluteSite(uri1)
    abs2 = absoluteSite(uri2)
    m = numpy.minimum(img1.shape, img2.shape)
    crop1 = img1[:m[0],:m[1],:]
    crop2 = img2[:m[0],:m[1],:]

    row = """
    <div>
    <div>{uri1} - {uri2}</div>
    <img src="{abs1}?size=thumb"><span>uri1</span>
    <img src="{abs2}?size=thumb"><span>uri2</span>
    /
    {processImgs1}
    {processImgs2}
    """.format(**vars())

    outVal = None
    for alg, scl, out in [
        #('norm', 800/.42, numpy.linalg.norm(crop1 - crop2) / m.sum()),
        ('sum', 800/1.46, numpy.abs(crop1-crop2).reshape((-1,)).sum(axis=0) / m.sum())]:

        outVal = out
        row += '<pre>{alg:<8}: <span class="bar" style="width: {w}px">{out}</span></pre>'.format(alg=alg, out=out, w=out*scl)

    row += "</div>"
    return outVal, row

def analyze(graph, uris):
    img1 = uri1 = processImgs1 = None
    outRows = []
    for i, uri2 in enumerate(uris):
        print >>sys.stderr, "%s of %s" % (i+1, len(uris))
        img2, processImgs2 = prepImage(uri2)
        
        if img1 is not None:
            outVal, row = compare(uri1, uri2, img1, img2,
                                  processImgs1, processImgs2)
            outRows.append((outVal, row))

        img1 = img2
        uri1 = uri2
        processImgs1 = processImgs2

    outRows.sort()
    for row in outRows:
        print row[1]
        

def picsOnDay(graph, day):
    return [row['pic'] for row in graph.queryd(
        "SELECT ?pic WHERE { ?pic a foaf:Image ; dc:date ?day } ORDER BY ?pic",
        initBindings={'day' : Literal(day, datatype=XS['date'])})]

graph = db.getGraph()
print """

<style>
body {
font-family: monospace;
}
body > div {
   border: 1px solid gray;
    margin: 6px;
    }
.bar {
display: inline-block;
height: 30px;
background: #d5d5d5;
}
img + span {
    position: relative;
    left: -30px;
    top: 10px;
    color: #F4F4F4;
    text-shadow: .5px .5px 0px #000000;
    opacity: 1;
    width: 0;
    display: inline-block;
}
</style>
"""
analyze(graph, [u for u in (picsOnDay(graph, datetime.date(2011,9,16))
                            + picsOnDay(graph, datetime.date(2011,9,17)))
                #if any(x in str(u) for x in '4403 4404 4445 4446'.split())
                ])

    
