#!/usr/bin/python
"""
send photo tags, descriptions, and comments (?) to search
"""
from __future__ import division
import boot, warnings

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import formless

from db import getGraph
import networking
import restkit, json, logging
log = boot.log

log.setLevel(logging.DEBUG)
logging.getLogger("graph2").setLevel(logging.INFO)
graph = getGraph()
search = restkit.Resource(networking.searchRoot())

sent = 0
for row in graph.queryd("""
   SELECT ?pic ?tags ?comment ?filename ?isVideo WHERE {
     ?pic a foaf:Image .
     OPTIONAL { ?pic pho:tagString ?tags }
     OPTIONAL { ?pic rdfs:comment ?comment }
     OPTIONAL { ?pic pho:filename ?filename }
     OPTIONAL { ?pic a ?isVideo . FILTER (?isVideo = pho:Video) }
   }"""):
    txt = ' '.join(
        x for x in
        [row['tags'],
         row['comment'],
         row['filename'],
         'video' if row['isVideo'] else '',
        ] if x)

    # also go to commentServe and add up the comments (but no authors,
    # since that should not be searched, at least at the same strength
    # as the rest of the text)

    # need to boost recent dates somehow. send a date? send a boost factor?
    
    picVid = 'Video' if row['isVideo'] else 'Photo'
    if txt.strip():
        doc = dict(uri=row['pic'],
                   title="%s %s" % (picVid, row['filename']),
                   view=row['pic'] + "/page",
                   text=txt)
        for retries in range(3):
            try:
                ret = search.post("index", source="photo",
                                  payload=json.dumps(doc))
                # this is the exact amount you have to call to get keepalive
                ret.body_string()
                sent += 1
                break
            except Exception:
                import traceback, time
                print "while sending %s %r" % (sent, doc)
                traceback.print_exc(limit=2)
                time.sleep(5)
