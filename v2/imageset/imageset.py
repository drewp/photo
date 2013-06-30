#!../../bin/python
"""
main search/filter/pager that takes query params for describing a
set of images and returns json descriptions of them
"""
from klein import run, route
import sys, json, itertools, datetime
from rdflib import Literal
sys.path.append("../..")

from db import getGraph
from requestprofile import timed
from oneimagequery import photoCreated

graph = getGraph()

def newestPics(graph):
    d = datetime.date.today()
    while True:
        rows = list(graph.queryd("""
               SELECT DISTINCT ?uri WHERE {
                 ?uri a foaf:Image; dc:date ?d .
               }""", initBindings={"d": Literal(d)}))
        for row in rows:
            row['time'] = photoCreated(graph, row['uri'])
        rows.sort(key=lambda row: row['time'], reverse=True)
        for row in rows:
            row['time'] = row['time'].isoformat()
            yield row
        d = d - datetime.timedelta(days=1)

@route('/set.json')
def main(request):
    if request.args['sort'] == ['new']:
        pics, elapsed = timed(lambda: list(itertools.islice(newestPics(graph), 0, 3)))
        return json.dumps({"newest": pics,
                           "profile": {"newestPics": elapsed}})
    else:
        raise NotImplementedError()

run("0.0.0.0", 8035)
