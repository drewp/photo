import unittest
import datetime
from dateutil.tz import tzlocal

from rdflib import Namespace

from db import getTestGraph
from oneimagequery import photoCreated

EX = Namespace('http://example.com/')
graph = getTestGraph('''
@prefix ex: <http://example.com/> .
@prefix pho: <http://photo.bigasterisk.com/0.1/> .
@prefix xs: <http://www.w3.org/2001/XMLSchema#> .
@prefix dc: <http://purl.org/dc/elements/1.1/> .

ex:img1
  pho:fileTime "2017-02-11T12:30:57.850030-08:00"^^xs:dateTime;
  pho:basename "2017-02-08T11-12-25.mov" .

ex:img2
  pho:filename "/my/pic/house/changing/2017-02-11T11:19:06.jpg" ;
  dc:date "2017-02-11"^^dc:date ;
  pho:basename "2017-02-11T11:20:06.jpg" ;
  pho:fileTime "2017-02-11T11:20:06.510067-08:00"^^xs:dateTime .


''')

class TestPhotoCreated(unittest.TestCase):
    def testUseIphoneFilename(self):
        self.assertEqual(datetime.datetime(2017, 2, 8, 11, 12, 25, tzinfo=tzlocal()),
                         photoCreated(graph, EX['img1']))
        
    def testUseFileTime(self):
        self.assertEqual(datetime.datetime(2017, 2, 11, 11, 20, 6, tzinfo=tzlocal()),
                         photoCreated(graph, EX['img2']))        
