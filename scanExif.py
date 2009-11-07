"""
tried pypi 'pexif'; errors on struct.unpack
tried pyexif.sf.net; doesn't find data in phone pics
tried python-iptcdata; didn't find anything in my pics
tried ctypes on libexif; C macros aren't available

comparable: http://www.kanzaki.com/ns/exif2rdf.pl
also: http://svn.foaf-project.org/foaftown/geo/photos/old/geoloc_media.pl

"""
from __future__ import division
from rdflib import Namespace, Literal, BNode, RDF, URIRef
import subprocess, logging
from xml.etree import ElementTree

PHO = Namespace("http://photo.bigasterisk.com/0.1/")
DC = Namespace("http://purl.org/dc/elements/1.1/")
XS = Namespace("http://www.w3.org/2001/XMLSchema#")
EXIF = Namespace("http://www.kanzaki.com/ns/exif#")
WGS = Namespace("http://www.w3.org/2003/01/geo/wgs84_pos#")

log = logging.getLogger('scanExif')
log.setLevel(logging.DEBUG)

class ScanExif(object):
    def __init__(self, graph):
        self.graph = graph

    def addPic(self, uri):
        """
        uri has a PHO.filename edge with a real path object. Read that
        path and write more statements from the exif data.

        Skip this if there is already exif data for the image. Todo:
        notice if the image file -changed-, and reread in that case.
        """
        if self.graph.contains((uri, EXIF.dateTime, None)):
            #log.debug("seen %s" % uri)
            return
        
        filename = self.graph.value(uri, PHO.filename)
        if filename is None:
            log.warn("addPic on %r has no pho:filename" % uri)
            return

        self.addByFilename(uri, filename)

    def addByFilename(self, uri, filename):

        # ctypes was starting to work, but libexif uses C macros for
        # some of the data traversal, so pyrex would probably be
        # better for this.
        #exif = ctypes.CDLL('libexif.so')
        #exif.exif_data_new_from_file.restype = ExifData
        #ed = exif.exif_data_new_from_file(filename)
        #exif.exif_data_dump(ed)

        xml = subprocess.Popen(["exif", "-x", filename],
                               stdout=subprocess.PIPE).communicate()[0]
        if not xml:
            # todo: no exif? we should still fake a date from the file mtime, perhaps
            return
        root = ElementTree.fromstring(xml)
        vals = {}
        for child in root:
            vals[child.tag] = child.text
            
        stmts = [
            # no timezone in exif? i think the best guess is *whatever
            # california was doing around then*
            (uri, EXIF.dateTime, Literal(fixTime(vals['Date_and_Time']),
                                         datatype=XS.dateTime)),
            # this is for easier searches on date
            (uri, DC.date, Literal(fixTime(vals['Date_and_Time']).split('T')[0],
                                   datatype=XS.date)),
            # camera? exposure stuff? orientation? res?
            ]
        if 'East_or_West_Longitude' in vals:
            # this is how palm pre photos come in:
            lat = floatFromDms(vals['InteroperabilityIndex'],
                               vals['InteroperabilityVersion'])
            long = floatFromDms(vals['East_or_West_Longitude'],
                                vals['Longitude'])

            point = URIRef("http://photo.bigasterisk.com/point/%g/%g" %
                           (lat, long))
            stmts.extend([
                (uri, WGS.location, point),
                (point, RDF.type, WGS.Point),
                (point, WGS.lat, Literal("%g" % lat)),
                (point, WGS.long, Literal("%g" % long)),
                # point could be 'near' other things
                ])
        self.graph.add(*stmts,
             **{'context' : URIRef("http://photo.bigasterisk.com/scan/exif")})
        log.info("added exif from %s %s triples" % (filename, len(self.graph)))

        
def floatFromDms(compass, dms):
    d, m, s = map(float, dms.split(', '))
    r = d + (m + s / 60) / 60
    if compass in ['S', 'W']:
        r = -r
    return r

def fixTime(exifTime):
    words = exifTime.replace(' ', ':').split(':')
    return "%s-%s-%sT%s:%s:%s" % tuple(words)

if __name__ == '__main__':
    ScanExif(None).addByFilename(None,
      '/my/pic/phonecam/dt-2009-07-16/CIMG0068.jpg'
#                                 '/my/pic/digicam/dl-2009-07-20/DSC_0092.JPG'
                                 )
