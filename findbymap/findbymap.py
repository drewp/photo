import sys, random
sys.path.append("..")
from boot import log
import path, cyclone.web, time, restkit, logging
from twisted.internet import reactor, task
from rdflib import Literal, URIRef
import db
from sesameSyncImport import PrettyErrorHandler
import auth, webuser

log.setLevel(logging.DEBUG)

class Photos(PrettyErrorHandler, cyclone.web.RequestHandler):
    def get(self):
        foaf = webuser.getUserCyclone(self.request)
        if foaf not in auth.superagents:
            raise ValueError("no ACL support yet")

        graph = self.settings.graph
        arg = self.get_argument
        t1 = time.time()
        class SparqlFloat(float):
            def n3(self):
                return str(self)
        bindings = dict(
            # wrong near coord wrap points
            lat1=SparqlFloat(min(float(arg("n")), float(arg("s")))),
            lat2=SparqlFloat(max(float(arg("n")), float(arg("s")))),
            long1=SparqlFloat(min(float(arg("e")), float(arg("w")))),
            long2=SparqlFloat(max(float(arg("e")), float(arg("w")))),
        )
        rows = graph.queryd("""
PREFIX wgs: <http://www.w3.org/2003/01/geo/wgs84_pos#>
SELECT DISTINCT ?pic ?lat ?long WHERE { 
?pic wgs:location [ wgs:lat ?lat ; wgs:long ?long ]
        FILTER (?lat > ?lat1 && ?lat < ?lat2 && ?long > ?long1 && ?long < ?long2 )
        }""", initBindings=bindings)
        print "%s -> %s rows in %s" % (bindings, len(rows), time.time() - t1)
        if len(rows) > 200:
            random.shuffle(rows)
            print "reducing"
            rows = rows[:200]
        # or two pics at same point should make a cluster too
        self.write({'markers':
                    [dict(uri=row['pic'], 
                          lat=row['lat'], 
                          long=row['long']) 
                     for row in rows]})


if __name__ == '__main__':
    reactor.listenTCP(
        9088, cyclone.web.Application(handlers=[
            (r"/(|gui.js)", cyclone.web.StaticFileHandler, {
                'path': '.', 'default_filename': 'index.html'
            }),
            (r'/photos', Photos),
        ], graph=db.getGraph()))
    reactor.run()
