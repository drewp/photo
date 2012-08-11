"""
implementation of http://esw.w3.org/WebAccessControl

currently this is contaminated with my old 'viewableBy' access system
and some other photo-site-specific things, but hopefully those can be
removed
"""

import logging, random, time, datetime, os
from dateutil.tz import tzlocal
from rdflib import URIRef, RDF, Literal
from nevow import inevow, url
import auth
from genshi.template import TemplateLoader
from genshi.output import XHTMLSerializer
from edit import writeStatements
from imageurl import ImageSetDesc
from lib import print_timing
from ns import PHO, FOAF, ACL, DCTERMS
loader = TemplateLoader(".", auto_reload=True)
serializer = XHTMLSerializer()
log = logging.getLogger()

class NeedsMoreAccess(ValueError):
    pass

def getUser(ctx):
    return _getUser(inevow.IRequest(ctx).getHeader)

def getUserWebpy(environ):
    return _getUser(
        lambda h: environ.get('HTTP_%s' % h.upper().replace('-','_')))

def _getUser(getHeader):
    if os.environ.get('PHOTO_FORCE_LOGIN', ''):
        return URIRef(os.environ['PHOTO_FORCE_LOGIN'])
    agent = getHeader('x-foaf-agent')
    if agent is None:
        return None
    return URIRef(agent)

def agentClassCheck(graph, agent, photo):
    """
    is there a perm that specifically lets this agent (or class) see this photo?
    """
    bb = {'initBindings' : {'photo' : photo, 'agent' : agent}}
    # UNION was breaking
    return (graph.queryd("ASK { ?photo pho:viewableByClass ?agent . }", **bb) or
            graph.queryd("ASK { ?photo pho:viewableBy ?agent . }", **bb) or
            graph.queryd("ASK { [ acl:agent ?agent ; acl:mode acl:Read ; acl:accessTo ?photo ] . }", **bb))

def viewableViaPerm(graph, uri, agent):
    """
    viewable via some permission that can be set and removed
    """
    if (graph.contains((uri, PHO['viewableBy'], PHO['friends']))
        or graph.contains((uri, PHO['viewableBy'], PHO['anyone']))):
        log.debug("ok, graph says :viewableBy :friends or :anyone")
        return True

    if graph.queryd("ASK { [ acl:agent pho:friends ; acl:mode acl:Read ; acl:accessTo ?photo ] .}", initBindings={'photo' : uri}):
        log.debug("ok, graph has an authorization for :friends")
        return True

    # spec wants me to use agentClass on this, but I've already
    # screwed that up elsewhere, so it will take new triples to make
    # the old data compatible
    if graph.queryd("ASK { [ acl:agent foaf:Agent ; acl:mode acl:Read ; acl:accessTo ?photo ] .}", initBindings={'photo' : uri}):
        log.debug("ok, graph has an authorization for foaf:Agent ('the public')")
        return True

    if agent and graph.queryd("""
        SELECT ?cls WHERE {
           {
             ?uri pho:viewableBy ?cls .
           } UNION {
             ?auth acl:accessTo ?uri ;
               acl:agent ?cls ;
               acl:mode acl:Read .
           }
           ?agent a ?cls .
        }
        """, initBindings={'uri' : uri, 'agent' : agent}):
        log.debug("ok because the user is in a class who may view the photo")
        return True

    if agent and graph.queryd("""
       SELECT ?auth WHERE {
         ?auth acl:agent ?agent ; acl:mode acl:Read ; acl:accessTo ?uri .
       }
    """, initBindings={'uri' : uri, 'agent' : agent}):
        log.debug("ok because the user has been authorized to read the photo")
        return True

    
    if agent and graph.queryd("""
       SELECT ?auth WHERE {
         { ?auth acl:agent ?agentClass . } UNION {
           ?auth acl:agentClass ?agentClass .
         }
         ?auth acl:mode acl:Read ; acl:accessTo ?uri .
         ?agent a ?agentClass .
       }
    """, initBindings={'uri' : uri, 'agent' : agent}):
        log.debug("ok because the user has been authorized to read the photo")
        return True

    if agent and graph.queryd("""
        SELECT ?cls WHERE {
           ?uri foaf:depicts ?topic . 
           ?topic pho:viewableByClass ?cls .
           ?agent a ?cls .
        }
        """, initBindings={'uri' : uri, 'agent' : agent}):
        log.debug("ok because the user is in a class who may view the photo's topic")
        return True


    if agent:
        imgSet = agentImageSetCheck(graph, agent, uri)
        if imgSet is not None:
            log.debug("ok because user has permission to see %r", imgSet)
            return True

    # this capability doesn't appear in the make-public button
    topicViewableBy = set(r['vb'] for r in graph.queryd("""
    SELECT ?vb WHERE {
      ?uri foaf:depicts ?d .
      ?d pho:viewableBy ?vb .
      }
    """, initBindings={"uri" : uri}))
    if (PHO['friends'] in topicViewableBy or
        PHO['anyone'] in topicViewableBy):
        log.debug("a photo topic is viewable by anyone")
        return True

    return False

@print_timing
def agentImageSetCheck(graph, agent, photo):
    """
    does this agent (or one of its classes) have permission to
    view some imageset that (currently) includes the image?

    returns an imageset URI or None
    """
    
    for row in graph.queryd("""
     SELECT DISTINCT ?access WHERE {
       ?auth acl:mode acl:Read ; acl:accessTo ?access .
       {
         ?auth acl:agent ?agent .
       } UNION {
         { ?auth acl:agentClass ?agentClass . } UNION { ?auth acl:agent ?agentClass . }
         ?agent a ?agentClass .
       }
     }
    """, initBindings={'agent' : agent}):
        maySee = row['access']
        if 'bigasterisk.com/openidProxySite' in maySee:
            # some other statements about permissions got in the
            # graph; it's wasting time to check them as images
            continue
        log.debug("%r can see %r - is the pic in that set?", agent, maySee)
        try:
            imgSet = ImageSetDesc(graph, agent, maySee)
        except ValueError:
            # includes permissions for things that aren't photos at all
            continue
        if imgSet.includesPhoto(photo):
            return maySee
    return None

def viewableViaInference(graph, uri, agent):
    """
    viewable for some reason that can't be removed here
    """

    # somehow allow local clients who could get to the filesystem
    # anyway. maybe with a cookie file in the fs, or just ip
    # screening

    if graph.queryd("""
        SELECT ?post WHERE {
          <http://bigasterisk.com/ari/> sioc:container_of ?post .
          ?post sioc:links_to ?uri .
        }""", initBindings={'uri' : uri}): # should just be ASK
        # this should also be limiting to readers of the blog!
        log.debug("ok because it's on the blog")
        return True

    return False

def viewableBySuperAgent(agent):
    # not final; just matching the old logic. Oops- this fast one gets
    # checked after some really slow queries. But that's ok; I get a
    # better taste of the slowness of the site this way
    if agent in auth.superagents:
        log.debug("ok, agent %r is in superagents", agent)
        return True
    return False


@print_timing
def viewable(graph, uri, agent):
    """
    should the resource at uri be retrievable by this agent
    """
    log.debug("viewable check for %s to see %s", agent, uri)
    ok = (viewableBySuperAgent(agent) or
          viewableViaPerm(graph, uri, agent) or
          viewableViaInference(graph, uri, agent))
    if not ok:
        log.debug("not viewable")

    return ok


def interestingAclAgentsAndClasses(graph):
    """
    what agents and classes should we offer to set perms by?
    returns rows with ?uri and ?label
    """
    return graph.queryd("""
      SELECT DISTINCT ?uri ?label WHERE {
        ?uri a pho:AgentsForAclUi .
        OPTIONAL { ?uri rdfs:label ?label }
      }""")

def agentMaySetAccessControl(agent):
    # todo: read acl.Control settings
    return agent in auth.superagents

# belongs in another module
def expandPhotos(graph, user, subject):
    """
    returns the set of images that this subject refers to, plus a
    short description of the set

    subject can be a photo itself, some search query, a topic, etc
    """

    # this may be redundant with what ImageSetDesc does with one photo?
    if graph.contains((subject, RDF.type, FOAF.Image)):
        return [subject], "this photo"

    #URIRef('http://photo.bigasterisk.com/set?current=http%3A%2F%2Fphoto.bigasterisk.com%2Femail%2F2010-11-15%2FP1010194.JPG&dir=http%3A%2F%2Fphoto.bigasterisk.com%2Femail%2F2010-11-15%2F')
    pics = ImageSetDesc(graph, user, subject).photos()
    if len(pics) == 1:
        return pics, "this photo"
    else:
        return pics, "these %s photos" % len(pics)

def agentCanSeeAllPhotos(graph, agent, photos):
    """
    may return 'inferred' to mean 'yes, but at least one is not from a
    permission setting that can be removed'

    this is a problem because if just one in the set is inferred, you
    should be able to set a perm that covers the rest but remove that
    perm later. The UI should probably present inferred access totally
    separately
    """
    someInferred = False
    for p in photos:
        viaPerm = viewableViaPerm(graph, p, agent)
        viaInfer = viewableViaInference(graph, p, agent)
        if not viaPerm and not viaInfer:
            return False
        if not viaPerm:
            someInferred = True
        log.debug("%s ok for %s" % (p, agent))

    return 'inferred' if someInferred else True

def accessControlWidget(graph, agent, subject):
    """
    subject might be one picture or some collection

    some agents or classes might have access due to some other facts,
    so you can't turn them off from this UI.

    result is a dict for interpolating to aclwidget.html
    """
    if not agentMaySetAccessControl(agent):
        return ""

    photos, groupDesc = expandPhotos(graph, agent, subject)

    def agentRowSetting(agent, subject):
        if authorizations(graph, row['uri'], subject):
            return True
        if all(agentClassCheck(graph, row['uri'], p) for p in photos):
            return 'inferred'
        return False

    agents = []
    for row in interestingAclAgentsAndClasses(graph):
        setting = agentRowSetting(row['uri'], subject)
        agents.append(dict(
            label=row['label'],
            setting=setting,
            uri=row['uri'],
            liClass='inferred' if setting=='inferred' else '',
            checked='checked="checked"' if setting else '',
            disabled='disabled="disabled"' if setting == 'inferred' else '',
            checkId="id-%s" % (random.randint(0,9999999)),
            authorizations=describeAuthorizations(graph, row['uri'], subject),
            ))

    # i think the correct thing to list would be *previous perm
    # settings that enabled access to these photos* so it's clear what
    # you're removing even when it's not an exact match to the photo
    # set. If the perm setting corresponds exactly to a perm you could
    # give (e.g. it was one you just applied), then use the normal
    # checkbox list. For anything else, split them out and make the
    # action be 'remove perm'
    ret = dict(
        desc=groupDesc,
        about=subject,
        agents=agents,
        )
    return ret

def describeAuthorizations(graph, forAgent, accessTo):
    ret = []
    for auth in authorizations(graph, forAgent, accessTo):
        rows = graph.queryd("""SELECT DISTINCT ?creator ?created WHERE {
                                 OPTIONAL { ?auth dcterms:creator ?creator }
                                 OPTIONAL { ?auth dcterms:created ?created }
                               }""", initBindings={'auth' : auth})
        if not rows:
            rows = [{}]
        ret.append(dict(auth=auth,
                        creator=rows[0].get('creator'),
                        created=rows[0].get('created')))
    return ret

def addAccess(graph, user, agent, accessTo):
    if not agentMaySetAccessControl(user):
        raise ValueError("user is not allowed to set access controls")

    # i'm trying to resist setting access for dates, since they're not
    # a good grouping in the first place and also because seeing one
    # date lets you see a span of them, currently
    assert isinstance(accessTo, URIRef)
    
    auth = URIRef("http://photo.bigasterisk.com/access/%f" % time.time())
    stmts = [(auth, RDF.type, ACL.Authorization),
             (auth, ACL.mode, ACL.Read),

             # the spec wants me to use accessToClass and agentClass when
             # those things are classes, but that seems annoying
             (auth, ACL.accessTo, accessTo),
             (auth, ACL.agent, agent),
        
             (auth, DCTERMS.creator, user),
             (auth, DCTERMS.created, Literal(datetime.datetime.now(tzlocal())))]

    subgraph = URIRef('http://photo.bigasterisk.com/update/%f' % time.time())
    graph.add(stmts, context=subgraph)
    log.info("wrote new auth %s to subgraph %s" % (auth, subgraph))

def legacyRemove(graph, agent, accessTo):
    if graph.queryd("ASK { ?photo pho:viewableBy ?agent . }",
                    initBindings={'photo' : accessTo, 'agent' : agent}):
        stmt = (accessTo, PHO.viewableBy, agent)
        log.info("removing %s", stmt)
        graph.remove([stmt])
        return True
    return False    

def authorizations(graph, forAgent, accessTo):
    return [row['auth'] for row in graph.queryd("""
      SELECT ?auth WHERE {
        ?auth acl:mode acl:Read ;
          acl:accessTo ?photo ;
          acl:agent ?agent .
      }""", initBindings={'photo' : accessTo, 'agent' : forAgent})]
    
def removeAccess(graph, user, agent, accessTo):
    if not agentMaySetAccessControl(user):
        raise ValueError("user is not allowed to set access controls")

    if legacyRemove(graph, agent, accessTo):
        return

    auths = authorizations(graph, agent, accessTo)

    for auth in auths:
        stmt = (auth, None, None)
        log.info("removing %s", stmt)
        graph.remove([stmt])

    if not auths:
        raise ValueError("didn't find any access to %s for %s" %
                         (accessTo, agent))


# older
def isPublic(graph, uri):
    return viewable(graph, uri, FOAF.Agent)

def makePublic(uri):
    return makePublics([uri])

def makePublics(uris):
    writeStatements([
        (uri, PHO.viewableBy, PHO.friends) for uri in uris
        ])
    
