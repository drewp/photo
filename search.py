from nevow import rend, loaders, tags as T
from rdflib import Namespace
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
                
                rows.append((lab.lower(), T.div[T.a(href=topic)[lab]]))
            rows.sort()
            yield [r[1] for r in rows]

