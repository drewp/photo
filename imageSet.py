from __future__ import division
import sys, os, md5, urllib, time, logging, zipfile
from StringIO import StringIO
from twisted.application import internet, service
from nevow import loaders, rend, static, tags as T, inevow
from rdflib import Namespace, RDF, RDFS, Variable, URIRef
from zope.interface import implements
from twisted.python.components import registerAdapter, Adapter
from photos import Full, thumb
log = logging.getLogger()
PHO = Namespace("http://photo.bigasterisk.com/0.1/")
SITE = Namespace("http://photo.bigasterisk.com/")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")

## class StringIOView(Adapter):
##     implements(inevow.IResource)
##     def locateChild(ctx, segments):
##         return None, []
##     def renderHTTP(self, ctx):
##         return str(self.original.getvalue())
## try: registerAdapter(StringIOView, StringIO, inevow.IResource)
## except ValueError: pass

class ImageSet(rend.Page):
    """
    multiple images, with one currently-featured one. Used for search results
    """
    docFactory = loaders.xmlfile("imageSet.html")
    def __init__(self, ctx, graph, uri):
        self.graph, self.uri = graph, uri

        q = self.graph.queryd("""SELECT ?photo WHERE {
                                   ?photo foaf:depicts ?u
                                 }""",
                              initBindings={Variable('?u') : self.uri})

        self.photos = sorted([row['photo'] for row in q])

        self.currentPhoto = URIRef(ctx.arg('current'))
        if self.currentPhoto not in self.photos:
            self.currentPhoto = self.photos[0]

    def renderHTTP(self, ctx):
        if ctx.arg('archive') == 'zip':
            return self.archiveZip(ctx)
        return rend.Page.renderHTTP(self, ctx)

    def archiveZip(self, ctx):
        f = StringIO('')
        zf = zipfile.ZipFile(f, 'w', zipfile.ZIP_DEFLATED)
        for photo in self.photos:
            data, mtime = thumb(photo, maxSize=Full)
            zf.writestr(str(photo.split('/')[-1]), data)

        zf.close()
        request = inevow.IRequest(ctx)
        request.setHeader("Content-Type", "multipart/x-zip")

        downloadFilename = self.uri.split('/')[-1] + ".zip"
        request.setHeader("Content-Disposition",
                          "attachment; filename=%s" %
                          downloadFilename.encode('ascii'))

        return f.getvalue()
        
    def render_title(self, ctx, data):
        return self.graph.label(self.uri)

    def render_intro(self, ctx, data):
        intro = self.graph.value(self.uri, PHO['intro'])
        if intro is not None:
            intro = intro.replace(r'\n', '\n') # rdflib parse bug?
            return ctx.tag[T.raw(intro)]
        else:
            return ''
    
    def render_setLabel(self, ctx, data):
        return self.graph.label(self.uri)

    def render_currentLabel(self, ctx, data):
        return self.graph.label(self.currentPhoto,
                                # keep the title line taking up space
                                # so the image doesn't bounce around
                                # when there's no title
                                default=T.raw("&nbsp;"))
    
    def data_photosInSet(self, ctx, data):
        return self.photos
    
    def render_thumb(self, ctx, data):
        return T.a(href=["?current=", data])[T.img(src=[data, "?size=thumb"])]

    def render_featured(self, ctx, data):
        return T.a(href=[self.currentPhoto, "?size=full"])[T.img(src=[self.currentPhoto, "?size=large"],
                     alt=self.graph.label(self.currentPhoto))]

    def render_zipUrl(self, ctx, data):
        return [self.uri, "?archive=zip"]
