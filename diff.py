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

problems: 4169 4170, 4182 4183, 4133 4134, 4403 4404

"""
from __future__ import division
import datetime, sys
from rdflib import RDF, URIRef
import restkit, Image, ImageOps, numpy
from StringIO import StringIO
from rdflib import Literal
import db
from ns import XS, SITE, PHO
from urls import absoluteSite
from spark import sparkline_discrete
from hsv import hsv_from_rgb
sys.path.append("../webcam3")
from radialprofile import azimuthalAverage

htmlHead = """
<style>
body { font-family: monospace; }
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
    color: #7E7E7E;
    display: inline-block;
    font-size: 7px;
    left: -30px;
    position: relative;
    top: 7px;
    width: 0;
}
.chart {
    height: 320px;
    position: relative;
}
.chart span {
    background: #8A96D3;
    bottom: 0;
    position: absolute;
    width: 2px;
}
</style>
"""

#cgitb.enable(format='text')
numpy.seterr(all='warn')

def arrayForImage(uri):
    res = 15
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

def imageForArray(ar, format):
    scaled = numpy.uint8(ar*255)
    img = Image.fromarray(scaled, format)
    return img

def hiresArray(uri):
    jpg = restkit.Resource(absoluteSite(uri)).get(size='screen').body_string()
    i = Image.open(StringIO(jpg)).convert('L')
    ar = numpy.asarray(i, dtype='f') / 255
    ar.shape = i.size[1], i.size[0]
    return ar

def getFreqs(ar):
    freqImage = numpy.abs(numpy.fft.fft2(ar))
    freqs = azimuthalAverage(freqImage)
    return freqs

def inlineImage(img, cap):
    assert isinstance(img, Image.Image)
    out = StringIO()
    img.save(out, "jpeg")
    return '<img src="data:image/jpeg;base64,%s"><span>%s</span>' % (
        out.getvalue().encode('base64'), cap)

def prepImage(uri):
    img = arrayForImage(uri)

    process = imageForArray(img, 'RGB')
    h,s,v = process.split()
    rs = lambda i: i.resize((64,64), Image.NEAREST)
    processImgs = (inlineImage(rs(h), "hue") +
                   inlineImage(rs(s), "sat") +
                   inlineImage(rs(v), "val"))
    return img, processImgs

def compare(uri1, uri2, img1, img2, processImgs1, processImgs2, includeFft):
    abs1 = absoluteSite(uri1)
    abs2 = absoluteSite(uri2)
    m = numpy.minimum(img1.shape, img2.shape)
    crop1 = img1[:m[0],:m[1],:]
    crop2 = img2[:m[0],:m[1],:]

    ffts = []
    if includeFft:
        for uri in [uri1, uri2]:
            freqs = range(5)#getFreqs(hiresArray(uri))
            ffts.append(inlineImage(
                sparkline_discrete(freqs[:int(len(freqs)*.9):2],
                                   dmin=0, width=1, height=70, longlines=True),
                'freqs'))
    else:
        ffts = ['', '']

    row = """
    <div>
      <div>{uri1} - {uri2}</div>
      <img src="{abs1}?size=thumb"><span>uri1</span>
      <img src="{abs2}?size=thumb"><span>uri2</span>
      /
      {processImgs1}
      {processImgs2}
      /
      {ffts[0]}
      {ffts[1]}
    """.format(**vars())

    outVal = None
    for alg, scl, out in [
        #('norm', 800/.42, numpy.linalg.norm(crop1 - crop2) / m.sum()),
        ('sum', 800/.38, numpy.abs(crop1-crop2).reshape((-1,)).sum(axis=0) / m.prod())]:

        outVal = out
        row += '<pre>{alg:<8}: <span class="bar" style="width: {w}px">{out}</span></pre>'.format(alg=alg, out=out, w=out*scl)

    row += "</div>"
    return outVal, row

def combineSets(comps, maxDelta):
    """
    return [set_of_uri, ...] where each set is all uris related better than max
    """
    out = []
    for a,b,d in comps:
        if d < maxDelta:
            if out and a in out[-1]:
                out[-1].add(b)
            else:
                out.append(set([a,b]))
    return out

def htmlChart(vals):
    html = '<div class="chart">'
    for i, v in enumerate(vals):
        html += '<span style="left: %spx; height: %spx"></span>' % (
            i*2, v * 300/.37)
    html += '</div>'
    return html

def analyze(graph, uris, maxDelta, includeFft=False):
    """
    returns a sloppy html page about the images that were read, and a
    list of RDF statements that state which images are in (rdf:type)
    which sets
    """
    html = htmlHead
    img1 = uri1 = processImgs1 = None
    outRows = []
    comps = [] # uri1, uri2, delta
    for i, uri2 in enumerate(uris):
        print "%s of %s" % (i+1, len(uris))
        img2, processImgs2 = prepImage(uri2)
        
        if img1 is not None:
            delta, row = compare(uri1, uri2, img1, img2,
                                 processImgs1, processImgs2, includeFft)
            outRows.append((delta, row))
            comps.append((uri1, uri2, delta))

        img1 = img2
        uri1 = uri2
        processImgs1 = processImgs2

    outRows.sort()

    html += htmlChart(r[0] for r in outRows)
    html += ''.join(r[1] for r in outRows)

    sets = combineSets(comps, maxDelta=maxDelta)
    stmts = set()
    for s in sets:
        uri = URIRef(min(s) + "/similarSet")
        stmts.add((uri, RDF.type, PHO['SimilaritySet']))
        for img in s:
            stmts.add((img, RDF.type, uri))
    return stmts, html

def picsOnDay(graph, day):
    return [row['pic'] for row in graph.queryd(
        "SELECT ?pic WHERE { ?pic a foaf:Image ; dc:date ?day } ORDER BY ?pic",
        initBindings={'day' : Literal(day, datatype=XS['date'])})]


graph = db.getGraph()

uris = (picsOnDay(graph, datetime.date(2011,9,16))
        + picsOnDay(graph, datetime.date(2011,9,17)))

stmts, html = analyze(
    graph, [u for u in uris if (
        'plus-local' not in str(u)
        and '44' in str(u)
        )], maxDelta=.078)

open("diffout.html", "w").write(html)

ctx = SITE['analyzedDiffs']
print "rewriting context %s" % ctx
graph.subgraphClear(ctx)
graph.add(stmts, ctx)


