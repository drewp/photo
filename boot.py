
import sys
from logging import getLogger, WARN, INFO, basicConfig

getLogger("restkit.client").setLevel(WARN)
getLogger("restkit.conn").setLevel(WARN)
getLogger("timing").setLevel(WARN)
basicConfig(level=INFO)

log = getLogger()

sys.path.insert(0, "/home/drewp/projects/sparqlhttp")
sys.path.insert(0, "/my/proj/sparqlhttp")
sys.path.insert(0, "/my/dl/modified/monque")
import sparqlhttp
print sparqlhttp

