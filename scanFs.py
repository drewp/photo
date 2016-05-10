#!/usr/bin/python
"""
read a tree of the filesystem and write rdf about the images we find

 uri a foaf:Image
 uri :inDirectory dir
                  dir a :DiskDirectory
                  dir :inDirectory dir
 uri :filename basename

"""
import os, urllib, logging
from rdflib import URIRef, Literal
from ns import PHO, SITE, FOAF, RDF
log = logging.getLogger('scanFs')
log.setLevel(logging.DEBUG)

# these also appear in nginx_route.conf
imageExtensions = ('.jpg', '.gif', '.jpeg', '.png')
videoExtensions = ('.mp4','.avi','.mov','.webm')

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

        if not os.path.exists(filename):
            # todo: might we have heard about it before we can see it on nfs?
            self.fileDisappeared(filename)

    def fileDisappeared(self, filename):
        log.info('file %r is gone', filename)
        filename = os.path.abspath(filename)
        fileUri = uriOfFilename(self.rootUri, self.topDir, filename)

        for ctx in [URIRef("http://photo.bigasterisk.com/scan/exif"),
                    URIRef("http://photo.bigasterisk.com/scan/fs")
        ]:
            # need 2 remove passes because the graph.remove call only
            # works in 1 ctx at once.
            toRemove = []
            for row in self.graph.queryd('''
              SELECT ?p ?o WHERE {
                GRAPH ?g { ?s ?p ?o }
              }''', initBindings={'g': ctx, 's': fileUri}):
                toRemove.append((fileUri, row['p'], row['o']))
            log.info('removing %s triples from %r for %r', len(toRemove), ctx, fileUri)
            log.info(toRemove)
            self.graph.remove(toRemove, context=ctx)
        # todo: not removing tags or deeper gps statements

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
        
        self.graph.add(triples=stmts,
                       context=URIRef("http://photo.bigasterisk.com/scan/fs"))
        return dirUri
