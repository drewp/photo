"""
story view
"""
import urllib, time, restkit, logging, json, hashlib
from imageSet import photosWithTopic
from lib import print_timing
from genshi import Markup
from genshi.template import TemplateLoader
from genshi.output import XHTMLSerializer
import pystache

from rdflib import RDFS
from urls import localSite
from imageurl import starFilter
from oneimage import photoCreated
import networking, access
from mediaresource import sizes, MediaResource
loader = TemplateLoader(".", auto_reload=True)
serializer = XHTMLSerializer()
log = logging.getLogger()

def syncServiceCall(name, photoUri, foafUser, **moreParams):
    if not photoUri:
        raise ValueError("no uri to %s service call" % name)
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
    innerUri = localSite(uri) + '/size'
    site = restkit.Resource('http://bang:8086/')
    # restkit.get would hang in this twisted process
    return json.loads(site.get(path=innerUri, size=sizeName,
                                  headers={'x-foaf-agent' : foafUser}
                                  ).body_string())

def sizeAttrs(graph, foafUser, uri, sizeName):
    # this is similar to serve.ImageSizeResponse.renderHTTP, to avoid
    # an http call
    size = sizes[sizeName]
    r = MediaResource(graph, uri)
    w, h = r.getSize(size)
    return {'width' : w, 'height' : h}

@print_timing
def renderPage(graph, topic, foafUser, cookie):
    isVideo = {}
    photos = photosWithTopic(graph, {'topic':topic}, isVideo=isVideo)
    filtered = starFilter(graph, 'only', foafUser, photos)
    if filtered:
        photos = filtered 
    
    tmpl = loader.load("story.html")

    rows = []
    knownFacts = set()
    commentJs = '1'
    for photo in photos:
        if not access.viewable(graph, photo, foafUser):
            log.debug("story %s NeedsMoreAccess because %s can't view %s", topic, foafUser, photo)
            raise access.NeedsMoreAccess()
        try:
            date = photoCreated(graph, photo).date()
        except ValueError:
            date = None
        else:
            if not rows or rows[-1]['date'] != date:
                rows.append(dict(type='date', date=date))

        facts = json.loads(syncServiceCall('facts', photo, foafUser))
        factLines = [l['line'] for l in facts['factLines']
                     if not l['line'].startswith("Picture taken ")]
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
            isVideo=isVideo.get(photo, False),
            commentHtml=Markup(commentHtml),
            desc=graph.value(photo, RDFS.comment),
            ))

    accessControl = pystache.render(
        open("template/aclwidget.mustache").read(),
        access.accessControlWidget(graph, foafUser, topic))
    
    stream = tmpl.generate(
        rows=rows,
        title=graph.value(topic, RDFS.label, any=True),
        localSite=localSite,
        loginBar=Markup(networking.getLoginBarSync(cookie)),
        accessControl=Markup(accessControl),
        dateRange=findDateRange(graph, photos),
        sizeAttrs=lambda uri, sizeName: sizeAttrs(graph, foafUser, uri, sizeName),
        )
    return (''.join(serializer(stream))).encode('utf8')

def findDateRange(graph, photos):
    dates = set()
    for p in photos:
        try:
            dt = photoCreated(graph, p)
            dates.add(dt.date())
        except ValueError:
            pass
    if not dates:
        return "(no photos with dates)"
    lo = min(dates)
    hi = max(dates)
    if lo == hi:
        return lo.isoformat()
    return "%s to %s" % (lo.isoformat(), hi.isoformat())
    
