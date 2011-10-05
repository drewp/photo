#!/usr/bin/python
"""
send photo tags, descriptions, and comments (?) to search
"""
from __future__ import division
from db import getGraph
import restkit, json, logging
logging.basicConfig(level=logging.DEBUG)

graph = getGraph()
search = restkit.Resource("http://bang:8080/search_2.8.1-1.0.3/")

combinedTxt = {} # uri : all text

for row in graph.queryd("""
   SELECT ?pic ?tags ?comment ?filename WHERE {
     ?pic a foaf:Image .
     OPTIONAL { ?pic pho:tagString ?tags }
     OPTIONAL { ?pic rdfs:comment ?comment }
     OPTIONAL { ?pic pho:filename ?filename } 
   }"""):
    txt = ' '.join(x for x in row.values() if x and x != row['pic'])
    if txt.strip():
        search.post("index", source="photo",
                    payload=json.dumps(dict(uri=row['pic'],
                                            view=row['pic'] + "/page",
                                            text=txt)))
