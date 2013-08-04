
import os
from rdflib import URIRef
from nevow import inevow

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
