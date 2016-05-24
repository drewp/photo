from xml.utils import iso8601
import datetime
from dateutil.tz import tzlocal

_photoCreated = {} # uri : datetime
def photoCreated(graph, uri):
    """datetime of the photo's creation time. Cached for the life of
    this process"""

    try:
        ret = _photoCreated[uri]
        if isinstance(ret, ValueError):
            raise ret
        return ret
    except KeyError:
        pass

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
            # also look up the :alternate tree for source images with times
            _photoCreated[uri] = ValueError("can't find a date for %s" % uri)
            raise _photoCreated[uri]
    
    photoDate = rows[0]['t']

    try:
        sec = iso8601.parse(str(photoDate))
    except Exception:
        # i think this is the 1-hour error bug on the site. incoming
        # dates might not have any zone, but we can make a guess about
        # their local time
        sec = iso8601.parse(str(photoDate) + '-0700')

    # todo: this is losing the original tz unnecessarily
    ret = datetime.datetime.fromtimestamp(sec, tzlocal())
    _photoCreated[uri] = ret
    return ret

