from rdflib import Namespace
from edit import writeStatements

PHO = Namespace("http://photo.bigasterisk.com/0.1/")

def isPublic(graph, uri):
    return graph.contains((uri, PHO.viewableBy, PHO.friends))

def allPublic(graph, uris):
    return all(isPublic(graph, pic) for pic in uris)

def makePublic(uri):
    return makePublics([uri])

def makePublics(uris):
    writeStatements([
        (uri, PHO.viewableBy, PHO.friends) for uri in uris
        ])
    
