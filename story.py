"""
story view
"""
import urllib, time, restkit, logging, json, hashlib
from imageSet import photosWithTopic
from lib import print_timing
from genshi import Markup

from genshi.template import TemplateLoader
from genshi.output import XHTMLSerializer
from rdflib import RDFS
from urls import localSite
from imageurl import starFilter
from oneimage import photoCreated
import networking, access
from photos import getSize, sizes
loader = TemplateLoader(".", auto_reload=True)
serializer = XHTMLSerializer()
log = logging.getLogger()

def syncServiceCall(name, photoUri, foafUser, **moreParams):
    t1 = time.time()
    params = {'uri' : photoUri}
    params.update(moreParams)
    url = '%s?%s' % (networking.serviceUrl(name), urllib.urlencode(params))
    response = restkit.request(url=url, headers={'x-foaf-agent' : foafUser})
    log.info("service call %r in %.01f ms", name, 1000 * (time.time() - t1))
    if response.status_int != 200:
        raise ValueError("in service call %s" % url)
    return response.body_string()

def sizeAttrs_by_http(foafUser, uri, sizeName):
    innerUri = uri.replace('http://photo.bigasterisk.com/', '/') + '/size'
    site = restkit.Resource('http://bang:8086/')
    # restkit.get would hang in this twisted process
    return json.loads(site.get(path=innerUri, size=sizeName,
                                  headers={'x-foaf-agent' : foafUser}
                                  ).body_string())

def sizeAttrs(foafUser, uri, sizeName):
    # this is similar to serve.ImageSizeResponse.renderHTTP, to avoid
    # an http call
    size = sizes[sizeName]
    w, h = getSize(uri, size)
    return {'width' : w, 'height' : h}

@print_timing
def renderPage(graph, topic, foafUser, cookie):
    photos = photosWithTopic(graph, topic)
    starFilter(graph, 'only', 'someagent', photos)
    
    tmpl = loader.load("story.html")

    rows = []
    knownFacts = set()
    commentJs = '1'
    for photo in photos:
        date = photoCreated(graph, photo).date()
        if not rows or rows[-1]['date'] != date:
            rows.append(dict(type='date', date=date))

        facts = json.loads(syncServiceCall('facts', photo, foafUser))
        factLines = [l for l in facts['factLines']
                     if not l.startswith("Picture taken ")]
        factLines = [l for l in factLines if l not in knownFacts]
        knownFacts.update(factLines)

        commentHtml = syncServiceCall('comments', photo, foafUser, js=commentJs)
        if commentJs == '1':
            commentJs = '0'

        rows.append(dict(
            type='pic',
            date=date,
            uri=photo,
            # more stable than the row num as pics get added and removed:
            anchor=hashlib.md5(photo).hexdigest()[:8],
            factLines=factLines,
            commentHtml=Markup(commentHtml),
            desc=graph.value(photo, RDFS.comment),
            ))
    
    stream = tmpl.generate(
        rows=rows,
        title=graph.value(topic, RDFS.label, any=True),
        localSite=localSite,
        loginBar=Markup(networking.getLoginBarSync(cookie)),
        accessControl=Markup(access.accessControlWidget(graph, foafUser, topic).decode('utf8')),
        dateRange=findDateRange(graph, photos),
        sizeAttrs=lambda uri, sizeName: sizeAttrs(foafUser, uri, sizeName),
        )
    return (''.join(serializer(stream))).encode('utf8')

def findDateRange(graph, photos):
    dates = set()
    for p in photos:
        dt = photoCreated(graph, p)
        dates.add(dt.date())
    if not dates:
        return "(no dates)"
    lo = min(dates)
    hi = max(dates)
    if lo == hi:
        return lo.isoformat()
    return "%s to %s" % (lo.isoformat(), hi.isoformat())
    
