from rdflib import URIRef
from nevow import inevow

def getUser(ctx):
    agent = inevow.IRequest(ctx).getHeader('x-foaf-agent')
    if agent is None:
        return None
    return URIRef(agent)
