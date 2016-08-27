#!bin/python

from db import getGraph
from mediaresource import MediaResource

graph = getGraph()

for row in graph.queryd("""
   SELECT ?pic WHERE {
     ?pic a foaf:Image .
     { ?pic exif:orientation exif:bottom-right } UNION {
      ?pic exif:orientation exif:right-top } 
   }"""):
    MediaResource(graph, row['pic']).purgeCached()
