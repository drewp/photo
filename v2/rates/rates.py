"""
page about rates of images taken, so you can look for interesting
time ranges
"""

import sys, json, logging, os
from collections import defaultdict
import datetime
from klein import run, route
from twisted.web.static import File
sys.path.append("../..")
from db import getGraph

graph = getGraph()

logging.basicConfig(level=logging.DEBUG)

@route(r'/<any("", "gui.js"):which>')
def index(request, which):
    return File("./%s" % request.uri)

_rates = None
def getRates():
    global _rates
    if os.environ.get('PHOTO_CACHE_RATES') and _rates is not None:
        return _rates
    out = {
        'byWeek': defaultdict(lambda: 0),
        'byMonth': defaultdict(lambda: 0),
        'byYear':  defaultdict(lambda: 0),
        'byDay':  defaultdict(lambda: 0),
    }

    for row in graph.queryd(
            """SELECT ?date WHERE {
                 ?pic a foaf:Image; dc:date ?date .
               }"""):
        date = datetime.date(*map(int, row['date'].split('-')))
        weekStart = date - datetime.timedelta(days=date.isoweekday())
        out['byWeek'][weekStart.isoformat()] += 1
        out['byDay'][row['date']] += 1
        out['byMonth'][row['date'].rsplit('-', 1)[0]] += 1
        out['byYear'][row['date'].rsplit('-', 2)[0]] += 1
    _rates = out
    return out
    
@route('/rates')
def rates(request):
    return json.dumps(getRates())

@route('/heatmap')
def heatmap(request):
    import heatmap
    reload(heatmap)
    request.setHeader('Content-Type', 'image/png')
    return heatmap.makeImage(getRates())

if __name__ == '__main__':
    run("0.0.0.0", 8045)
