import sys
sys.path.append("/home/drewp/projects/sparqlhttp")
sys.path.append('/my/proj/sparqlhttp')
from sparqlhttp.graph2 import SyncGraph

import pymongo, bson
sys.modules['pymongo.son'] = bson.son
from pymongo import Connection

from monque import Monque
import networking
from ns import initNs

def getGraph():
    return SyncGraph('sesame', networking.graphRepoRoot()+'/photo', initNs=initNs)

def getMonque():
    return Monque(connection=Connection(*networking.monqueMongo()),
                  db='photoQueue')
