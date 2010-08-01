#!/usr/bin/python

"""
backend service that does operations on a single image

uses 'x-foaf-agent' header for permissions

POST /viewPerm?value=public&img=http://photo.bigast... -> {msg: "public"}
GET /viewPerm?img=http://photo.bigast... -> { public: true }
GET /facts?img=http://photo.bigast... -> rendered table
GET /ariDateAge?img=http://photo... -> for ari photos

the fetching of the resized images is still over in serve
"""
import web, sys, jsonlib, datetime, cgi, time, logging
from web.contrib.template import render_genshi
from rdflib import Namespace, RDFS, URIRef, RDF
from remotesparql import RemoteSparql
from public import isPublic, makePublics
import networking
from xml.utils import iso8601
from tagging import getTagLabels

PHO = Namespace("http://photo.bigasterisk.com/0.1/")
SITE = Namespace("http://photo.bigasterisk.com/")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")
EXIF = Namespace("http://www.kanzaki.com/ns/exif#")
SCOT = Namespace("http://scot-project.org/scot/ns#")

log = logging.getLogger()
render = render_genshi('.', auto_reload=True)

class viewPerm(object):
    def GET(self):
        i = web.input()
        uri = URIRef(i['img'])
        web.header('Content-type', 'application/json')
        return jsonlib.dumps({"viewableBy" :
                         "public" if isPublic(graph, uri) else "superuser"})
        
    def POST(self):
        """
        img=http://photo & img=http://photo2 & ...
        """
        # security here---

        uris = []
        for k, v in cgi.parse_qsl(web.data()):
            if k == 'img':
                uris.append(URIRef(v))
        
        makePublics(uris)
        
        web.header('Content-type', 'application/json')
        return '{"msg" : "public"}'


def facts(graph, img):

    lines = []
    now = time.time()

    try:
        created = photoCreated(graph, img)
        sec = time.mktime(created.timetuple())
    except ValueError:
        return ''

    ago = int((now - sec) / 86400)
    if ago < 365:
        ago = '; %s days ago' % ago
    else:
        ago = ''
    lines.append("Picture taken %s%s" % (created.isoformat(' '), ago))

    allDepicts = [row['who'] for row in
                  graph.queryd(
                      "SELECT DISTINCT ?who WHERE { ?img foaf:depicts ?who }",
                      initBindings={"img" : img})]

    allTags = getTagLabels(graph, "todo", img)

    for who, tag, birthday in [
        (URIRef("http://photo.bigasterisk.com/2008/person/apollo"),
        'apollo',
         '2008-07-22'),
        ]:
        try:
            if (who in allDepicts or tag in allTags):
                name = graph.value(
                    who, FOAF.name, default=graph.label(
                        who, default=tag))

                lines.append("%s is %s old. " % (
                    name, personAgeString(birthday, created.isoformat())))
        except Exception, e:
            log.error("%s birthday failed: %s" % (who, e))


    # 'used in this blog entry'
    return lines


class stats(object):
    def GET(self):
        i = web.input()
        uri = URIRef(i['img'])
        web.header('Content-type', 'application/json')

        # check security

        # this will be all the stuff in render_facts

        d = graph.value(uri, EXIF.dateTime)

        return jsonlib.dumps({"date" : d,
                             
                              })

def personAgeString(isoBirthday, photoDate):
    try:
        sec = iso8601.parse(str(photoDate))
    except Exception:
        sec = iso8601.parse(str(photoDate) + '-0700')

    birth = iso8601.parse(isoBirthday)
    days = (sec - birth) / 86400
    if days / 30 < 12:
        return "%.2f months" % (days / 30)
    else:
        return "%.2f years" % (days / 365)

_photoCreated = {} # uri : datetime
def photoCreated(graph, uri):
    """datetime of the photo's creation time. Cached for the life of
    this process"""

    try:
        return _photoCreated[uri]
    except KeyError:
        pass
    
    photoDate = (graph.value(uri, EXIF.dateTime) or
                 graph.value(uri, PHO.fileTime))
    try:
        sec = iso8601.parse(str(photoDate))
    except Exception:
        sec = iso8601.parse(str(photoDate) + '-0700')

    # todo: this is losing tz unnecessarily
    ret = datetime.datetime.fromtimestamp(sec)
    _photoCreated[uri] = ret
    return ret


if __name__ == '__main__':

    graph = RemoteSparql(networking.graphRepoRoot(), "photo",
                         initNs=dict(foaf=FOAF,
                                     rdfs=RDFS.RDFSNS,
                                     rdf=RDF.RDFNS,
                                     exif=EXIF,
                                     pho=PHO))

    urls = (r'/', "index",
            r'/viewPerm', 'viewPerm',
            r'/stats', 'stats',
            )

    app = web.application(urls, globals(), autoreload=True)

    sys.argv.append("9043")
    app.run()
