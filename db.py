import sys
sys.path.append("/my/proj/sparqlhttp")
from sparqlhttp.graph2 import SyncGraph

import networking
from ns import initNs

def getGraph():
    return SyncGraph('sesame', networking.graphRepoRoot()+'/photo', initNs=initNs)
