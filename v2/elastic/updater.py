#!../../bin/python
"""

Runs elasticsearch and another server that does writes to ES.

Read from sesame, write/update documents to elasticsearch
"""

from klein import run, route
import sys
sys.path.append("../..")
from cyclone.httpclient import fetch

from db import getGraph
import networking
from oneimagequery import photoCreated

graph = getGraph()

def findPhotos(graph):
    for row in graph.query("SELECT ?uri WHERE { ?uri a foaf:Image . }"):
        yield row.uri

def writeDoc(graph, uri, elasticRoot):
    t = photoCreated(graph, uri)
    fetch(elasticRoot + '')

@route('/update/all', method='POST')
def updateAll(request):
    for uri in findPhotos(graph):
        writeDoc(uri)

@route('/update', method='POST')
def updateOne(request):
    if request.args['uri']
        pics, elapsed = timed(lambda: list(itertools.islice(newestPics(graph), 0, 3)))
        return json.dumps({"newest": pics,
                           "profile": {"newestPics": elapsed}})
    else:
        raise NotImplementedError()



run("0.0.0.0", 8036)
