
import logging, sys

logging.getLogger("restkit.client").setLevel(logging.WARN)
logging.getLogger("restkit.conn").setLevel(logging.WARN)
logging.basicConfig(level=logging.DEBUG)

log = logging.getLogger()

sys.path.insert(0, "/home/drewp/projects/sparqlhttp")
sys.path.insert(0, "/my/proj/sparqlhttp")
import sparqlhttp
print sparqlhttp

# for rdflib
sys.path.insert(0, "/home/drewp/projects/ffg/lib/rdflib/build/lib.linux-x86_64-2.7")
import rdflib
print "rdflib", rdflib.__version__
