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
import json, time, urllib, datetime, itertools
from dateutil.tz import tzlocal
from klein import run, route
from rdflib import URIRef, Variable, Literal
import auth
from xml.utils import iso8601
from tagging import getTagLabels
import access, webuser
from oneimagequery import photoCreated
from ns import PHO, FOAF, EXIF, SCOT, DC, RDF, DCTERMS
from urls import localSite
from alternates import findAltRoot
import db
import networking

log = boot.log

@route('/viewPerm', methods=['GET'])
def GET_viewPerm(request):
    uri = URIRef(request.args['img'][0])
    request.setHeader('Content-type', 'application/json')
    return json.dumps({"viewableBy" :
                "public" if access.isPublic(graph, uri) else "superuser"})

@route('/viewPerm', methods=['POST'])
def POST_viewPerm(request):
    """
    moved to /aclChange
    """
    raise NotImplementedError

@route('/facts')
def GET_facts(request):
    request.setHeader("content-type", "application/json")
    img = URIRef(request.args['uri'][0])

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
                if (who in allDepicts or Literal(tag) in allTags):
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

@route('/links')
def GET_links(request):
    """images and other things related to this one"""

    img = URIRef(request.args['uri'][0])
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

    alts = findAltRoot(graph, img)
    if alts:
        links['alternates'] = [{'uri' : setUrl(alt=alts[0]),
                               'label' : alts[1]}]

    # taken near xxxxx

    return json.dumps({'links' : links.items()})

from tagging import getTags, saveTags


@route('/tags', methods=['GET'])
def GET_tags(request):
    """description too, though you can get that separately if you want"""
    img = URIRef(request.args['uri'][0])
    user = webuser.getUserKlein(request)
    request.setHeader("Content-Type", "text/json")
    return json.dumps(getTags(graph, user, img))

@route('/tags', methods=['PUT'])
def PUT_tags(request):
    img = URIRef(request.args['uri'][0])
    user = webuser.getUserKlein(request)
    log.info('user %r', user)
    saveTags(graph,
             foafUser=user,
             img=img,
             tagString=request.args.get('tags', [''])[0],
             desc=request.args.get('desc', [''])[0])
    request.setHeader("Content-Type", "text/json")
    return json.dumps(getTags(graph, user, img))

        
@route('/stats')
def GET_stats(request):
    uri = URIRef(request.args['img'][0])
    request.setHeader('Content-type', 'application/json')

    # check security

    # this will be all the stuff in render_facts

    d = graph.value(uri, EXIF.dateTime)

    return json.dumps({"date" : d,

                          })

# GET should tell you about the alts for the image
@route('/alt', methods=['POST'])
def POST_alt(request):
    uri = URIRef(request.args['uri'][0])
    desc = json.load(request.content)
    if desc['source'] != str(uri):
        # sometimes this happens on a : vs %3A disagreement, which
        # is something I think I workaround elsewhere. Drop
        # 'source' attr entirely? figure out where this new :
        # escaping is happening?
        raise ValueError("source %r != %r" % (desc['source'], str(uri)))
    newAltUri = pickNewUri(uri, desc['tag'])

    ctx = URIRef(newAltUri + "#create")
    now = Literal(datetime.datetime.now(tzlocal()))
    creator = webuser.getUserKlein(request)
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
    run('0.0.0.0', networking.oneImageServer()[1])

