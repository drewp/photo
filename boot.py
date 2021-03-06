
import sys
from logging import getLogger, WARN, INFO, basicConfig

getLogger("restkit.client").setLevel(WARN)
getLogger("restkit.conn").setLevel(WARN)
getLogger("timing").setLevel(WARN)
basicConfig(level=INFO, format="%(asctime)s %(levelname)s %(name)s %(filename)s:%(lineno)d %(message)s")

log = getLogger()

sys.path.insert(0, "/home/drewp/projects/sparqlhttp")
sys.path.insert(0, "/my/proj/sparqlhttp")

getLogger("rdflib").setLevel(WARN) # for a version announcement that comes out on info /my/site/photo/local/lib/python2.7/site-packages/rdflib/__init__.py
import sparqlhttp
log.debug("sparqlhttp from %r", sparqlhttp)

