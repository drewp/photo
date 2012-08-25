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
from __future__ import division
import boot
import web, sys, json, time, urllib, datetime, itertools
from dateutil.tz import tzlocal
from web.contrib.template import render_genshi
from rdflib import URIRef, Variable, Literal
import auth
from xml.utils import iso8601
from tagging import getTagLabels
import access
from oneimagequery import photoCreated
from ns import PHO, FOAF, EXIF, SCOT, DC, RDF, DCTERMS
from urls import localSite
import db

log = boot.log
render = render_genshi('.', auto_reload=True)

class viewPerm(object):
    def GET(self):
        i = web.input()
        uri = URIRef(i['img'])
        web.header('Content-type', 'application/json')
        return json.dumps({"viewableBy" :
                    "public" if access.isPublic(graph, uri) else "superuser"})
        
    def POST(self):
        """
        moved to /aclChange
        """
        raise NotImplementedError

class facts(object):
    def GET(self):
        web.header("content-type", "application/json")
        img = URIRef(web.input()['uri'])

        # check security

        ret = {}
        lines = []
        now = time.time()

        try:
            created = photoCreated(graph, img)
            ret['created'] = created.isoformat()
            sec = time.mktime(created.timetuple())
        except ValueError, e:
            log.warn("no created time for %s" % img)
            import traceback
            traceback.print_exc()
            created = sec = None

        if sec is not None:
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

        if created is not None:
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

        ret['factLines'] = [dict(line=x) for x in lines]

        # 'used in this blog entry'        
        return json.dumps(ret)

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
            try:
                links.setdefault('depicting', []).append(
                    {'uri' : localSite(row['d']), 'label' : row['label']})
            except ValueError, e:
                log.warn("error in FOAF.depicts: %s %s" % (vars(), e))
                pass

        for row in relQuery(PHO.inDirectory):
            links.setdefault('inDirectory', []).append(
                {'uri' : setUrl(dir=row['d']),
                 'label' : row['d'].split('/')[-2]})

        for row in relQuery(DC.date):
            links.setdefault('takenOn', []).append(
                {'uri' : setUrl(date=row['d']),
                 'label' : row['d']})
        # photos from email may have only the email's date

        for row in relQuery(SCOT.hasTag):
            links.setdefault('withTag', []).append(
                {'uri' : setUrl(tag=row['label']),
                 'label' : row['label']})

        # taken near xxxxx

        return json.dumps({'links' : links.items()})

from tagging import getTags, saveTags



class tags(object):
    """description too, though you can get that separately if you want"""
    def GET(self):
        img = URIRef(web.input()['uri'])
        user = access.getUserWebpy(web.ctx.environ)
        web.header("Content-Type", "text/json")
        return json.dumps(getTags(graph, user, img))

    def PUT(self):
        i = web.input()
        img = URIRef(i['uri'])
        user = access.getUserWebpy(web.ctx.environ)
        saveTags(graph,
                 foafUser=user,
                 img=img,
                 tagString=i.get('tags', ''),
                 desc=i.get('desc', ''))
        web.header("Content-Type", "text/json")
        return json.dumps(getTags(graph, user, img))

        

class stats(object):
    def GET(self):
        i = web.input()
        uri = URIRef(i['img'])
        web.header('Content-type', 'application/json')

        # check security

        # this will be all the stuff in render_facts

        d = graph.value(uri, EXIF.dateTime)

        return json.dumps({"date" : d,
                             
                              })

class alt(object):
    # GET should tell you about the alts for the image
    
    def POST(self):
        uri = URIRef(web.input()['uri'])
        desc = json.loads(web.data())
        if desc['source'] != str(uri):
            # sometimes this happens on a : vs %3A disagreement, which
            # is something I think I workaround elsewhere. Drop
            # 'source' attr entirely? figure out where this new :
            # escaping is happening?
            raise ValueError("source %r != %r" % (desc['source'], str(uri)))
        newAltUri = self.pickNewUri(uri, desc['tag'])

        ctx = URIRef(newAltUri + "#create")
        now = Literal(datetime.datetime.now(tzlocal()))
        creator = access.getUserWebpy(web.ctx.environ)
        if not creator:
            raise ValueError("missing creator")
        
        stmts = [
            (uri, PHO.alternate, newAltUri),
            (newAltUri, RDF.type, FOAF.Image),
            (newAltUri, DCTERMS.creator, creator),
            (newAltUri, DCTERMS.created, now),
            ]
        
        for k, v in desc.items():
            if k in ['source']:
                continue
            if k == 'types':
                for typeUri in v:
                    stmts.append((newAltUri, RDF.type, URIRef(typeUri)))
            else:
                # this handles basic json types at most. consider
                # JSON-LD or just n3 as better input formats, but make
                # sure all their statements are about the uri, not
                # arbitrary data that could change security
                # permissions and stuff
                stmts.append((newAltUri, PHO[k], Literal(v)))
        
        graph.add(stmts, context=ctx)
        return "added %s statements to context %s" % (len(stmts), ctx)

    def pickNewUri(self, uri, tag):
        for suffix in itertools.count(1):
            proposed = URIRef("%s/alt/%s%s" % (uri, tag, suffix))
            if not graph.contains((proposed, None, None)):
                return proposed
                


def personAgeString(isoBirthday, photoDate):
    try:
        sec = iso8601.parse(str(photoDate))
    except Exception:
        sec = iso8601.parse(str(photoDate) + '-0700')

    birth = iso8601.parse(isoBirthday)
    days = (sec - birth) / 86400
    if days / 30 < 12:
        return "%.1f months" % (days / 30)
    else:
        return "%.1f years" % (days / 365)

if __name__ == '__main__':
    
    graph = db.getGraph()

    urls = (r'/', "index",
            r'/facts', 'facts',
            r'/links', 'links',
            r'/viewPerm', 'viewPerm',
            r'/stats', 'stats',
            r'/tags', 'tags',
            r'/alt', 'alt',
            )

    app = web.application(urls, globals(), autoreload=False)

    sys.argv.append("9043")
    app.run()
