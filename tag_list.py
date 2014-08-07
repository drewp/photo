#!bin/python
"""
print all filenames and their tags
"""
from __future__ import division
import warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import formless

from db import getGraph
graph = getGraph()


for row in graph.queryd("""
   SELECT ?pic ?tags ?fn WHERE {
     ?pic a foaf:Image ;  pho:filename ?fn ;  pho:tagString ?tags .
   }"""):
    if not row['tags'].strip():
        continue
    prefixed = ' '.join('T-%s' % x for x in row['tags'].split())
    print row['fn'], prefixed
