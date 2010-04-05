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
from public import isPublic, makePublic

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
              SELECT DISTINCT ?subdir ?type WHERE {
                ?subdir pho:inDirectory ?topDir .
                ?subdir rdf:type pho:DiskDirectory .
                OPTIONAL { ?subdir exif:dateTime ?t . }
              } ORDER BY desc(?t) ?subdir""",
                                 initBindings={Variable("topDir") : topDir}),
            contents=graph.queryd("""
              SELECT DISTINCT ?pic ?dateTime WHERE {
                ?pic pho:inDirectory ?topDir .
                ?pic rdf:type ?type .
                FILTER (?type != pho:DiskDirectory) .
                OPTIONAL { ?pic exif:dateTime ?dateTime . }
              } ORDER BY desc(?dateTime) ?pic""",
                                 initBindings={Variable("topDir") : topDir}),
            recent=graph.queryd("""
              SELECT DISTINCT ?pic ?dateTime WHERE {
                ?pic a foaf:Image;
                     exif:dateTime ?dateTime .
              } ORDER BY desc(?dateTime) LIMIT 10
            """),#
            parent=graph.value(topDir, PHO.inDirectory),
            viewable=lambda uri: isPublic(graph, uri),
            )

class makePublicReq(object):
    def POST(self):
        i = web.input()
        uri = URIRef(i['uri'])
        makePublic(uri)
        return "public"
               

urls = (r'/', "index",
        r'/makePublic', 'makePublicReq',
        )

app = web.application(urls, globals())

if __name__ == '__main__':
    sys.argv.append("9028")
    app.run()
