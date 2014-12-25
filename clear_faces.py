#!bin/python
import boot
import db
import multiprocessing.dummy
log = boot.log
graph = db.getGraph()
rows = list(graph.queryd("""SELECT ?pic ?ctx WHERE {
  GRAPH ?ctx {
    ?pic a pho:Crop;
      dcterms:creator <http://bigasterisk.com/tool/scanFace> .
  }
}"""))

left = len(rows)

def removeOne(row):
    global left
    log.info('%d left, removing %s', left, row['ctx'])
    left -= 1
    graph.subgraphClear(row['ctx'])

pool = multiprocessing.dummy.Pool(8)
pool.map(removeOne, rows)

    
# before
# curl http://bang:8080/openrdf-sesame/repositories/photo/size
# 1558672
