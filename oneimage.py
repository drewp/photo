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
import web, sys, jsonlib, datetime, cgi, time, logging, urllib
from web.contrib.template import render_genshi
from rdflib import Namespace, RDFS, URIRef, RDF, Variable
from remotesparql import RemoteSparql
from public import isPublic, makePublics
import networking, auth
from xml.utils import iso8601
from tagging import getTagLabels

PHO = Namespace("http://photo.bigasterisk.com/0.1/")
SITE = Namespace("http://photo.bigasterisk.com/")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")
EXIF = Namespace("http://www.kanzaki.com/ns/exif#")
SCOT = Namespace("http://scot-project.org/scot/ns#")
DC = Namespace("http://purl.org/dc/elements/1.1/")

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

class facts(object):
    def GET(self):
        img = URIRef(web.input()['uri'])

        # check security

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
            ] + auth.birthdays:
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

        return jsonlib.write({'factLines' : lines})

class links(object):
    """images and other things related to this one"""
    def GET(self):

        img = URIRef(web.input()['uri'])
        links = {}
        
        def relQuery(rel):
            rows = graph.queryd("""
               SELECT DISTINCT ?d ?label WHERE {
                 ?img ?rel ?d .
                 OPTIONAL { ?d rdfs:label ?label }
               }""", initBindings={Variable("rel") : rel,
                                   Variable("img") : img})
            for r in rows:
                if 'label' not in r:
                    r['label'] = r['d']
                yield r

        def setUrl(**params):
            params['current'] = img
            return ('/set?' + urllib.urlencode(params))

        for row in relQuery(FOAF.depicts):
            links.setdefault('depicting', []).append(
                {'uri' : row['d'], 'label' : row['label']})

        for row in relQuery(PHO.inDirectory):
            links.setdefault('inDirectory', []).append(
                {'uri' : setUrl(dir=row['d']),
                 'label' : row['d'].split('/')[-2]})

        for row in relQuery(DC.date):
            links.setdefault('takenOn', []).append(
                {'uri' : setUrl(date=row['d']),
                 'label' : row['d']})

        for row in relQuery(SCOT.hasTag):
            links.setdefault('withTag', []).append(
                {'uri' : setUrl(tag=row['label']),
                 'label' : row['label']})

        # taken near xxxxx

        return jsonlib.write({'links' : links.items()})

from tagging import getTags, saveTags

class tags(object):
    """description too, though you can get that separately if you want"""
    def GET(self):
        img = URIRef(web.input()['uri'])
        user = URIRef(web.ctx.environ['HTTP_X_FOAF_AGENT'])
        web.header("Content-Type", "text/json")
        return jsonlib.dumps(getTags(graph, user, img))

    def PUT(self):
        i = web.input()
        img = URIRef(i['uri'])
        user = URIRef(web.ctx.environ['HTTP_X_FOAF_AGENT'])
        saveTags(graph,
                 foafUser=user,
                 img=img,
                 tagString=i.get('tags', ''),
                 desc=i.get('desc', ''))
        web.header("Content-Type", "text/json")
        return jsonlib.dumps(getTags(graph, user, img))

        

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
    if photoDate is None:
        raise ValueError("can't find a date for %s" % uri)
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
                                     scot=SCOT,
                                     pho=PHO))

    urls = (r'/', "index",
            r'/facts', 'facts',
            r'/links', 'links',
            r'/viewPerm', 'viewPerm',
            r'/stats', 'stats',
            r'/tags', 'tags',
            )

    app = web.application(urls, globals(), autoreload=True)

    sys.argv.append("9043")
    app.run()
