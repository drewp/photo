#!../../bin/python
"""
main search/filter/pager that takes query params for describing a
set of images and returns json descriptions of them

query language in json:
{
  filter:
    (all non-null filters must be true for each image)
    (images you don't have access to are not visible)
    tags: [<strings, including '*'>] # must include these
    withoutTags: ['nsfw']  # must not include these
    onlyTagged: <list of tags that pics must have a subset of>
    type: 'video'|'image'
    dir: uri
    time: <yyyy-mm-dd>
      or  <yyyy-mm-dd>-<yyyy-mm-dd>
      or  put times on any of those values
    readableBy: <user or group>
    
  attrs:
    uri: true
    time: true
    acl: false # tbd
    tags: false
    
  sort:
    (default is [{time: 'asc'}])
    list can also have
     {uri: 'asc'}
     {random: <seed>} # seed is stable if the 
    multiple sorts are rare, but maybe something like tag-then-date will come up

  page:
    limit: <n>
    after: <uri>|None
      (or)
    skip: <count>
    TBD: pageWith: <uri>, to get items near this current one and then
      report back where the scroll position should be
}

query language in url params:
    tag= (repeat)
    hidden=none (remove default withoutTags)
    withoutTag= (repeat)
    onlyTagged= (empty means pics with no tags, =foo =bar means pics with
      a subset of [foo,bar] but no more)
    type=
    attrs=uri,time,acl
    sort=time
    sort=-time
    sort=random+3525
    limit=
    after=
    skip=
some of this is merged with the current-image selection stuff. the paging params probably wouldn't appear

results:
{
  images: [
    {uri, type:video, ...}
  ],
  # tbd: how many excluded?
  paging:
    limit: <your limit>
    count: <len(images)>
    total: <n>
}
"""
import logging
from klein import run, route
from twisted.internet import reactor
import sys, json, itertools, random, time, sha, collections
from rdflib import URIRef
import concurrent.futures
from dateutil.parser import parse
import dateutil.tz
sys.path.append("../..")

from db import getGraph
from requestprofile import timed
from oneimagequery import photoCreated
from queryparams import queryFromParams
from mediaresource import MediaResource
from tagging import getTags
import networking

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()

class ImageIndex(object):
    """
    holds various indices in memory. reads all pics from the graph
    once, but then needs update(uri) called on any further changes.
    """
    def __init__(self, graph):
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=128)
        self.graph = graph

        # managed by update()
        self.byUri = {}

        # managed by updateSorts()
        self.byTime = []
        self.shuffled = []
        
        self._toRead = self._allImages()
        self._continueIndexing()
        
    def _allImages(self):
        log.info("finding all images")
        t1 = time.time()
        uris = set()
        for row in self.graph.query(
                "SELECT DISTINCT ?uri WHERE { ?uri a foaf:Image . }"):
            uris.add(row['uri'])
        log.info("found %s images in %s sec", len(uris), time.time() - t1)
        return uris

    def finishBackgroundIndexing(self):
        while self._toRead:
            self.update(self._toRead.pop())
        self.updateFinalSorts()
        
    def _continueIndexing(self, docsAtOnce=256, maxTimePerCall=1):
        t1 = time.time()

        while True:
            if not self._toRead:
                break

            uris = set()
            for n in range(docsAtOnce):
                if self._toRead:
                    uris.add(self._toRead.pop())

            docs = []
            if True:
                # parallel
                docs = sum(self.pool.map(self.gatherDocs, uris), [])
            else:
                # serial
                for uri in uris:
                    docs.extend(self.gatherDocs(uri))

            for doc in docs:
                self.addToIndices(doc)

            if time.time() - t1 > maxTimePerCall:
                break

        if not self._toRead:
            log.info("background indexing is done")
            self.updateFinalSorts()
            return
        self.updateSorts()
        log.info("%s left to index", len(self._toRead))
        reactor.callLater(.01, self._continueIndexing)

    def updateSorts(self):
        now = time.time()
        if now > getattr(self, '_lastSort', 0) + 30:
            self._lastSort = now
            self.byTime = self.byUri.values()
            self.byTime.sort(key=lambda d: (bool(d['t']), d['t'] or d['uri']))

            if len(self.shuffled) < 1000:
                self.updateShuffle()
        
    def updateFinalSorts(self):
        self.updateSorts()
        self.updateShuffle()

    def updateShuffle(self):
        self.shuffled = self.byTime[:]
        r = random.Random(987)
        r.shuffle(self.shuffled)
        
    def gatherDocs(self, uri):
        # check image first- maybe it was deleted
        try:
            t = photoCreated(self.graph, uri)
        except ValueError:
            t = None

        m = MediaResource(self.graph, uri)
        
            
        viewableBy = []

        return [{
            'uri': uri,
            't': t,
            'isVideo': m.isVideo(),
            'tags': set(str(lit) for lit in getTags(self.graph, 'todo', uri)['tags'])
            }]

    def addToIndices(self, doc):
        self.byUri[doc['uri']] = doc

    def update(self, uri):
        docs = self.gatherDocs(uri)
        for doc in docs:
            self.addToIndices(doc)

    # we'll need a fancier updater for when ACL and groups change

def mixed(i, maximum):
    """i hashed into 0..maximum"""
    return int(sha.new(str(i)).hexdigest(), 16) % maximum
    
class ImageSet(object):
    """
    runs queries, mostly on data gathered by ImageIndex, but maybe
    using the live graph too
    """
    def __init__(self, graph, index):
        self.graph = graph
        self.index = index

    def request(self, query):
        log.info('query: %r', query)
        paging = {
            'limit': query.get('paging', {}).get('limit', 10),
            'skip': query.get('paging', {}).get('skip', 0),
        }
        
        s = query.get('sort', [{'time': 'asc'}])

        stream = self.imageStream(s)
        
        stream = self.viewableStream(stream)

        qf = collections.defaultdict(lambda: None, query.get('filter', {}))
        if qf['type'] == 'image':
            stream = itertools.ifilter(lambda doc: not doc['isVideo'], stream)
        elif qf['type'] == 'video':
            stream = itertools.ifilter(lambda doc: doc['isVideo'], stream)
        stream = itertools.ifilter(lambda doc: doc['tags'].isdisjoint(qf['withoutTags']), stream)
        if qf['onlyTagged']:
            stream = itertools.ifilter(lambda doc: not doc['tags'].isdisjoint(qf['onlyTagged']), stream)

        if qf['timeRange']:
            # move the parsing to queryparams!
            s, e = qf['timeRange']
            if s:
                st = parse(s).replace(tzinfo=dateutil.tz.tzlocal())
                stream = itertools.ifilter(lambda doc: doc['t'] and doc['t'] >= st, stream)
            if e:
                et = parse(e).replace(tzinfo=dateutil.tz.tzlocal())
                stream = itertools.ifilter(lambda doc: doc['t'] and doc['t'] <= et, stream)
            
        images = []
        for rowNum, row in enumerate(stream):
            if rowNum < paging['skip']:
                continue
            if len(images) >= paging['limit']:
                # keep counting rowNum
                continue

            outDoc = {'uri': row['uri']}
            if 0: # debug
                rowForJson = row.copy()
                rowForJson['tags'] = list(rowForJson['tags'])
                rowForJson['t'] = rowForJson['t'].isoformat() if rowForJson['t'] else None
                outDoc['_doc'] = rowForJson
            if row['t'] is not None:
                outDoc['time'] = row['t'].isoformat()
            images.append(outDoc)

        try:
            paging['total'] = rowNum + 1
        except UnboundLocalError:
            pass
        
        return {
            'images': images,
            'paging': paging,
        }

    def viewableStream(self, imgs):
        for doc in imgs:
            # screen out the ones this user can't see
            yield doc

    def imageStream(self, sorts):
        if len(sorts) > 1:
            raise NotImplementedError('multiple sorts')
        s = sorts[0]

        if s == {'time': 'asc'}:
            return self.index.byTime
        elif s == {'time': 'desc'}:
            return reversed(self.index.byTime)
        elif 'random' in s:
            c = len(self.index.shuffled)
            offset = mixed(s['random'], c)
            return itertools.chain(
                itertools.islice(self.index.shuffled, offset, c),
                itertools.islice(self.index.shuffled, 0, offset))
        else:
            raise NotImplementedError('sort %r' % s)

def main():
    graph = getGraph()
    graph.query = graph.queryd
    index = ImageIndex(graph)
    iset = ImageSet(graph, index)

    @route('/update', methods=['POST'])
    def update(request):
        log.info('updating %r', request.args)
        index.update(URIRef(request.args['uri']))
        # schedule updateSorts? maybe they need to schedule themselves
        return 'indexed'
    
    @route('/set.json')
    def main(request):
        pairs = []
        for k, vs in request.args.items():
            for v in vs:
                pairs.append((k, v))
        q = queryFromParams(pairs)
        result = iset.request(q)
        return json.dumps(result)

    run("0.0.0.0", networking.imageSet()[1])

if __name__ == '__main__':
    main()
