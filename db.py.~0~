import sys
sys.path.append('/my/proj/sparqlhttp')
from sparqlhttp.graph2 import SyncGraph

import pymongo, bson
sys.modules['pymongo.son'] = bson.son

from monque import Monque
import networking
from ns import initNs

def getGraph():
    return SyncGraph('sesame', networking.graphRepoRoot()+'/photo', initNs=initNs)

def getMonque():
    from pymongo import Connection
    db = Connection('bang', 27017)['photoQueue']
    return Monque(db)
