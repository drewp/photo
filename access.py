import logging
from rdflib import URIRef, Namespace
from nevow import inevow
import auth
PHO = Namespace("http://photo.bigasterisk.com/0.1/")

log = logging.getLogger()

def getUser(ctx):
    agent = inevow.IRequest(ctx).getHeader('x-foaf-agent')
    if agent is None:
        return None
    return URIRef(agent)

def viewable(graph, uri, agent):
    """
    should the resource at uri be retrievable by this agent
    """
    log.debug("viewable check for %s to see %s", agent, uri)

    # not final; just matching the old logic
    if agent in auth.superagents:
        log.debug("ok, agent %r is in superagents", agent)
        return True

    # somehow allow local clients who could get to the filesystem
    # anyway. maybe with a cookie file in the fs, or just ip
    # screening



    if (graph.contains((uri, PHO['viewableBy'], PHO['friends']))
        or graph.contains((uri, PHO['viewableBy'], PHO['anyone']))):
        log.debug("ok, graph says :viewableBy :friends or :anyone")
        return True

    if graph.queryd("""
        SELECT ?post WHERE {
          <http://bigasterisk.com/ari/> sioc:container_of ?post .
          ?post sioc:links_to ?uri .
        }""", initBindings={'uri' : uri}): # should just be ASK
        # this should also be limiting to readers of the blog!
        log.debug("ok because it's on the blog")
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

    log.debug("not viewable")
    return False
