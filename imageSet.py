from __future__ import division
import logging, zipfile, datetime, time
from StringIO import StringIO
from nevow import loaders, rend, tags as T, inevow, url
from rdflib import Namespace, Variable, URIRef, RDF
from zope.interface import implements
from twisted.python.components import registerAdapter, Adapter
from xml.utils import iso8601
from photos import Full, thumb
from urls import localSite, absoluteSite
import auth
log = logging.getLogger()
PHO = Namespace("http://photo.bigasterisk.com/0.1/")
SITE = Namespace("http://photo.bigasterisk.com/")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")
EXIF = Namespace("http://www.kanzaki.com/ns/exif#")


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
        q = self.graph.queryd("""SELECT DISTINCT ?photo WHERE {
                                   {
                                     ?photo foaf:depicts ?u .
                                   } UNION {
                                     ?photo pho:inDirectory ?u .
                                   } UNION {
                                     ?photo pho:tag ?u . # retire this line
                                   } UNION {
                                     ?photo scot:hasTag ?u .
                                   }
                                  # ?photo pho:viewableBy pho:friends .
                                 }""",
                              initBindings={Variable('u') : self.uri})

        self.photos = sorted([row['photo'] for row in q])

        if not self.photos:
            raise ValueError("No photos found for %s" % uri)

        self.currentPhoto = URIRef(ctx.arg('current'))
        if self.currentPhoto not in self.photos:
            self.currentPhoto = self.photos[0]

    def render_currentPhotoUri(self, ctx, data):
        return self.currentPhoto

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

    def render_loginWidget(self, ctx, data):
        openid = inevow.IRequest(ctx).getHeader('x-openid-proxy')
        if openid is None:
            return T.a(href='/login')["Login"]
        
        openid = URIRef(openid)
        return "Logged in as %s" % openid

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

        if self.graph.contains((self.uri, RDF.type, PHO.DiskDirectory)):
            return ["directory ", self.graph.value(self.uri, PHO.filename)]
        
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
            T.a(href=self.otherImageHref(ctx, data))[
            T.img(class_=cls, src=[thisThumbSrc, "?size=thumb"])]]

    def otherImageHref(self, ctx, img):
        href = url.here.add("current", img)
        for topicKey in ['dir', 'tag']:
            if ctx.arg(topicKey):
                href = href.add(topicKey, ctx.arg(topicKey))
        return href

    def render_featured(self, ctx, data):
        currentLocal = localSite(self.currentPhoto)
        _, next = self.prevNext()
        return T.a(href=self.otherImageHref(ctx, next))[
            T.img(src=[currentLocal, "?size=large"],
                  alt=self.graph.label(self.currentPhoto))]

    def prevNext(self):
        i = self.photos.index(self.currentPhoto)
        return (self.photos[max(0, i - 1)],
                self.photos[min(len(self.photos) - 1, i + 1)])

    def render_nextImagePreload(self, ctx, data):
        _, next = self.prevNext()
        return T.img(class_='preload', src=[localSite(next), "?size=large"])

    def render_zipUrl(self, ctx, data):
        return [self.uri, "?archive=zip"]

    def render_link(self, ctx, data):
        src = [self.currentPhoto, '?size=large']
        return '<img src="', T.a(href=src)[src], '"/>'

    def render_fullSizeLink(self, ctx, data):
        return T.a(href=[localSite(self.currentPhoto), "?size=full"])[ctx.tag]

    def render_prevNextJs(self, ctx, data):
        prev, next = self.prevNext()
        
        return ctx.tag['var arrowPages = {prev : "',
                       self.otherImageHref(ctx, prev),'", next : "',
                       self.otherImageHref(ctx, next),'"}']


    def render_uploadButton(self, ctx, data):
         openid = inevow.IRequest(ctx).getHeader('x-openid-proxy')
         if openid is not None and URIRef(openid) in auth.superusers:
             return [T.button(onclick="flickrUpload()")['Upload to flickr / do not use this yet'],
                     T.span(id="flickrUploadStatus")]
         return ''

    def render_facts(self, ctx, data):
        img = self.currentPhoto

        now = time.time()
        lines = []

        try:
            photoDate = self.graph.value(img, EXIF.dateTime)
            try:
                sec = iso8601.parse(str(photoDate))
            except Exception:
                sec = iso8601.parse(str(photoDate) + '-0700')
        except ValueError:
            return ''
        
        lines.append("Picture taken %s; %s days ago" %
                     (photoDate.replace('T', ' '), int((now - sec) / 86400)))

        for who, tag, birthday in [
            (URIRef("http://photo.bigasterisk.com/2008/person/apollo"),
            'apollo',
             '2008-07-22'),
            (URIRef("http://bigasterisk.com/foaf.rdf#drewp"),
             'drew', '1900-01-01'),
            ]:
            try:
                if (self.graph.contains((img, FOAF['depicts'], who)) or
                    self.graph.contains((img, PHO.tag,
                         URIRef('http://photo.bigasterisk.com/tag/%s' % tag)))):
                    birth = iso8601.parse(birthday)
                    diff = sec - birth
                    days = (sec - birth) / 86400
                    if days / 30 < 15:
                        msg = "%.2f months" % (days / 30)
                    else:
                        msg = "%.2f years" % (days / 365)
                    name = self.graph.value(
                        who, FOAF.name, default=self.graph.label(
                            who, default=tag))
                    lines.append("%s is %s old. " % (name, msg))
            except Exception, e:
                log.error("%s birthday failed: %s" % (who, e))


        # 'used in this blog entry'
                
        return T.ul[[T.li[x] for x in lines]]
    
    def photoRss(self, ctx):
        request = inevow.IRequest(ctx)

        # this should be making atom!
        # it needs to return the most recent pics, with a link to the next set!

        # copied from what flickr emits
        request.setHeader("Content-Type", "text/xml; charset=utf-8")

        items = [T.Tag('title')["bigasterisk %s photos" % self.graph.label(self.uri)]]
        for pic in self.photos:
            items.append(T.Tag('item')[
                T.Tag('title')[self.graph.label(pic, default=pic.split('/')[-1])],
                T.Tag('link')[absoluteSite(pic) + '?size=screen'],
                T.Tag('description')[
                  '<a href="%s"><img src="%s" /></a>' %
                  (absoluteSite(pic) + '?size=large',
                   absoluteSite(pic) + '?size=thumb')],
                T.Tag('media:thumbnail')(url=absoluteSite(pic) + '?size=small'),
                T.Tag('media:content')(url=absoluteSite(pic) + '?size=screen'),
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
          
