from rdflib import Namespace, URIRef
PHO = Namespace("http://photo.bigasterisk.com/0.1/")

def isPublic(graph, uri):
    return graph.contains((uri, PHO.viewableBy, PHO.friends))

def makePublic(uri):
    uri = URIRef(i['uri'])
    writeStatements([
        (uri, PHO.viewableBy, PHO.friends)
        ])
