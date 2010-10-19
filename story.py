"""
story view
"""
import urllib, time, restkit, logging, jsonlib, hashlib
from imageSet import photosWithTopic
from lib import print_timing
from genshi import Markup

from genshi.template import TemplateLoader
from genshi.output import XHTMLSerializer
from rdflib import RDFS
from urls import localSite
from imageSet import starFilter
from oneimage import photoCreated
import networking
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

@print_timing
def renderPage(graph, topic, foafUser):
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

        facts = jsonlib.read(syncServiceCall('facts', photo, foafUser))
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
        title=graph.value(topic, RDFS.label),
        localSite=localSite,
        dateRange=findDateRange(graph, photos),
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
    