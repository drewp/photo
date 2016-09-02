import logging, datetime
from rdflib import URIRef, Literal, RDF
from nevow import url
import tagging
from search import randomSet
from oneimagequery import photoCreated
from lib import print_timing
from ns import SITE, PHO, XS
from dateutil.parser import parse
from dateutil.tz import tzlocal
from alternates import findCompleteAltTree
import pylru

log = logging.getLogger()

class NoSetUri(ValueError):
    "there is no stable URI that can represent this set"

# these could go wrong whenever there's an edit!
_imageSetDescCache = pylru.lrucache(500)

class ImageSetDesc(object): # in design phase
    @print_timing
    def __init__(self, graph, user, uriOrQuery):
        """
        uriOrQuery is like /set?tag=foo&star=only
        """
        self.graph = graph
        
        if '?' not in uriOrQuery:
            # sometimes a single image uri comes in, and it wasn't getting handled right
            uriOrQuery = str(url.URL().add('current', uriOrQuery))
            
        # shouldn't these removes be handled by paramsAffectingSet or something?
        self.parsedUrl = url.URL.fromString(uriOrQuery).remove('jsonUpdate').remove('setList')
        params = dict(self.parsedUrl.queryList())
        self._isVideo = {}

        topicDict = self.determineTopic(graph, params)
        
        if topicDict['topic'] == PHO.randomSet:
            self._photos = [r['pic'] for r in
                            randomSet(graph, int(params.get('random', '10')),
                                      user,
                                      year=params.get('year', None),
                                      tags=params.get('tags', 'without'),
                                      seed=int(params['seed'])
                                        if 'seed' in params else None)]
            self.setLabel = 'random choices'
            if params.get('year'):
                self.setLabel += " from the year %s" % params['year']
        elif topicDict.get('alternates', False):
            self._photos = findCompleteAltTree(graph, topicDict['topic'])
        else:
            self._photos = photosWithTopic(graph, topicDict, self._isVideo)
        self._currentPhoto = None
        if params.get('current') is not None:
            self._currentPhoto = URIRef(params['current'])          

        if not self._photos and self._currentPhoto:
            log.info("featuring one pic")
            self._photos = [self._currentPhoto]

        self._photos = starFilter(graph, params.get('star'), user, self._photos)
        if params.get('recent', '').strip():
            # recent=10 shows the last 10
            self._photos = self._photos[-int(params['recent'].strip()):]

        if self._currentPhoto not in self._photos:
            if len(self._photos) == 0:
                self._currentPhoto = None
            else:
                self._currentPhoto = self._photos[0]

        self.topicDict = topicDict

    def determineTopic(self, graph, params):
        key = (self.parsedUrl.path, tuple(sorted(params.items())))
        if key in _imageSetDescCache:
            return _imageSetDescCache[key]
        topicDict = {}
        completeUri = SITE[self.parsedUrl.path]
        if graph.queryd("ASK { ?img a foaf:Image }",
                          initBindings={'img' : completeUri}):
            topic = completeUri
        elif graph.queryd("ASK { ?img foaf:depicts ?uri }",
                         initBindings={'uri' : completeUri}):
            topic = completeUri
        else:
            log.debug("topic from params: %r", params)
            if 'dir' in params:
                topic = URIRef(params['dir'])
            elif 'tag' in params:
                topic = URIRef('http://photo.bigasterisk.com/tag/%s' % params['tag'])
            elif 'date' in params:
                if 'span' in params:
                    # 31d is wrong; you should just pass a date like yyyy-mm
                    if params['span'] in ['7d', '31d']:
                        topicDict['span'] = params['span']
                    else:
                        raise NotImplementedError
                topic = Literal(params['date'], datatype=XS.date)
                
            elif 'random' in params:
                topic = PHO.randomSet
            elif 'alt' in params:
                topic = URIRef(params['alt'])
                topicDict['alternates'] = True
            elif 'current' in params:
                # order is important, since 'current' could appear with other params
                topic = URIRef(params['current'])
            else:
                raise ValueError("no topic; %r" % params)
        topicDict['topic'] = topic
        _imageSetDescCache[key] = topicDict
        return topicDict

    def determineLabel(self, graph, topicDict):
        topic = topicDict['topic']
        if graph.contains((topic, RDF.type, PHO.DiskDirectory)):
            return ["directory ", graph.value(topic, PHO.filename)]
        elif isinstance(topic, Literal):
            if 'span' in topicDict:
                topic = "%s and the next %s" % (topic, topicDict['span'])
            return topic
        elif topicDict.get('alternates', False):
            return "alternates of %s" % graph.label(topic, default=topic)
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
        return ['dir', 'tag', 'date', 'span', 'star', 'recent', 'alt']
    
    def canonicalSetUri(self):
        """this page uri, but only including the params that affect
        what pics are shown, and in a stable order. This is suitable
        for using on authorization rules"""
        ret = self.parsedUrl.fromString(SITE[str(self.parsedUrl).lstrip('/')])
        ret = ret.clear()

        params = sorted(self.parsedUrl.queryList())
        keys = [k for k,v in params]
        if 'random' in keys:
            raise NoSetUri()
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
        return str(self.parsedUrl.replace('current', img))

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

    def isVideo(self, uri):
        if uri not in self._isVideo:
            self._isVideo[uri] = self.graph.contains((uri, RDF.type, PHO.Video))
        return self._isVideo[uri]
    
    def label(self):
        """
        Something that could fit in the phrase 'Pictures of _______'
        e.g. 'DSC_9993.JPG', 'sometagname', '2005-11-12', 'the foo
        directory', 'random choices'.
        """
        if not hasattr(self, 'setLabel'):
            self.setLabel = self.determineLabel(self.graph, self.topicDict)
        return self.setLabel
    
    def storyModeUrl(self):
        """this set in story mode"""
        return self.canonicalSetUri() + "&story=1" # todo

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
    """agent is needed (someday) to look up star tags"""
    if starArg is None or starArg == 'all':
        return photos
    elif starArg == 'only':
        keep = []
        for p in photos:
            if tagging.hasTag(graph, agent, p, SITE['tag/*']):
                keep.append(p)
        return keep
    else:
        raise NotImplementedError("star == %r" % starArg)

# could easily be wrong after edits
_photosWithTopic = pylru.lrucache(2)

def photosWithTopic(graph, topicDict, isVideo):
    """photos can be related to uri in a variety of ways: foaf:depicts,
    dc:date, etc

    we fill isVideo with uri:bool where we learn if the photo was a video
    """
    uri = topicDict['topic']
    q = queryOneTopic(graph, uri)

    if topicDict.get('span') in ['7d', '31d']:
        for otherDay in daysInSpan(topicDict['topic'], topicDict['span']):
            q.extend(queryOneTopic(graph, otherDay))
    
    def sortkey(uri):
        try:
            return photoCreated(graph, uri)
        except ValueError:
            return datetime.datetime(1,1,1, tzinfo=tzlocal())
    for row in q:
        isVideo[row['photo']] = bool(row['isVideo'])

    return sorted([row['photo'] for row in q], key=sortkey)

def daysInSpan(day, span):
    dd = int(span.replace('d',''))
    d = parse(day)
    for i in range(dd):
        d = d + datetime.timedelta(days=1)
        yield Literal(d.date().isoformat(), datatype=XS['date'])

def queryOneTopic(graph, uri):
    if uri in _photosWithTopic:
        return _photosWithTopic[uri]
        
    ret = graph.queryd("""SELECT DISTINCT ?photo ?isVideo WHERE {
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
                           OPTIONAL {
                             ?photo a ?isVideo .
                             FILTER( ?isVideo = pho:Video ) .
                           }
                         }""",
                      initBindings={'u' : uri})
    _photosWithTopic[uri] = ret
    return ret
