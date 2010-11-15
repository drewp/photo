"""
implementation of http://esw.w3.org/WebAccessControl

currently this is contaminated with my old 'viewableBy' access system
and some other photo-site-specific things, but hopefully those can be
removed
"""

import logging, random, urllib, time, datetime
from dateutil.tz import tzlocal
from rdflib import URIRef, Namespace, RDF, Literal
import restkit
from nevow import inevow
import auth
from genshi.template import TemplateLoader
from genshi.output import XHTMLSerializer
from edit import writeStatements
PHO = Namespace("http://photo.bigasterisk.com/0.1/")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")
ACL = Namespace("http://www.w3.org/ns/auth/acl#")
DC = Namespace("http://purl.org/dc/terms/")
loader = TemplateLoader(".", auto_reload=True)
serializer = XHTMLSerializer()
log = logging.getLogger()

def getUser(ctx):
    agent = inevow.IRequest(ctx).getHeader('x-foaf-agent')
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

    if agent and graph.queryd("""
        SELECT ?cls WHERE {
           ?uri pho:viewableBy ?cls .
           ?agent a ?cls .
        }
        """, initBindings={'uri' : uri, 'agent' : agent}):
        log.debug("ok because the user is in a class who may view the photo")
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

def viewableViaInference(graph, uri, agent):
    """
    viewable for some reason that can't be removed here
    """

    # not final; just matching the old logic
    if agent in auth.superagents:
        log.debug("ok, agent %r is in superagents", agent)
        return True

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

def viewable(graph, uri, agent):
    """
    should the resource at uri be retrievable by this agent
    """
    log.debug("viewable check for %s to see %s", agent, uri)
    ok = (viewableViaPerm(graph, uri, agent) or
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
def expandPhotos(graph, subject):
    """
    returns the set of images that this subject refers to, plus a
    short description of the set

    subject can be a photo itself, some search query, a topic, etc
    """
    if graph.value(subject, RDF.type) == FOAF.Image:
        return [subject], "this photo"

    if 0: # from old version
        # security- make sure this is not making some bad request
        setJs = getPage('http://localhost:8086/'+ctx.arg('allInSet').lstrip('/'),
                              headers={'Accept' : 'application/json'})
        uris = jsonlib.read(setJs)['photos']
        print "setting", uris

    if subject == URIRef("http://example.com/wholeset"):
        return [subject], "these 51 photos"

    raise NotImplementedError("expandPhotos on %r" % subject)

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
    """
    if not agentMaySetAccessControl(agent):
        return ""

    photos, groupDesc = expandPhotos(graph, subject)

    tmpl = loader.load("aclwidget.html")

    agents = [(row['label'],
               all(agentClassCheck(graph, row['uri'], p) for p in photos),
               row['uri'])
              for row in interestingAclAgentsAndClasses(graph)]

    # i think the correct thing to list would be *previous perm
    # settings that enabled access to these photos* so it's clear what
    # you're removing even when it's not an exact match to the photo
    # set. If the perm setting corresponds exactly to a perm you could
    # give (e.g. it was one you just applied), then use the normal
    # checkbox list. For anything else, split them out and make the
    # action be 'remove perm'

    stream = tmpl.generate(
        desc=groupDesc,
        about=subject,
        agents=agents,
        randomId=lambda: "id-%s" % (random.randint(0,9999999)),
        )
    return (''.join(serializer(stream))).encode('utf8')

def addAccess(graph, user, agent, accessTo):
    if not agentMaySetAccessControl(user):
        raise ValueError("user is not allowed to set access controls")
    
    auth = URIRef("http://photo.bigasterisk.com/access/%f" % time.time())
    stmts = [(auth, RDF.type, ACL.Authorization),
             (auth, ACL.mode, ACL.Read),

             # the spec wants me to use accessToClass and agentClass when
             # those things are classes, but that seems annoying
             (auth, ACL.accessTo, accessTo),
             (auth, ACL.agent, agent),
        
             (auth, DC.creator, user),
             (auth, DC.created, Literal(datetime.datetime.now(tzlocal())))]

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
    
def removeAccess(graph, user, agent, accessTo):
    if not agentMaySetAccessControl(user):
        raise ValueError("user is not allowed to set access controls")

    if legacyRemove(graph, agent, accessTo):
        return

    auths = [row['auth'] for row in graph.queryd("""
      SELECT ?auth WHERE {
        ?auth acl:mode acl:Read ;
          acl:accessTo ?photo ;
          acl:agent ?agent .
      }""", initBindings={'photo' : accessTo, 'agent' : agent})]

    for auth in auths:
        stmt = (auth, None, None)
        log.info("removing %s", stmt)
        graph.remove([stmt])

    if not auths:
        raise ValueError("didn't find any access to %s for %s" %
                         (accessTo, agent))


# older
def isPublic(graph, uri):
    return graph.contains((uri, PHO.viewableBy, PHO.friends))

def makePublic(uri):
    return makePublics([uri])

def makePublics(uris):
    writeStatements([
        (uri, PHO.viewableBy, PHO.friends) for uri in uris
        ])
    
