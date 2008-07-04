from __future__ import division
import logging, zipfile
from StringIO import StringIO
from nevow import loaders, rend, tags as T, inevow
from rdflib import Namespace, Variable, URIRef
from zope.interface import implements
from twisted.python.components import registerAdapter, Adapter
from photos import Full, thumb
from urls import localSite
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
                                   ?photo foaf:depicts ?u ;
                                          pho:viewableBy pho:friends .
                                 }""",
                              initBindings={Variable('?u') : self.uri})

        self.photos = sorted([row['photo'] for row in q])

        self.currentPhoto = URIRef(ctx.arg('current'))
        if self.currentPhoto not in self.photos:
            self.currentPhoto = self.photos[0]

    def renderHTTP(self, ctx):
        if ctx.arg('rss'):
            # can't use a /rss child, since we're not receiving
            # segments anymore here. That's probably going to be a
            # problem later, but rss=1 is ok today.
            return self.photoRss(ctx)
        
        if ctx.arg('archive') == 'zip':
            request = inevow.IRequest(ctx)
            ua = request.getHeader('User-agent')
            if 'Googlebot' in ua or 'Yahoo! Slurp' in ua or 'http://search.msn.com/msnbot.htm' in ua:
                raise ValueError("bots, you don't want these huge zip files")

            return self.archiveZip(ctx)
        ret = rend.Page.renderHTTP(self, ctx)
        return ret

    def render_zipSizeWarning(self, ctx, data):
        mb = 17.3 / 9 * len(self.photos)
        secs = mb * 1024 / 40 
        return "(file will be roughly %d MB and take %d mins to download)" % (mb, secs / 60)

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
        cls = "not-current"
        thisThumbSrc = localSite(data)
        if data == self.currentPhoto:
            cls = "current"
            return T.span(style="position: relative")[
                T.img(class_=cls, src=[thisThumbSrc, "?size=thumb"]),
                ]

        return T.span(style="position: relative")[
            T.a(href=["?current=", data])[
            T.img(class_=cls, src=[thisThumbSrc, "?size=thumb"])]]

    def render_featured(self, ctx, data):
        currentLocal = localSite(self.currentPhoto)
        return T.a(href=[currentLocal, "?size=full"])[T.img(src=[currentLocal, "?size=large"],
                     alt=self.graph.label(self.currentPhoto))]

    def render_zipUrl(self, ctx, data):
        return [self.uri, "?archive=zip"]

    def render_link(self, ctx, data):
        return '<img src="%s?size=large"/>' % self.currentPhoto

    def render_prevNextJs(self, ctx, data):
        i = self.photos.index(self.currentPhoto)
        
        return ctx.tag['var arrowPages = {prev : "%s", next : "%s"}' %
                       (self.photos[max(0, i - 1)],
                        self.photos[min(len(self.photos) - 1, i + 1)])]
    
    def photoRss(self, ctx):
        request = inevow.IRequest(ctx)

        # copied from what flickr emits
        request.setHeader("Content-Type", "text/xml; charset=utf-8")

        items = []
        for pic in self.photos:
            content = pic + '?size=screen'
            items.append(T.Tag('item')[
                T.Tag('title')[self.graph.label(pic, default=pic.split('/')[-1])],
                T.Tag('link')[content],
                T.Tag('media:thumbnail')(url=pic + '?size=small'),
                T.Tag('media:content')(url=content),
                ])

        from nevow import flat
        return """<?xml version="1.0" encoding="utf-8" standalone="yes"?>
        <rss version="2.0" 
          xmlns:media="http://search.yahoo.com/mrss"
          xmlns:atom="http://www.w3.org/2005/Atom">
            <channel>
            """ + flat.flatten(items) + """
            </channel>
        </rss>
        """
