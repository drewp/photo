import logging
logging.basicConfig()
import unittest
from db import getGraph
from imageurl import ImageSetDesc
from ns import SITE
logging.getLogger('restkit.client').setLevel(logging.WARN)

graph1 = getGraph()

class TestImageSetDesc(unittest.TestCase):
    def testCanonicalOmitsCurrentParam(self):
        s = ImageSetDesc(graph1, None, "/set?tag=t&current=foo")
        self.assertEqual(s.canonicalSetUri(), SITE["set?tag=t"])

    def testCanonicalIncludesDirParam(self):
        s = ImageSetDesc(graph1, None, "/set?dir=http%3A%2F%2Fexample.com%2Fd1&current=foo")
        self.assertEqual(s.canonicalSetUri(), SITE["set?dir=http%3A%2F%2Fexample.com%2Fd1"])

    def testCanonicalIncludesStarParam(self):
        s = ImageSetDesc(graph1, None, "/set?dir=http%3A%2F%2Fexample.com%2Fd1&star=only")
        self.assertEqual(s.canonicalSetUri(), SITE["set?dir=http%3A%2F%2Fexample.com%2Fd1&star=only"])

    def testCanonicalIncludesDateParam(self):
        s = ImageSetDesc(graph1, None, "/set?date=2010-11-20")
        self.assertEqual(s.canonicalSetUri(), SITE["set?date=2010-11-20"])

    def testCanonicalErrorsOnRandomParam(self):
        s = ImageSetDesc(graph1, None, "/set?random=10")
        self.assertRaises(ValueError, s.canonicalSetUri)

    def testAltUrlTurnsStarToOnly(self):
        s = ImageSetDesc(graph1, None, "/set?tag=t")
        self.assertEqual(s.altUrl(star='only'), "/set?tag=t&star=only")
        s = ImageSetDesc(graph1, None, "/set?tag=t&star=only")
        self.assertEqual(s.altUrl(star='only'), "/set?tag=t&star=only")
        s = ImageSetDesc(graph1, None, "/set?tag=t&star=all")
        self.assertEqual(s.altUrl(star='only'), "/set?tag=t&star=only")
        
    def testAltUrlTurnsStarToAll(self):
        s = ImageSetDesc(graph1, None, "/set?tag=t")
        self.assertEqual(s.altUrl(star='all'), "/set?tag=t")
        s = ImageSetDesc(graph1, None, "/set?tag=t&star=only")
        self.assertEqual(s.altUrl(star='all'), "/set?tag=t")
        s = ImageSetDesc(graph1, None, "/set?tag=t&star=all")
        self.assertEqual(s.altUrl(star='all'), "/set?tag=t")
        
