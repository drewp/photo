import urllib, os, random, datetime, time, logging
from nevow import rend, loaders, tags as T
from rdflib import Literal
from urls import localSite
from tagging import getTagsWithFreqs, hasTags
from isodate.isodates import date_isoformat
from urls import photoUri
from lib import print_timing
from ns import FOAF, XS
log = logging.getLogger()

_datePool = []
_datePoolCreated = None
@print_timing
def randomDates(graph, n=3, rand=random, year=None):
    global _datePoolCreated, _datePool
    if _datePoolCreated < time.time() - 40000:
        _datePool = [row['d'] for row in graph.queryd("""
            SELECT DISTINCT ?d WHERE { ?pic dc:date ?d }
            """)]
        _datePoolCreated = time.time()

    pool = _datePool
    if year is not None:
        pool = [d for d in _datePool if str(d).startswith(year)]
    
    return rand.sample(pool, n)


@print_timing
def randomSet(graph, n=3, foafUser=None, seed=None, year=None, tags="without"):
    """
    list of dicts with uri, filename, date

    foafUser isn't used yet, but someday it probably will for security
    regarding presence-of-tags

    pass a seed if you want the same set of images repeatedly

    pass a year string to limit dates to that year

    todo: this should be doable with sparql SAMPLE, but in a little
    test, sesame was only giving me pics from the last 2 days.
    """
    rand = random.Random(seed)
    
    ret = []
    retUris = set()

    dates = randomDates(graph, n, rand, year)
    triesLeft = 100
    while len(ret) < n:
        triesLeft -= 1
        if triesLeft < 0:
            break
            
        if not dates: # accidental dups could exhaust the dates
            dates = randomDates(graph, 3, rand, year)
        d = dates.pop()

        allPicsThatDay = graph.queryd("""
            SELECT DISTINCT ?pic ?filename WHERE {
              ?pic dc:date ?d .
              ?pic a foaf:Image;
                   pho:filename ?filename .
            }""", initBindings={
                # unclear why this happened, but d was arriving as
                # a Literal string with no datatype and not matching
                # anything
                'd' : Literal(d, datatype=XS['date'])})
        if not allPicsThatDay:
            continue
        pick = rand.choice(allPicsThatDay)
        if pick['pic'] in retUris:
            continue

        if tags == "without" and hasTags(graph, foafUser, pick['pic']):
            log.debug("random: skip pic with tags")
            continue
        elif tags == "only" and not hasTags(graph, foafUser, pick['pic']):
            continue

        retUris.add(pick['pic'])
        ret.append({'uri': pick['pic'],
                    'filename' : pick['filename'],
                    'date' : d})
    return ret

@print_timing
def nextDateWithPics(graph, start, offset):
    """
    takes datetime and timedelta
    """
    tries = 100
    x = start + offset
    if isinstance(start, datetime.datetime):
        future = datetime.datetime.now()
    else:
        future = datetime.date.today()
    future = future + datetime.timedelta(days=2)
    
    while (not dateHasPics(graph, x)) and tries > 0 and x <= future:
        x = x + offset
        tries -= 1
    if not tries or x > future:
        raise ValueError("traveled too far")
    return x

try:
    _dateHasPics
except NameError:
    _dateHasPics = set()
def dateHasPics(graph, date):
    """
    takes datetime
    """
    dlit = Literal(date_isoformat(date), datatype=XS.date)
    if dlit in _dateHasPics:
        return True
    # should be an ASK
    rows = graph.queryd("""
               SELECT ?img WHERE {
                 ?img a foaf:Image; dc:date ?d .
               } LIMIT 1""", initBindings={"d" : dlit})
    ret = bool(list(rows))
    if ret:
        _dateHasPics.add(dlit)
    return ret

try:
    _topicLabels
except NameError:
    _topicLabels = {}
def topicLabel(graph, topic):
    try:
        return _topicLabels[topic]
    except KeyError:
        ret = _topicLabels[topic] = graph.label(
            topic,
            default=graph.value(topic, FOAF['name'], default=topic))
        return ret

class Events(rend.Page):
    docFactory = loaders.xmlfile("search.html")
    
    def __init__(self, ctx, graph):
        self.graph = graph
        rend.Page.__init__(self, ctx)

    @print_timing
    def render_topics(self, ctx, data):
        graph = self.graph
        byClass = {}
        for row in self.graph.queryd("""
          SELECT DISTINCT ?topic ?cls WHERE {
            ?img a foaf:Image ;
              foaf:depicts ?topic .
            ?topic a ?cls .
          }"""):
            byClass.setdefault(row['cls'], set()).add(row['topic'])

        for cls, topics in byClass.items():
            yield T.h2[graph.label(cls, default=cls)]
            rows = []
            for topic in topics:
                try:
                    localUrl = localSite(topic)
                except ValueError, e:
                    log.warn("skipping topic %r: %s" % (topic, e))
                    continue
                lab = topicLabel(graph, topic)
                rows.append((lab.lower(), T.div[T.a(href=localUrl)[lab]]))
            rows.sort()
            yield [r[1] for r in rows]

    @print_timing
    def render_saveSets(self, ctx, data):
        for row in self.graph.queryd("""
        SELECT DISTINCT ?set ?label WHERE {
          ?img pho:saveSet ?set .
          OPTIONAL { ?set rdfs:label ?label }
        }"""):
            yield T.div[
                T.a(href="/edit?saveSet=%s" %
                    urllib.quote(row['set'], safe=''))[
                        row.get('label') or row['set']]
                ]

    @print_timing
    def render_random(self, ctx, data):
        
        for randRow in randomSet(self.graph, 3):
            print 'randRow', randRow
            current = randRow['uri']
            bindings = {"pic" : current}
            tags = [[T.a(href=['/set?tag=', row['tag']])[row['tag']], ' ']
                    for row in self.graph.queryd(
                        """SELECT DISTINCT ?tag WHERE {
                             ?pic scot:hasTag [
                               rdfs:label ?tag ]
                           }""", initBindings=bindings)]
            depicts = [[T.a(href=localSite(row['uri']))[row['label']], ' ']
                       for row in self.graph.queryd("""
                         SELECT DISTINCT ?uri ?label WHERE {
                           ?pic foaf:depicts ?uri .
                           ?uri rdfs:label ?label .
                         }""", initBindings=bindings)]
            # todo: description and tags would be good too, and some
            # other service should be rendering this whole section
            yield T.div(class_="randPick")[
                T.a(href=['/set?',
                          urllib.urlencode(dict(date=randRow['date'],
                                                current=current))])[
                    T.img(src=[localSite(current), '?size=medium']),
                    ],
                T.div[tags],
                T.div[depicts],
                T.div[randRow['filename'].replace('/my/pic/','')],
                ]

    def render_seed(self, ctx, data):
        return random.randint(0, 9999999)

    @print_timing
    def render_newestDirs(self, ctx, data):
        # todo- should use rdf and work over all dirs
        top = '/my/pic/digicam'
        times = []
        for fn in os.listdir(top):
            fn = os.path.join(top, fn) + '/'
            if not os.path.isdir(fn):
                continue
            times.append((os.path.getmtime(fn), fn))
        times.sort(reverse=True)
        for t, dirname in times[:10]:
            # todo: escaping
            yield T.div[T.a(href=[localSite('/set?dir='), photoUri(dirname)])[dirname]]

    @print_timing
    def render_newestDates(self, ctx, data, n=5):
        dates = []
        d = datetime.datetime.now() + datetime.timedelta(days=1)
        while len(dates) < n:
            d = nextDateWithPics(self.graph, d,
                                 -datetime.timedelta(days=1))
            dates.append(T.li[T.a(href=["set?date=", date_isoformat(d)])[
                date_isoformat(d)]])
        return T.ul[dates]

    @print_timing
    def render_tags(self, ctx, data):
        freqs = getTagsWithFreqs(self.graph)
        freqs = sorted(freqs.items(), key=lambda (t, n): (-n, t))
        return T.ul[[T.li[T.a(href=["set?tag=", t])[t, " (", n, ")"]] for t, n in freqs]]
                    

