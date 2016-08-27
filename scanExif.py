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
                try:
                    stmts.extend(self.orientationStatements(uri, vals))
                except ValueError as e:
                    log.warn('orientationStatements on %r: %r', uri, e)

            #self.graph.remove([(uri, None, None)]) # used to flush some stmts
            self.graph.add(stmts,
                 context=URIRef("http://photo.bigasterisk.com/scan/exif"))
            log.info("added exif from %s %s triples" % (filename, len(stmts)))
        except:
            log.error("on uri=%r filename=%r", uri, filename)
            raise

    def exifValues(self, filename):
        # ctypes was starting to work, but libexif uses C macros for
        # some of the data traversal, so pyrex would probably be
        # better for this.
        #exif = ctypes.CDLL('libexif.so')
        #exif.exif_data_new_from_file.restype = ExifData
        #ed = exif.exif_data_new_from_file(filename)
        #exif.exif_data_dump(ed)
        #
        # also, PIL has PIL.ExifTags (untested)

        assert filename.startswith('/'), "%r not an absolute path" % filename

        cmd = ["exif", "-x", filename]
        log.debug("running %r" % cmd)
        xml = subprocess.Popen(cmd, stdout=subprocess.PIPE).communicate()[0]
        if not xml:
            raise ValueError("no result from exif")
        if not xml.strip().endswith('</exif>'):
            raise ValueError('incomplete xml')

        # galaxy note 2 puts these in, and then the xml doesn't parse
        xml = xml.replace("<User_Comment>\x12\xf8\x0f;</User_Comment>", "")
        xml = xml.replace("<User_Comment>\x12\xf8\x0f;\x01</User_Comment>", "")

        # from note 4, selfie mode
        xml = xml.replace("<User_Comment>\x11\xab\x11\xab</User_Comment>", "")

        # from HP Scanjet 5590
        xml = xml.replace('<Reference_Black/White>', '<Reference_Black_White>')
        xml = xml.replace('</Reference_Black/White>', '</Reference_Black_White>')

        
        try:
            root = ElementTree.fromstring(xml)
        except ElementTree.ParseError, e:
            # happened on /my/pic/phonecam/dn1/20130418_221054-1.jpg
            # not sure how to correct it
            raise
            
        vals = {}
        for child in root:
            vals[child.tag] = child.text
        return vals
    
    def timeStatements(self, uri, vals):
        dateAndTime = None
        # moved 'original' first for pics like /my/pic/digicam/ext-2011-08-11/DSCN1311.JPG
        for timeKey in ['Date_and_Time__original_',
                        'Date_and_Time__Original_',
                        'Date_and_Time', 
                        'Date_and_Time__digitized_',
                        'Date_and_Time__Digitized_',
                        ]:
            try:
                dateAndTime = fixTime(vals[timeKey])
                break
            except (KeyError, TypeError):
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
            try:
                stmts.append((uri, EXIF['exposureTime'], 
                              Literal(parseExposureTime(vals['Exposure_Time']),
                                      datatype=XS.decimal)))
            except (ZeroDivisionError, ValueError) as e:
                log.warn("can't use exposure time %r for %r: %r", vals['Exposure_Time'], uri, e)
        return stmts
        
    def orientationStatements(self, uri, vals):
        stmts = []
        if 'Orientation' in vals:
            o = vals['Orientation'].lower()
            if o not in [
                    'top-left', 'top-right',
                    'bottom-right', 'bottom-left',
                    'left-top', 'right-top',
                    'right-bottom', 'left-bottom',
                    ]:
                raise ValueError(repr(o))
            stmts.append((uri, EXIF['orientation'], EXIF[o]))
        return stmts

    def fileTimeStatements(self, uri, filename):
        dt = datetime.datetime.fromtimestamp(os.path.getmtime(filename))
        dt = dt.replace(tzinfo=tzlocal())
        dateLit = Literal(dt.isoformat(), datatype=XS.dateTime)
        return [(uri, PHO.fileTime, dateLit),
                (uri, DC.date, Literal(dateLit.split('T')[0],
                                       datatype=XS.date))]

def quotientNoExponent(n, d):
    return "{0:.10g}".format(Decimal(n) / Decimal(d))

def parseExposureTime(s):
    """
    >>> parseExposureTime('1/373 sec.')
    '0.002680965147'
    >>> parseExposureTime('1/4 sec.')
    '0.25'
    """
    num, unit = s.split(' ')
    if unit != 'sec.':
        raise ValueError('unknown time unit')
    if '/' in num:
        n, d = map(Decimal, num.split('/'))
    else:
        n, d = int(num), 1
    if d/n > 10000:
        raise ValueError('too big') # e.g. from Palm Pre
    return quotientNoExponent(n, d)
        
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
    import sys, pprint, doctest
    doctest.testmod()
    logging.basicConfig(level=logging.DEBUG)
    class PrintStmts(object):
        def add(self, *args, **kw):
            pprint.pprint(("graph add", args, kw))
    ScanExif(PrintStmts()).addByFilename(None, sys.argv[1])
