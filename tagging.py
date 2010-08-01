"""
tags and descriptions (but not comments; those are in another
service. Maybe tag+desc will go there too someday)
"""

import time, logging
from xml.utils import iso8601
from rdflib import URIRef, Literal, RDFS, Namespace, Variable, RDF
log = logging.getLogger()
DCTERMS = Namespace("http://purl.org/dc/terms/")
PHO = Namespace("http://photo.bigasterisk.com/0.1/")
SCOT = Namespace("http://scot-project.org/scot/ns#")

_twf = None

def allowedToWrite(graph, foafUser):
    return foafUser in [
        URIRef("http://bigasterisk.com/foaf.rdf#drewp"),
        URIRef("http://bigasterisk.com/kelsi/foaf.rdf#kelsi"),
        ]

def saveTags(graph, foafUser, img, tagString, desc):
    global _twf
    if not allowedToWrite(graph, foafUser):
        raise ValueError("not allowed")
    _twf = None 
    
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
        # need to trim bad url chars and whatever else we're not going to allow
        tag = URIRef('http://photo.bigasterisk.com/tag/%s' % w)
        stmts.add((img, SCOT.hasTag, tag))
        tagDefs.add((tag, RDFS.label, Literal(w)))
        tagDefs.add((tag, RDF.type, SCOT.Tag))
        tagDefs.add((tag, SCOT.usedBy, foafUser)) # derivable from the subgraph

    prevContexts = [row['g'] for row in graph.queryd(
        "SELECT ?g WHERE { GRAPH ?g { ?img pho:tagString ?any } }",
        initBindings={Variable("img") : img})]
        
    graph.add(*stmts, **{'context' : subgraph})
    log.info("Wrote tag data to %s" % subgraph)
    graph.add(*tagDefs, **{'context' :
                           URIRef('http://photo.bigasterisk.com/tagDefs')})

    for c in prevContexts:
        graph.remove((None, None, None), context=c)

def getTags(graph, foafUser, img):

    # check user read perms

    return dict(
        tagString=graph.value(img, PHO.tagString, default=''),
        tags=[r['tag'] for r in graph.queryd(
            "SELECT ?tag WHERE { ?img scot:hasTag [ rdfs:label ?tag ] }",
            initBindings={Variable("img") : img})],
        desc=graph.value(img, RDFS.comment, default=''),
        )

_hasTags = set() # assume tags get added over time but not removed, so
                 # i don't store the negatives
def hasTags(graph, foafUser, img):
    # user security check goes here
    if img in _hasTags:
        return True
    ret = graph.value(img, PHO.tagString, default='').strip() != ''
    if ret:
        _hasTags.add(img)
    return ret


def getTagsWithFreqs(graph):
    # slow- 200+ ms
    global _twf
    if _twf is not None:
        return _twf
    freq = {}
    for row in graph.queryd("SELECT ?tag WHERE { ?pic scot:hasTag [ rdfs:label ?tag ] }"):
        freq[row['tag']] = freq.get(row['tag'], 0) + 1
    _twf = freq
    return freq
