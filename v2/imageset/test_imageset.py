import unittest, logging
logging.basicConfig(level=logging.WARN)
logging.getLogger('rdflib').setLevel(logging.WARN)
import imageset

from rdflib import ConjunctiveGraph, Namespace
from rdflib.parser import StringInputSource
from ns import bindAll

P = Namespace('http://example.com/pic/')
        
class WithTestImages(unittest.TestCase):
    def setUp(self):
        graph = ConjunctiveGraph()
        graph.parse(StringInputSource('''
          @prefix p: <http://example.com/pic/> .
          @prefix : <http://photo.bigasterisk.com/0.1/> .
          @prefix foaf: <http://xmlns.com/foaf/0.1/> .
          @prefix xs: <http://www.w3.org/2001/XMLSchema#> .
          @prefix exif: <http://www.kanzaki.com/ns/exif#> .

          p:a a foaf:Image; exif:dateTime "2014-01-01T00:00:00Z"^^xs:dateTime .
          p:b a foaf:Image; exif:dateTime "2014-01-02T00:00:00Z"^^xs:dateTime .
          p:c a foaf:Image; exif:dateTime "2014-01-03T00:00:00Z"^^xs:dateTime .
          p:d a foaf:Image; exif:dateTime "2014-01-04T00:00:00Z"^^xs:dateTime .
        '''), format='n3')

        bindAll(graph)

        index = imageset.ImageIndex(graph)
        index.finishBackgroundIndexing()
        self.imageSet = imageset.ImageSet(graph, index)
        self.request = self.imageSet.request

def uris(result):
    return [r['uri'] for r in result['images']]
        
class TestPaging(WithTestImages):
    def test_stops_at_limit(self):
        result = self.request({'paging': {'limit': 2}})
        self.assertEqual(2, len(result['images']))
        
    def test_skips_first_results(self):
        result = self.request({'paging': {'limit': 2, 'skip': 1}})
        self.assertListEqual([P.b, P.c], uris(result))
        
    def test_returns_stats(self):
        result = self.request({'paging': {'limit': 2, 'skip': 1}})
        self.assertEqual(2, result['paging']['limit'])
        self.assertEqual(1, result['paging']['skip'])
        self.assertEqual(4, result['paging']['total'])

class TestRandom(WithTestImages):
    def test_predictable_order_with_seed(self):
        result = self.request({'sort': [{'random': 1}]})
        self.assertListEqual([P.c, P.a, P.d, P.b], uris(result))

    def test_maintains_order_with_paging(self):
        result = self.request({'sort': [{'random': 1}], 'paging': {'skip': 2}})
        self.assertListEqual([P.d, P.b], uris(result))
    
