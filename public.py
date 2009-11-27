from rdflib import Namespace, URIRef
from edit import writeStatements

PHO = Namespace("http://photo.bigasterisk.com/0.1/")

def isPublic(graph, uri):
    return graph.contains((uri, PHO.viewableBy, PHO.friends))

def makePublic(uri):
    writeStatements([
        (uri, PHO.viewableBy, PHO.friends)
        ])
