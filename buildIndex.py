#!/usr/bin/python
"""
send photo tags, descriptions, and comments (?) to search
"""
from __future__ import division
import boot
from db import getGraph
import networking
import restkit, json
log = boot.log

graph = getGraph()
search = restkit.Resource(networking.searchRoot())

for row in graph.queryd("""
   SELECT ?pic ?tags ?comment ?filename ?isVideo WHERE {
     ?pic a foaf:Image .
     OPTIONAL { ?pic pho:tagString ?tags }
     OPTIONAL { ?pic rdfs:comment ?comment }
     OPTIONAL { ?pic pho:filename ?filename }
     OPTIONAL { ?pic a ?isVideo . FILTER (?isVideo = pho:Video) }
   }"""):
    txt = ' '.join(x for x in
                   [row['tags'], row['comment'], row['filename']] if x)

    # also go to commentServe and add up the comments (but no authors,
    # since that should not be searched, at least at the same strength
    # as the rest of the text)
    
    picVid = 'Video' if row['isVideo'] else 'Photo'
    if txt.strip():
        doc = dict(uri=row['pic'],
                   title="%s %s" % (picVid, row['filename']),
                   view=row['pic'] + "/page",
                   text=txt)
        print doc
        search.post("index", source="photo",
                    payload=json.dumps(doc))
