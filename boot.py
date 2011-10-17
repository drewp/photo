
import sys
from logging import getLogger, WARN, INFO, basicConfig

getLogger("restkit.client").setLevel(WARN)
getLogger("restkit.conn").setLevel(WARN)
getLogger("timing").setLevel(WARN)
basicConfig(level=INFO)

log = getLogger()

sys.path.insert(0, "/home/drewp/projects/sparqlhttp")
sys.path.insert(0, "/my/proj/sparqlhttp")
import sparqlhttp
print sparqlhttp

# for rdflib
sys.path.insert(0, "/home/drewp/projects/ffg/lib/rdflib/build/lib.linux-x86_64-2.7")
import rdflib
print "rdflib", rdflib.__version__
