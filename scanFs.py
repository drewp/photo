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
from rdflib import Namespace, RDF, URIRef, Literal

log = logging.getLogger('scanFs')
log.setLevel(logging.DEBUG)

PHO = Namespace("http://photo.bigasterisk.com/0.1/")
SITE = Namespace("http://photo.bigasterisk.com/")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")

imageExtensions = ('.jpg', '.gif', '.jpeg')
videoExtensions = ('.mp4','.avi')

def uriOfFilename(rootUri, root, filename):
    prefix = root.rstrip('/')
    if not filename.startswith(prefix):
        raise ValueError("%s doesn't start with %s" % (filename, prefix))
    relFile = filename[len(prefix):]
    return URIRef(rootUri + urllib.quote(relFile))

def filenameIsImage(filename):
    """
     or a video
    """
    for ext in imageExtensions + videoExtensions:
        if filename.lower().endswith(ext):
            return True
    return False

class ScanFs(object):
    def __init__(self, graph, topDir):
        """
        sparqlhttp.graph2.SyncGraph object
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

        if (self.graph.contains((fileUri, RDF.type, FOAF.Image)) and
            self.graph.contains((fileUri, PHO.filename, None))):
            #log.debug("seen %s" % filename)

            # this return needs to be turned off if you're trying to
            # reread files already in the graph. Or you could just zap
            # the :scan/fs context and do them all again
            
            return fileUri
        
        dirUri = self.addDir(os.path.dirname(filename))
        ctx = URIRef("http://photo.bigasterisk.com/scan/fs")
        self.graph.add([
            (fileUri, RDF.type, FOAF.Image),
            (fileUri, PHO.inDirectory, dirUri),
            (fileUri, PHO.filename, Literal(filename)),
            (fileUri, PHO.basename, Literal(os.path.basename(filename)))],
                       context=ctx)

        if filename.lower().endswith(videoExtensions):
            self.graph.add([(fileUri, RDF.type, PHO.Video)], context=ctx)

        log.info("added pic %s" % filename)
        return fileUri

    def addDir(self, dirPath):
        """add description of this disk directory and every parent directory"""
        if not dirPath.startswith(self.topDir):
            raise ValueError("%s is not in %s" % (dirPath, self.topDir))
        
        dirUri = uriOfFilename(self.rootUri, self.topDir, dirPath)
        dirUri = URIRef(dirUri.rstrip('/') + '/')
        
        stmts = [(dirUri, RDF.type, PHO['DiskDirectory']),
                 (dirUri, PHO['filename'], Literal(dirPath)),
                 (dirUri, PHO['basename'], Literal(os.path.basename(dirPath)))]

        try:
            parentUri = self.addDir(os.path.dirname(dirPath))
            stmts.append((dirUri, PHO.inDirectory, parentUri))
        except ValueError:
            pass
        
        self.graph.add(stmts,
                       context=URIRef("http://photo.bigasterisk.com/scan/fs"))
        return dirUri
