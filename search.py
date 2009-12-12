import urllib, os, random, time
from nevow import rend, loaders, tags as T
from rdflib import Namespace, URIRef, Variable
from urls import localSite, SITE
from tagging import getTagsWithFreqs
FOAF = Namespace("http://xmlns.com/foaf/0.1/")

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
        dates = random.sample(self.graph.queryd("""
              SELECT DISTINCT ?d WHERE { ?pic dc:date ?d }
           """), 3)
        for row in dates:
            d = row['d']
            allPicsThatDay = self.graph.queryd("""
                SELECT DISTINCT ?pic ?filename WHERE {
                  ?pic dc:date ?d .
                  ?pic a foaf:Image;
                       pho:filename ?filename
                }""", initBindings={Variable('d') : d})
            if not allPicsThatDay:
                continue
            pick = random.choice(allPicsThatDay)
            current = pick['pic']
            bindings = {Variable("pic") : current}
            tags = [[T.a(href=['http://photo.bigasterisk.com/set?tag=',
                               row['tag']])[row['tag']], ' ']
                    for row in self.graph.queryd(
                        """SELECT DISTINCT ?tag WHERE {
                             ?pic scot:hasTag [
                               rdfs:label ?tag ]
                           }""", initBindings=bindings)]
            depicts = [[T.a(href=row['uri'])[row['label']], ' ']
                       for row in self.graph.queryd("""
                         SELECT DISTINCT ?uri ?label WHERE {
                           ?pic foaf:depicts ?uri .
                           ?uri rdfs:label ?label .
                         }""", initBindings=bindings)]
            # todo: description and tags would be good too, and some
            # other service should be rendering this whole section
            yield T.div(class_="randPick")[
                T.a(href=['http://photo.bigasterisk.com/set?',
                          urllib.urlencode(dict(date=d, current=current))])[
                    T.img(src=[current, '?size=medium']),
                    ],
                T.div[tags],
                T.div[depicts],
                T.div[pick['filename'].replace('/my/pic/','')],
                ]

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
            yield T.div[T.a(href=[localSite('/set?dir='), uriFromDir(dirname)])[dirname]]

    def render_tags(self, ctx, data):
        freqs = getTagsWithFreqs(self.graph)
        freqs = sorted(freqs.items(), key=lambda (t, n): (-n, t))
        return T.ul[[T.li[T.a(href=["set?tag=", t])[t, " (", n, ")"]] for t, n in freqs]]
                    


def uriFromDir(dirname):
    assert dirname.startswith('/my/pic/')
    return URIRef(SITE + dirname[len('/my/pic/'):])
