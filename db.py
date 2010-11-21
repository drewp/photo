import sys
sys.path.append("/my/proj/sparqlhttp")
from sparqlhttp.graph2 import SyncGraph

import networking
from rdflib import Namespace, RDFS

PHO = Namespace("http://photo.bigasterisk.com/0.1/")
SITE = Namespace("http://photo.bigasterisk.com/")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")
SIOC = Namespace("http://rdfs.org/sioc/ns#")
DC = Namespace("http://purl.org/dc/elements/1.1/")
DCTERMS = Namespace("http://purl.org/dc/terms/")
SCOT = Namespace("http://scot-project.org/scot/ns#")
XS = Namespace("http://www.w3.org/2001/XMLSchema#")

initNs = dict(
    foaf=FOAF,
    rdfs=RDFS.RDFSNS,
    sioc=SIOC,
    pho=PHO,
    scot=SCOT,
    dc=DC,
    dcterms=DCTERMS,
    exif=Namespace("http://www.kanzaki.com/ns/exif#"),
    acl=Namespace("http://www.w3.org/ns/auth/acl#"),
    )

def getGraph():
    return SyncGraph('sesame', networking.graphRepoRoot()+'/photo', initNs=initNs)
