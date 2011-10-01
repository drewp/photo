"""
tried pypi 'pexif'; errors on struct.unpack
tried pyexif.sf.net; doesn't find data in phone pics
tried python-iptcdata; didn't find anything in my pics
tried ctypes on libexif; C macros aren't available

comparable: http://www.kanzaki.com/ns/exif2rdf.pl
also: http://svn.foaf-project.org/foaftown/geo/photos/old/geoloc_media.pl

"""
from __future__ import division
from decimal import Decimal
from rdflib import Literal, URIRef
import subprocess, logging, os, datetime
from xml.etree import ElementTree
from dateutil.tz import tzlocal
from xml.parsers.expat import ExpatError
from ns import PHO, DC, XS, EXIF, WGS, RDF

log = logging.getLogger('scanExif')
log.setLevel(logging.DEBUG)

def quotientNoExponent(n, d):
    return "{0:f}".format(Decimal(n) / Decimal(d))

class ScanExif(object):
    def __init__(self, graph):
        """Takes sparqlhttp.graph2.SyncGraph"""
        self.graph = graph

    def addPic(self, uri, rerunScans=False):
        """
        uri has a PHO.filename edge with a real path object. Read that
        path and write more statements from the exif data.

        Skip this if there is already exif data for the image (unless
        you force rerunScans).

        Todo:
        notice if the image file -changed-, and reread in that case.
        """
        if not rerunScans and self.graph.contains((uri, EXIF.dateTime, None)):
            #log.debug("seen %s" % uri)
            return
        
        filename = self.graph.value(uri, PHO.filename)
        if filename is None:
            log.warn("addPic on %r has no pho:filename" % uri)
            return

        self.addByFilename(uri, filename)

    def addByFilename(self, uri, filename):
        try:
            vals = self.exifValues(filename)
            log.debug("exif values: %r", vals)
        except (ExpatError, ValueError):
            stmts = self.fileTimeStatements(uri, filename)
        else:
            stmts = []

            stmts.extend(self.timeStatements(uri, vals))
            stmts.extend(self.positionStatements(uri, vals))
            stmts.extend(self.exposureStatements(uri, vals))

        #self.graph.remove([(uri, None, None)]) # used to flush some stmts
        self.graph.add(stmts,
             context=URIRef("http://photo.bigasterisk.com/scan/exif"))
        log.info("added exif from %s %s triples" % (filename, len(stmts)))

    def exifValues(self, filename):
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
            raise ValueError("no result from exif")

        root = ElementTree.fromstring(xml)
            
        vals = {}
        for child in root:
            vals[child.tag] = child.text
        return vals
    
    def timeStatements(self, uri, vals):
        dateAndTime = None
        # moved 'original' first for pics like /my/pic/digicam/ext-2011-08-11/DSCN1311.JPG
        for timeKey in ['Date_and_Time__original_', 'Date_and_Time', 
                        'Date_and_Time__digitized_']:
            try:
                dateAndTime = fixTime(vals[timeKey])
                break
            except KeyError:
                pass
        if dateAndTime is not None:
            return [
                # no timezone in exif? i think the best guess is *whatever
                # california was doing around then*
                (uri, EXIF.dateTime, Literal(dateAndTime, datatype=XS.dateTime)),
                # this is for easier searches on date
                (uri, DC.date, Literal(dateAndTime.split('T')[0], datatype=XS.date)),
                # camera? exposure stuff? orientation? res?
                ]
        return []
    

    def positionStatements(self, uri, vals):
        stmts = []

        try:
            # this is how old palm pre photos come in:
            lat = floatFromDms(vals['InteroperabilityIndex'],
                               vals['InteroperabilityVersion'])
            long = floatFromDms(vals['East_or_West_Longitude'],
                                vals['Longitude'])
        except KeyError:
            # modern palm pre photos, and presumably other normal systems:
            try:
                lat = floatFromDms(vals['North_or_South_Latitude'],
                                   vals['Latitude'])
                long = floatFromDms(vals['East_or_West_Longitude'],
                                    vals['Longitude'])
            except KeyError:
                return []

        point = URIRef("http://photo.bigasterisk.com/point/%g/%g" %
                       (lat, long))
        stmts.extend([
            (uri, WGS.location, point),
            (point, RDF.type, WGS.Point),
            (point, WGS.lat, Literal("%g" % lat, datatype=XS.decimal)),
            (point, WGS.long, Literal("%g" % long, datatype=XS.decimal)),
            # point could be 'near' other things
            ])
        return stmts
    
    def exposureStatements(self, uri, vals):
        stmts = []
        if 'Exposure_Time' in vals:
            n, d = map(Decimal, vals['Exposure_Time'].split(' ')[0].split('/'))
            if d/n > 10000:
                pass # bogus, e.g. from Palm Pre
            else:
                stmts.append((uri, EXIF['exposureTime'], 
                              Literal(quotientNoExponent(n, d),
                                      datatype=XS.decimal)))
        return stmts


    def fileTimeStatements(self, uri, filename):
        dt = datetime.datetime.fromtimestamp(os.path.getmtime(filename))
        dt = dt.replace(tzinfo=tzlocal())
        dateLit = Literal(dt.isoformat(), datatype=XS.dateTime)
        return [(uri, PHO.fileTime, dateLit),
                (uri, DC.date, Literal(dateLit.split('T')[0],
                                       datatype=XS.date))]
        
def floatFromDms(compass, dms):
    d, m, s = map(Decimal, dms.split(', '))
    r = d + (m + s / 60) / 60
    if compass in ['S', 'W']:
        r = -r
    return r

def fixTime(exifTime):
    words = exifTime.replace(' ', ':').split(':')
    return "%s-%s-%sT%s:%s:%s" % tuple(words)

if __name__ == '__main__':
    import sys, pprint
    logging.basicConfig(level=logging.DEBUG)
    class PrintStmts(object):
        def add(self, *args, **kw):
            pprint.pprint(("graph add", args, kw))
    ScanExif(PrintStmts()).addByFilename(None, sys.argv[1])
