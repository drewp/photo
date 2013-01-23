"""
look for faces in a pic, submit alts that crop around those faces
"""
from __future__ import division
import boot
import sys, os, restkit, json, traceback
from rdflib import URIRef
import cv # needs python-opencv
from db import getGraph
from mediaresource import MediaResource
from ns import PHO

class ScanFace(object):
    def __init__(self, graph):
        self.graph = graph
        self.cascade = cv.Load('/usr/share/opencv/haarcascades/haarcascade_frontalface_default.xml') # needs libopencv-core-dev

    def scanPic(self, uri):
        mr = MediaResource(graph, uri)
        jpg, mtime = mr.getImageAndMtime(1000)
        mat = cv.CreateMatHeader(1, len(jpg), cv.CV_8UC1)
        cv.SetData(mat, jpg, len(jpg))
        img = cv.DecodeImage(mat)

        grayscale = cv.CreateImage((img.width, img.height), 8, 1)
        cv.CvtColor(img, grayscale, cv.CV_RGB2GRAY)
        
        cv.EqualizeHist(grayscale, grayscale)

        storage = cv.CreateMemStorage(0)
        faces = cv.HaarDetectObjects(grayscale,
                                     self.cascade,
                                     storage,
                                     1.2, # scaleFactor between scans
                                     3, # minNeighbors
                                     cv.CV_HAAR_DO_CANNY_PRUNING,
                                     (20,20) # min window size
                                     )
        size = cv.GetSize(grayscale)

        for f, neighbors in faces:
            desc = {
                'source' : str(uri),
                'types' : [PHO.Crop],
                'tag' : 'face',
                'x1' : f[0] / size[0],
                'y1' : f[1] / size[1],
                'x2' : (f[0] + f[2]) / size[0],
                'y2' : (f[1] + f[3]) / size[1],
                
                # this ought to have a padded version for showing, and
                # also the face coords inside that padded version, for
                # recognition. Note that the padded one may run into
                # the margins

                'neighbors' : neighbors,
                }

            alt = restkit.Resource(uri.replace('http://photo.bigasterisk.com/', 'http://bang:8031/') + "/alt")
            resp = alt.post(payload=json.dumps(desc), headers={
                'content-type' : 'application/json',
                'x-foaf-agent' : 'http://bigasterisk.com/tool/scanFace'})
            print resp.status, resp.body_string()

    def hasAnyFaces(self, uri):
        """does this source image have any face alts yet"""
        return self.graph.queryd(
            'ASK { ?uri pho:alternate ?alt . ?alt pho:tag "face" .}',
            initBindings={'uri':uri})
       

if __name__ == '__main__':
    graph = getGraph()
    s = ScanFace(graph)

    for row in graph.queryd("""
          SELECT ?img WHERE {
            ?img a foaf:Image .
          }"""):
        if 'gif' in row['img']:
            # maybe crashes cv
            continue
        print row['img']
        if s.hasAnyFaces(row['img']):
            print "has faces"
            continue
        if graph.queryd(
            """ASK {
            { ?uri pho:scanned <http://bigasterisk.com/tool/scanFace> }
            UNION
            { ?parent pho:alternate ?uri }
            }""",
            initBindings={'uri':row['img']}):
            continue
        
        graph.add([(row['img'], PHO['scanned'], URIRef('http://bigasterisk.com/tool/scanFace'))], context=PHO['scanFace'])
        try:
            s.scanPic(row['img'])
        except Exception, e:
            print "on", row['img']
            traceback.print_exc()
            

    # http://photo.bigasterisk.com/phonecam/ki3/IMG_1488.JPG was a tester
    
    

        
