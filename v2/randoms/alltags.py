import sys
from klein import run, route
import json
sys.path.append("../..")
from db import getGraph
import auth

graph = getGraph()

@route('/allTags')
def allTags(request):
    tags = set()
    for row in graph.queryd(
            "SELECT ?tag WHERE { ?pic scot:hasTag [ rdfs:label ?tag ] }"):
        tag = unicode(row['tag'])
        if tag in auth.hiddenTags:
            continue
        tags.add(tag)
    tags = sorted(tags)
    return json.dumps({'tags': tags})

if __name__ == '__main__':
    run("0.0.0.0", 8054)
