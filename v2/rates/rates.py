"""
page about rates of images taken, so you can look for interesting
time ranges
"""

import sys, json, logging
from collections import defaultdict
import datetime
from klein import run, route
from twisted.web.static import File
sys.path.append("../..")
from db import getGraph

graph = getGraph()

logging.basicConfig(level=logging.DEBUG)

@route('/')
def index(request):
    if request.uri != '/':
        raise NotImplementedError()
    return File("./")

@route('/rates')
def rates(request):
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

    return json.dumps(out)
    
run("0.0.0.0", 8045)
