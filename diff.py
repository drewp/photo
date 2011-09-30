"""
compare images taken consecutively, when they're similar enough, make
a new set out of the similar images. Give it a type that draws as 1
image within a image set list. List one image as the preferred one
(last one? sharpest one?). Users can pick a different image to be the
preferred one in the set. Draw-as-1-img will also be the case for
crops and other refinements.

show the timeline of when the pics were taken. sometimes i take a series of pics to show how long something lasted.

sometimes the images aren't exactly consecutive. same-directory is
better than mixed directories, since those are probably from different
cameras

try to notice stereo-pair images.

record sharpness of every pic, especially for use in picking a set leader.

let the user break down a set according to a lower similarity
threshold, or breaking it apart entirely, or manually removing images
from it.
"""
import datetime

def analyze(graph, uris):
    prev = None
    for uri in uris:
        

def analyzeDay(graph, day):
    analyze(graph, (row['pic'] for row in graph.queryd(
        "SELECT ?pic WHERE { ?pic a foaf:Image ; dc:date ?day }",
        initBindings={'day' : Literal(day, datatype=XS['date'])})))

graph = db.getGraph()
analyzeDay(datetime.date(2011,9,16))
    
