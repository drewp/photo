#!/usr/bin/python

"""
webpy+genshi tool for browsing the hierarchy of pics (especially to
find the newest ones) and making them publicly viewable. End of
mission statement.
"""
import web, sys
from web.contrib.template import render_genshi
from rdflib import Namespace, RDFS, Variable, URIRef, RDF
from remotesparql import RemoteSparql
from edit import writeStatements

PHO = Namespace("http://photo.bigasterisk.com/0.1/")
SITE = Namespace("http://photo.bigasterisk.com/")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")
EXIF = Namespace("http://www.kanzaki.com/ns/exif#")

render = render_genshi('.', auto_reload=True)

graph = RemoteSparql("http://bang:8080/openrdf-sesame/repositories", "photo",
                     initNs=dict(foaf=FOAF,
                                 rdfs=RDFS.RDFSNS,
                                 rdf=RDF.RDFNS,
                                 exif=EXIF,
                                 pho=PHO))

class index(object):
    def GET(self):
        i = web.input()
        topDir = URIRef(i.get('dir', '') or 'http://photo.bigasterisk.com/')

        return render.browse2_index(
            subdirs=graph.queryd("""
              SELECT DISTINCT ?subdir WHERE {
                ?subdir pho:inDirectory ?topDir .
                ?subdir rdf:type ?type .
                OPTIONAL { ?subdir exif:dateTime ?t . }
              } ORDER BY ?type desc(?t) ?subdir""",
                                 initBindings={Variable("topDir") : topDir}),
            recent=graph.queryd("""
              SELECT DISTINCT ?pic ?dateTime WHERE {
                ?pic a foaf:Image;
                     exif:dateTime ?dateTime .
              }  LIMIT 10
            """),#ORDER BY desc(?dateTime)
            parent=graph.value(topDir, PHO.inDirectory),
            viewable=lambda uri: graph.contains((uri, PHO.viewableBy,
                                                PHO.friends)),
            )

class makePublic(object):
    def POST(self):
        i = web.input()
        uri = URIRef(i['uri'])
        print writeStatements([
            (uri, PHO.viewableBy, PHO.friends)
            ])
        return "public"
               

urls = (r'/', "index",
        r'/makePublic', 'makePublic',
        )

app = web.application(urls, globals())

if __name__ == '__main__':
    sys.argv.append("9025")
    app.run()
