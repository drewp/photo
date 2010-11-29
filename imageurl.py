import logging, datetime
from rdflib import URIRef, Literal, Namespace, RDF
from nevow import url
import tagging
from search import randomSet
from oneimagequery import photoCreated

SITE = Namespace("http://photo.bigasterisk.com/")
PHO = Namespace("http://photo.bigasterisk.com/0.1/")
XS = Namespace("http://www.w3.org/2001/XMLSchema#")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")

log = logging.getLogger()


class ImageSetDesc(object): # in design phase
    paramsAffectingSet = ['dir', 'tag', 'date', 'star']
    def __init__(self, graph, user, uriOrQuery):
        """
        uriOrQuery is like /set?tag=foo&star=only
        """

        self.parsedUrl = url.URL.fromString(uriOrQuery)
        params = dict(self.parsedUrl.queryList())

        completeUri = SITE[self.parsedUrl.path]
        if graph.queryd("ASK { ?img foaf:depicts ?uri }",
                         initBindings={'uri' : completeUri}):
            topic = completeUri
        else:  
            if 'dir' in params:
                topic = URIRef(params['dir'])
            elif 'tag' in params:
                topic = URIRef('http://photo.bigasterisk.com/tag/%s' % params['tag'])
            elif 'date' in params:
                topic = Literal(params['date'], datatype=XS.date)
            elif 'random' in params:
                topic = PHO.randomSet
            elif 'current' in params:
                # order is important, since 'current' could appear with other params
                topic = URIRef(params['current'])
            else:
                raise ValueError("no topic; %r" % uriOrQuery)
        
        if topic == PHO.randomSet:
            self._photos = [r['pic'] for r in
                            randomSet(graph, int(params.get('random', '10')),
                                      user,
                                      seed=int(params['seed'])
                                        if 'seed' in params else None)]
            self.setLabel = 'random choices'
        else:
            self._photos = photosWithTopic(graph, topic)
        self._currentPhoto = None
        if params.get('current') is not None:
            self._currentPhoto = URIRef(params['current'])          

        if not self._photos and self._currentPhoto:
            log.info("featuring one pic")
            self._photos = [self._currentPhoto]

        starFilter(graph, params.get('star'), user, self._photos)

        if self._currentPhoto not in self._photos:
            if len(self._photos) == 0:
                self._currentPhoto = None
            else:
                self._currentPhoto = self._photos[0]


        if graph.contains((topic, RDF.type, PHO.DiskDirectory)):
            self.setLabel = ["directory ", graph.value(topic, PHO.filename)]
        elif isinstance(topic, Literal):
            self.setLabel = topic
        else:
            self.setLabel = graph.label(topic)

        self.topic = topic
    
    def canonicalSetUri(self):
        """this page uri, but only including the params that affect
        what pics are shown, and in a stable order. This is suitable
        for using on authorization rules"""
        ret = self.parsedUrl.fromString(SITE[str(self.parsedUrl).lstrip('/')])
        ret = ret.clear()
        for k,v in sorted(self.parsedUrl.queryList()): # isn't this a problem when new params are added?
            if k in ['random']:
                raise ValueError("canonical set uri is undefined for random sets")
            if k in self.paramsAffectingSet:
                ret = ret.add(k, v)
        return URIRef(str(ret))

    def altUrl(self, star=None):
        """relative url with the requested change

        star='only' or 'all'
        """
        ret = self.parsedUrl
        if star is not None:
            if star == 'all':
                ret = ret.remove('star')
            elif star == 'only':
                ret = ret.replace('star', 'only')
            else:
                raise NotImplementedError

        return str(ret)

    def photos(self):
        """
        all the photos this query resolves to
        """
        return self._photos

    def currentPhoto(self):
        """
        a single photo from this set, can be selected by the URI
        """
        return self._currentPhoto

    def includesPhoto(self, uri):
        return uri in self._photos
    
    def label(self):
        """
        Something that could fit in the phrase 'Pictures of _______'
        e.g. 'DSC_9993.JPG', 'sometagname', '2005-11-12', 'the foo
        directory', 'random choices'.
        """
        return self.setLabel
    
    def storyModeUrl(self):
        """this set in story mode"""
        raise NotImplementedError

    def relatedSetLinks(self):
        """all the related ImageSetDescs, e.g. ones with the same tag, etc"""
        raise NotImplementedError

    def sampleImages(self):
        """i had a plan that when we're talking about another image
        set, we could include a few tiny thumbnails and a count to let
        you know what that other set has"""
        raise NotImplementedError

    # methods to make alternate urls of this set with some other params applied

def starFilter(graph, starArg, agent, photos):
    """culls from your list"""
    if starArg is None:
        pass
    elif starArg == 'only':
        keep = []
        for p in photos:
            if tagging.hasTag(graph, agent, p, SITE['tag/*']):
                keep.append(p)
        photos[:] = keep
    elif starArg == 'all':
        pass
    else:
        raise NotImplementedError("star == %r" % starArg)


def photosWithTopic(graph, uri):
    """photos can be related to uri in a variety of ways: foaf:depicts,
    dc:date, etc"""
    q = graph.queryd("""SELECT DISTINCT ?photo WHERE {
                               {
                                 ?photo foaf:depicts ?u .
                               } UNION {
                                 ?photo pho:inDirectory ?u .
                               } UNION {
                                 ?photo scot:hasTag ?u .
                               } UNION {
                                 ?photo dc:date ?u .
                               } UNION {
                                 ?email a pho:Email ; dc:date ?u ; dcterms:hasPart ?photo .
                               }
                              # ?photo pho:viewableBy pho:friends .
                             }""",
                          initBindings={'u' : uri})

    def sortkey(uri):
        try:
            return photoCreated(graph, uri)
        except ValueError:
            return datetime.datetime(1,1,1)

    return sorted([row['photo'] for row in q], key=sortkey)
