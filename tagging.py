"""
tags and descriptions (but not comments; those are in another
service. Maybe tag+desc will go there too someday)
"""

import time, logging
from xml.utils import iso8601
from rdflib import URIRef, Literal, RDFS, Namespace, Variable
log = logging.getLogger()
DCTERMS = Namespace("http://purl.org/dc/terms/")
PHO = Namespace("http://photo.bigasterisk.com/0.1/")

def saveTags(graph, foafUser, img, tagString, desc):
    subgraph = URIRef('http://photo.bigasterisk.com/update/%f' %
                      time.time())
    stmts = set([
        (subgraph, DCTERMS.creator, foafUser),
        (subgraph, DCTERMS.created,
         Literal(iso8601.tostring(time.time(), timezone=time.altzone))),
        (img, PHO.tagString, Literal(tagString)),
        (img, RDFS.comment, Literal(desc)),
        ])
    tagDefs = set()
    for w in tagString.split():
        tag = URIRef('http://photo.bigasterisk.com/tag/%s' % w)
        stmts.add((img, PHO.tag, tag))
        tagDefs.add((tag, RDFS.label, Literal(w)))

    prevContexts = [row['g'] for row in graph.queryd(
        "SELECT ?g WHERE { GRAPH ?g { ?img pho:tagString ?any } }",
        initBindings={Variable("img") : img})]
        
    graph.add(*stmts, **{'context' : subgraph})
    log.info("Wrote tag data to %s" % subgraph)
    graph.add(*tagDefs, **{'context' :
                           URIRef('http://photo.bigasterisk.com/tagDefs')})

    for c in prevContexts:
        graph.remove((None, None, None), context=c)

def getTags(graph, img):
    return dict(
        tags=graph.value(img, PHO.tagString, default=''),
        desc=graph.value(img, RDFS.comment, default=''),
        )
