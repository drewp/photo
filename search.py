import urllib, os, random, datetime
from nevow import rend, loaders, tags as T
from rdflib import Namespace, Variable, Literal
from urls import localSite
from tagging import getTagsWithFreqs
from isodate.isodates import date_isoformat
from urls import photoUri

FOAF = Namespace("http://xmlns.com/foaf/0.1/")
XS = Namespace("http://www.w3.org/2001/XMLSchema#")

def randomDates(graph, n=3, rand=random):
    dates = rand.sample(graph.queryd("""
              SELECT DISTINCT ?d WHERE { ?pic dc:date ?d }
           """), n)
    return [row['d'] for row in dates]

def randomSet(graph, n=3, seed=None):
    """
    list of dicts with pic, filename, date

    pass a seed if you want the same set of images repeatedly
    """
    rand = random.Random(seed)
    
    ret = []
    retUris = set()

    dates = randomDates(graph, n, rand)

    while len(ret) < n:
        if not dates: # accidental dups could exhaust the dates
            dates = randomDates(graph, 3, rand)
        d = dates.pop()

        allPicsThatDay = graph.queryd("""
            SELECT DISTINCT ?pic ?filename WHERE {
              ?pic dc:date ?d .
              ?pic a foaf:Image;
                   pho:filename ?filename
            }""", initBindings={Variable('d') : d})
        if not allPicsThatDay:
            continue
        pick = rand.choice(allPicsThatDay)
        if pick['pic'] in retUris:
            continue
        retUris.add(pick['pic'])
        ret.append({'pic': pick['pic'],
                    'filename' : pick['filename'],
                    'date' : d})
    return ret

def nextDateWithPics(graph, start, offset):
    """
    takes datetime and timedelta
    """
    tries = 100
    x = start + offset
    while not dateHasPics(graph, x) and tries:
        x = x + offset
        tries -= 1
    if not tries:
        raise ValueError("traveled too far")
    return x

def dateHasPics(graph, date):
    """
    takes datetime
    """
    dlit = Literal(date_isoformat(date), datatype=XS.date)
    rows = graph.queryd("""
               SELECT ?img WHERE {
                 ?img a foaf:Image; dc:date ?d .
               }""", initBindings={Variable("d") : dlit})
    return bool(list(rows))

class Events(rend.Page):
    docFactory = loaders.xmlfile("search.html")
    
    def __init__(self, ctx, graph):
        self.graph = graph
        rend.Page.__init__(self, ctx)

    def render_topics(self, ctx, data):
        graph = self.graph
        byClass = {}
        for row in self.graph.queryd("""SELECT DISTINCT ?topic ?cls WHERE { ?img a foaf:Image ; foaf:depicts ?topic . ?topic a ?cls . }"""):
            byClass.setdefault(row['cls'], set()).add(row['topic'])

        for cls, topics in byClass.items():
            yield T.h2[graph.label(cls, default=cls)]
            rows = []
            for topic in topics:
                lab = graph.label(topic, default=graph.value(topic, FOAF['name'], default=topic))

                localUrl = localSite(topic)
                rows.append((lab.lower(), T.div[T.a(href=localUrl)[lab]]))
            rows.sort()
            yield [r[1] for r in rows]

    def render_saveSets(self, ctx, data):
        sets = set()
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
            
    def render_random(self, ctx, data):
        for randRow in randomSet(self.graph, 3):
            current = randRow['pic']
            bindings = {Variable("pic") : current}
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
                    T.img(src=[current, '?size=medium']),
                    ],
                T.div[tags],
                T.div[depicts],
                T.div[randRow['filename'].replace('/my/pic/','')],
                ]

    def render_seed(self, ctx, data):
        return random.randint(0, 9999999)

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

    def render_newestDates(self, ctx, data, n=5):
        dates = []
        d = datetime.datetime.now() + datetime.timedelta(days=1)
        while len(dates) < n:
            d = nextDateWithPics(self.graph, d,
                                 -datetime.timedelta(days=1))
            dates.append(T.li[T.a(href=["set?date=", date_isoformat(d)])[
                date_isoformat(d)]])
        return T.ul[dates]

    def render_tags(self, ctx, data):
        freqs = getTagsWithFreqs(self.graph)
        freqs = sorted(freqs.items(), key=lambda (t, n): (-n, t))
        return T.ul[[T.li[T.a(href=["set?tag=", t])[t, " (", n, ")"]] for t, n in freqs]]
                    

