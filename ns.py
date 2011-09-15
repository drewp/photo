from rdflib import Namespace, RDFS, RDF

ACL = Namespace("http://www.w3.org/ns/auth/acl#")
DC = Namespace("http://purl.org/dc/elements/1.1/")
DCTERMS = Namespace("http://purl.org/dc/terms/")
EXIF = Namespace("http://www.kanzaki.com/ns/exif#")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")
PHO = Namespace("http://photo.bigasterisk.com/0.1/")
SCOT = Namespace("http://scot-project.org/scot/ns#")
SIOC = Namespace("http://rdfs.org/sioc/ns#")
SITE = Namespace("http://photo.bigasterisk.com/")
WGS = Namespace("http://www.w3.org/2003/01/geo/wgs84_pos#")
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
