import re, logging
from xml.utils import iso8601
import datetime, urllib
from dateutil.tz import tzlocal
from lib import print_timing
from dateutil.parser import parse
import restkit.errors
from servicecall import serviceCallSync, plainCallSync
log = logging.getLogger()

def _fromBasename(graph, uri):

    for row in graph.query("SELECT ?bn WHERE { ?uri pho:basename ?bn }", initBindings={'uri': uri}):
        match = re.match(r'^(\d\d\d\d)-(\d\d)-(\d\d)T(\d\d)-(\d\d)-(\d\d)\.mov$', row['bn'])
        if match:
            y,mo,d,h,mi,s = map(int, match.groups())
            return datetime.datetime(y, mo, d, h, mi, s, tzinfo=tzlocal())
    
def _fromGraphData(graph, uri):
    rows = list(graph.query("""
       SELECT ?t ?mail WHERE {
         { ?uri exif:dateTime ?t }
         UNION { ?uri pho:fileTime ?t } .
         OPTIONAL { ?mail dcterms:hasPart ?uri }
       } ORDER BY ?t LIMIT 1""", initBindings={'uri' : uri}))
    # wrong: exif datetime is preferred over email time, but this is
    # still picking email time.
    if not rows or rows[0]['mail']:
        rows = graph.query("""SELECT ?t WHERE {
             ?email a pho:Email ; dcterms:created ?t ; dcterms:hasPart ?uri .
           }""", initBindings={'uri' : uri})
        if not rows:
            return None
    
    photoDate = rows[0]['t']

    try:
        sec = iso8601.parse(str(photoDate))
    except Exception:
        # i think this is the 1-hour error bug on the site. incoming
        # dates might not have any zone, but we can make a guess about
        # their local time
        sec = iso8601.parse(str(photoDate) + '-0800')
        
    # todo: this is losing the original tz unnecessarily
    return datetime.datetime.fromtimestamp(sec, tzlocal())
    
def photoCreated(graph, uri, _cache=None, useImageSet=True):
    """datetime of the photo's creation time. Cached for the life of
    this process"""

    if _cache is not None:
        try:
            ret = _cache[str(uri)]
            if isinstance(ret, ValueError):
                raise ret
            return ret
        except KeyError:
            pass
    else:
        _cache = {}
        
    ret = _photoCreatedEval(graph, uri, useImageSet)
    if not ret:
        # also look up the :alternate tree for source images with times
        _cache[str(uri)] = ValueError("can't find a date for %s" % uri)
        raise _cache[str(uri)]

    if _cache is not None:
        _cache[str(uri)] = ret
    return ret

def _photoCreatedEval(graph, uri, useImageSet):
    if useImageSet:
        try:
            lines = plainCallSync('todo', 'imageset',
                                  '/created?' + urllib.urlencode({
                                      'uri': [str(uri)]}, doseq=1))
        except restkit.errors.RequestFailed:
            log.warn('imageset/created failed on %s', uri)
        else:
            if lines != 'None':
                return parse(lines)

    ret = _fromBasename(graph, uri)
    if ret:
        return ret

    ret = _fromGraphData(graph, uri)
    return ret
