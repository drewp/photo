import logging, datetime
from rdflib import URIRef, Literal, RDF
from nevow import url
import tagging
from search import randomSet
from oneimagequery import photoCreated
from lib import print_timing
from ns import SITE, PHO, XS

log = logging.getLogger()


class ImageSetDesc(object): # in design phase
    def __init__(self, graph, user, uriOrQuery):
        """
        uriOrQuery is like /set?tag=foo&star=only
        """
        self.graph = graph
        self.parsedUrl = url.URL.fromString(uriOrQuery)
        params = dict(self.parsedUrl.queryList())

        topic = self.determineTopic(graph, params)
        
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
        if params.get('recent', '').strip():
            # recent=10 shows the last 10
            self._photos = self._photos[-int(params['recent'].strip()):]

        if self._currentPhoto not in self._photos:
            if len(self._photos) == 0:
                self._currentPhoto = None
            else:
                self._currentPhoto = self._photos[0]

        self.topic = topic

    @print_timing
    def determineTopic(self, graph, params):
        completeUri = SITE[self.parsedUrl.path]
        if graph.queryd("ASK { ?img foaf:depicts ?uri }",
                         initBindings={'uri' : completeUri}):
            topic = completeUri
        elif graph.queryd("ASK { ?img a foaf:Image }",
                          initBindings={'img' : completeUri}):
            topic = completeUri
        else:
            log.debug("topic from params: %r", params)
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
                raise ValueError("no topic; %r" % params)
        return topic

    def determineLabel(self, graph, topic):
        if graph.contains((topic, RDF.type, PHO.DiskDirectory)):
            return ["directory ", graph.value(topic, PHO.filename)]
        elif isinstance(topic, Literal):
            return topic
        else:
            return graph.label(topic)

    def paramsAffectingSet(self, params):
        """
        only some params affect what images are in the set (as opposed
        to other viewing mode stuff), but this set of params is
        tricky. E.g. if all you have is 'current', then current
        affects the set. Normally it doesn't.
        """
        if not any(t in params for t in ['dir', 'tag', 'date', 'random']):
            return 'current'
        return ['dir', 'tag', 'date', 'star', 'recent']
    
    def canonicalSetUri(self):
        """this page uri, but only including the params that affect
        what pics are shown, and in a stable order. This is suitable
        for using on authorization rules"""
        ret = self.parsedUrl.fromString(SITE[str(self.parsedUrl).lstrip('/')])
        ret = ret.clear()

        params = sorted(self.parsedUrl.queryList())
        keys = [k for k,v in params]
        if 'random' in keys:
            raise ValueError("canonical set uri is undefined for random sets")
        importantParams = self.paramsAffectingSet(keys)
        
        for k,v in params:
            if k not in importantParams:
                continue
            if (k,v) == ('star', 'all'): # generalize to all default vals?
                continue
            if v.strip():
                ret = ret.add(k, v)
        return URIRef(str(ret))

    def altUrl(self, star=None, recent=None):
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

        if recent is not None:
            ret = ret.replace('recent', recent)
            
        return str(ret)

    def otherImageUrl(self, img):
        """
        url with this other image as the current one
        """
        return self.parsedUrl.replace('current', img)

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
        if not hasattr(self, 'setLabel'):
            self.setLabel = self.determineLabel(self.graph, self.topic)
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
    if starArg is None or starArg == 'all':
        pass
    elif starArg == 'only':
        keep = []
        for p in photos:
            if tagging.hasTag(graph, agent, p, SITE['tag/*']):
                keep.append(p)
        photos[:] = keep
    else:
        raise NotImplementedError("star == %r" % starArg)

@print_timing
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
