import sys
sys.path.append("/home/drewp/projects/sparqlhttp")
sys.path.append('/my/proj/sparqlhttp')
from sparqlhttp.graph2 import SyncGraph

import pymongo

import networking
from ns import initNs

def getGraph():
    return SyncGraph('sesame', networking.graphRepoRoot()+'/photo', initNs=initNs)

def getTestGraph(n3):
    from rdflib import Graph
    from rdflib.parser import StringInputSource
    g = Graph()
    g.parse(StringInputSource(n3), format="n3")
    for k,v in initNs.items():
        g.bind(k, v)
    return g
    
def getMonque():
    from pymongo import Connection
    db = Connection(*networking.monqueMongo())['photoQueue']
    from monque import Monque
    return Monque(db)

def getProgressCollection():
    from pymongo import MongoClient
    db = MongoClient(*networking.monqueMongo(), connect=False)['photoQueue']
    return db['progress']
    

if __name__ == '__main__':
    getMonque()
    getGraph().contains((None, None, None))
    print "connected ok"
