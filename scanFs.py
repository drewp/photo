#!/usr/bin/python
"""
read a tree of the filesystem and write rdf about the images we find

 uri a foaf:Image
 uri :inDirectory dir
                  dir a :DiskDirectory
                  dir :inDirectory dir
 uri :filename basename

"""
import sys, os, urllib, logging
from rdflib.Graph import ConjunctiveGraph
from rdflib import Namespace, RDF, RDFS, URIRef, Literal

log = logging.getLogger('scanFs')
log.setLevel(logging.DEBUG)

PHO = Namespace("http://photo.bigasterisk.com/0.1/")
SITE = Namespace("http://photo.bigasterisk.com/")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")

def uriOfFilename(rootUri, root, filename):
    prefix = root.rstrip('/')
    if not filename.startswith(prefix):
        raise ValueError("%s doesn't start with %s" % (filename, prefix))
    relFile = filename[len(prefix):]
    return URIRef(rootUri + urllib.quote(relFile))

def goodDirNames(names):
    ret = []
    for name in names:
        if not (name.startswith('.') or name.startswith('~')):
            ret.append(name)
    return ret

def filenameIsImage(filename):
    for ext in ['.jpg', '.gif']:
        if filename.lower().endswith(ext):
            return True
    return False

class ScanFs(object):
    def __init__(self, graph, topDir):
        """
        Graph2 object
        """
        assert not topDir.endswith('/')
        self.graph, self.topDir = graph, topDir
        self.rootUri = URIRef(SITE.rstrip('/'))
        
    def fileChanged(self, filename):
        """full path to a file that got added, changed, or deleted.
        If it was a photo, return URI else None"""

        if os.path.exists(filename) and filenameIsImage(filename):
            return self.addPicFile(filename)

        #todo: if file disappeared, clean it out of the graph

    def addPicFile(self, filename):
        filename = os.path.abspath(filename)
        fileUri = uriOfFilename(self.rootUri, self.topDir, filename)
        dirUri = self.addDir(os.path.dirname(filename))
        self.graph.add((fileUri, RDF.type, FOAF.Image),
                       (fileUri, PHO.inDirectory, dirUri),
                       (fileUri, PHO.filename, Literal(filename)),
                       context=URIRef("http://photo.bigasterisk.com/scan/fs"))
        log.info("added pic %s" % filename)
        return fileUri

    def addDir(self, dirPath):
        """add description of this disk directory and every parent directory"""
        if not dirPath.startswith(self.topDir):
            raise ValueError("%s is not in %s" % (dirPath, self.topDir))
        
        dirUri = uriOfFilename(self.rootUri, self.topDir, dirPath)
        dirUri = URIRef(dirUri.rstrip('/') + '/')
        
        stmts = [(dirUri, RDF.type, PHO['DiskDirectory']),
                 (dirUri, PHO['filename'], Literal(dirPath))]

        try:
            parentUri = self.addDir(os.path.dirname(dirPath))
            stmts.append((dirUri, PHO.inDirectory, parentUri))
        except ValueError:
            pass
        
        self.graph.add(*stmts, **{'context':
                             URIRef("http://photo.bigasterisk.com/scan/fs")})
        return dirUri

def main(root, topDir='/my/pic'):

    # this is incomplete; it needs to setup a Graph2 connection
    
    root = os.path.abspath(root)
    assert root.startswith(topDir) or root == topDir

    graph = ConjunctiveGraph()
    
    rootUri = SITE[root[len(topDir) + len('/'):]]
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        print >>sys.stderr, "visit", dirpath

        dirnames[:] = goodDirNames(dirnames)

        for filename in filenames:
            if not filenameIsImage(filename):
                continue

            scanFs.addPicFile(os.path.abspath(os.path.join(dirpath, filename)))

    print >>sys.stderr, "done, writing %d triples" % len(graph)
    print graph.serialize(format='nt')

if __name__ == '__main__':
    main(sys.argv[1])
