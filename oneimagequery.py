from xml.utils import iso8601
import datetime
from dateutil.tz import tzlocal

_photoCreated = {} # uri : datetime
def photoCreated(graph, uri):
    """datetime of the photo's creation time. Cached for the life of
    this process"""

    try:
        return _photoCreated[uri]
    except KeyError:
        pass

    rows = list(graph.query("""
       SELECT ?t WHERE {
         { ?uri exif:dateTime ?t }
         UNION { ?uri pho:fileTime ?t }
       } ORDER BY ?t LIMIT 1""", initBindings={'uri' : uri}))
    if not rows:

        rows = graph.query("""SELECT ?t WHERE {
             ?email a pho:Email ; dcterms:created ?t ; dcterms:hasPart ?uri .
           }""", initBindings={'uri' : uri})
        if not rows:
            # also look up the :alternate tree for source images with times
            raise ValueError("can't find a date for %s" % uri)
    
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

