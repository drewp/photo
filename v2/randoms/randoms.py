#!../../bin/python
"""
this is probably also a param on the more-general set selection
method, but it was also one of my first v2 components and it seemed
like a good first simple module
"""
from klein import run, route
import sys, json
sys.path.append("../..")
from search import randomSet
from db import getGraph
from requestprofile import timed

graph = getGraph()

@route('/randoms')
def home(request):
    # old one also displayed any tag and any foaf:depicts for the image
    r, elapsed = timed(randomSet, graph, n=int(request.args.get('n', [3])[0]))
    return json.dumps({"randoms": r, "profile": {"randomSet": elapsed}})

run("0.0.0.0", 8034)
