import unittest, logging
logging.basicConfig(level=logging.WARN)
logging.getLogger('rdflib').setLevel(logging.WARN)
import imageset

from rdflib import ConjunctiveGraph, Namespace
from rdflib.parser import StringInputSource

P = Namespace('http://example.com/pic/')

class WithTestImages(unittest.TestCase):
    def setUp(self):
        self.graph = ConjunctiveGraph()
        self.graph.parse(StringInputSource('''
        @prefix p: <http://example.com/pic/> .
        @prefix : <http://photo.bigasterisk.com/0.1/> .
        @prefix foaf: <http://xmlns.com/foaf/0.1/> .
        p:a a foaf:Image .
        p:b a foaf:Image .
        p:c a foaf:Image .
        p:d a foaf:Image .
        '''), format='n3')

        self.imageSet = imageset.ImageSet(self.graph)
        self.request = self.imageSet.request

def uris(result):
    return [r['uri'] for r in result['images']]
        
class TestPaging(WithTestImages):
  def test_stops_at_limit(self):
      result = self.request({'paging': {'limit': 2}})
      self.assertEqual(2, len(result['images']))
      
  def test_skips_first_results(self):
      result = self.request({'paging': {'limit': 2, 'skip': 1}})
      self.assertEqual([P.b, P.c], uris(result))
      
  def test_returns_stats(self):
      result = self.request({'paging': {'limit': 2, 'skip': 1}})
      self.assertEqual(2, result['paging']['limit'])
      self.assertEqual(1, result['paging']['skip'])
      self.assertEqual(4, result['paging']['total'])
