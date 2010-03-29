"""
todo:
fix rss paging
fix rss on /set pages
split server into per-set and per-image services
separate all security checks into their own module
next/prev day pickers
calendar view
similarity grouping
email pic or set
download from flickr
ocr and search, like http://norman.walsh.name/2009/11/01/evernote
"""
from __future__ import division
import logging, zipfile, datetime, time, jsonlib, cgi, urllib, random
from StringIO import StringIO
from nevow import loaders, rend, tags as T, inevow, url
from rdflib import Namespace, Variable, URIRef, RDF, RDFS, Literal
from zope.interface import implements
from twisted.python.components import registerAdapter, Adapter
from twisted.web.client import getPage
from xml.utils import iso8601
from isodate.isodates import parse_date, date_isoformat
from photos import Full, thumb, sizes
from urls import localSite, absoluteSite
from public import isPublic
from edit import writeStatements
from oneimage import personAgeString
from search import randomSet, nextDateWithPics
import tagging
import auth
log = logging.getLogger()
PHO = Namespace("http://photo.bigasterisk.com/0.1/")
SITE = Namespace("http://photo.bigasterisk.com/")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")
EXIF = Namespace("http://www.kanzaki.com/ns/exif#")
SCOT = Namespace("http://scot-project.org/scot/ns#")
DC = Namespace("http://purl.org/dc/elements/1.1/")
XS = Namespace("http://www.w3.org/2001/XMLSchema#")


## class StringIOView(Adapter):
##     implements(inevow.IResource)
##     def locateChild(ctx, segments):
##         return None, []
##     def renderHTTP(self, ctx):
##         return str(self.original.getvalue())
## try: registerAdapter(StringIOView, StringIO, inevow.IResource)
## except ValueError: pass


def photosWithTopic(graph, uri):
    """photos can be related to uri in a variety of ways: foaf:depicts,
    dc:date, etc"""
    q = graph.queryd("""SELECT DISTINCT ?photo WHERE {
                               {
                                 ?photo foaf:depicts ?u .
                               } UNION {
                                 ?photo pho:inDirectory ?u .
                               } UNION {
                                 ?photo scot:hasTag ?u .
                               } UNION {
                                 ?photo dc:date ?u .
                               }
                              # ?photo pho:viewableBy pho:friends .
                             }""",
                          initBindings={Variable('u') : uri})

    return sorted([row['photo'] for row in q])    

class ImageSet(rend.Page):
    """
    multiple images, with one currently-featured one. Used for search results
    """
    docFactory = loaders.xmlfile("imageSet.html")
    def __init__(self, ctx, graph, uri, **kw):
        self.graph, self.uri = graph, uri
        if uri == PHO.randomSet:
            self.photos = [r['pic'] for r in
                           randomSet(graph, kw.get('randomSize', 10),
                                     seed=kw.get('seed', None))]
            self.setLabel = 'random choices'
        else:
            self.photos = photosWithTopic(self.graph, self.uri)
        self.currentPhoto = None
        if ctx.arg('current') is not None:
            self.currentPhoto = URIRef(ctx.arg('current'))

        if not self.photos and self.currentPhoto:
            print "featuring one pic"
            self.photos = [self.currentPhoto]

        if self.photos and self.currentPhoto not in self.photos:
            self.currentPhoto = self.photos[0]

    def render_setLabel(self, ctx, data):

        if self.graph.contains((self.uri, RDF.type, PHO.DiskDirectory)):
            return ["directory ", self.graph.value(self.uri, PHO.filename)]

        if hasattr(self, 'setLabel'):
            return self.setLabel

        if isinstance(self.uri, Literal):
            return self.uri
        
        return self.graph.label(self.uri)
                
    def otherImageHref(self, ctx, img):
        href = url.here.add("current", img)
        for topicKey in ['dir', 'tag', 'date', 'random', 'seed']:
            if ctx.arg(topicKey):
                href = href.add(topicKey, ctx.arg(topicKey))
        return href

    def render_currentPhotoUri(self, ctx, data):
        return self.currentPhoto

    def renderHTTP(self, ctx):
        req = inevow.IRequest(ctx)
        if req.method == 'POST':
            if ctx.arg('tagRange'):
                return self.postTagRange(ctx)
            raise ValueError("unknown action")
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

    def postTagRange(self, ctx):
        # security?
        
        i1 = self.photos.index(URIRef(ctx.arg('start')))
        i2 = self.photos.index(URIRef(ctx.arg('end')))

        newUri = URIRef(ctx.arg('uri'))

        imgStatements = [(img, FOAF.depicts, newUri)
                         for img in self.photos[i1:i2+1]]

        writeStatements([
            (newUri, RDF.type, URIRef(ctx.arg('rdfClass'))),
            #(newUri, DC.created, Literal now
            (newUri, RDFS.label, Literal(ctx.arg('label'))),
            ] + imgStatements)

        return jsonlib.dumps({
            "msg": "tagged %s images: <a href=\"%s\">view your new set</a>" %
            (len(imgStatements), newUri)
            })

    def render_loginWidget(self, ctx, data):
        return getPage("http://bang:9023/_loginBar", headers={
            "Cookie" : inevow.IRequest(ctx).getHeader("cookie") or ''}
                       ).addCallback(T.raw)
        
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
    
    def render_currentLabel(self, ctx, data):
        if self.currentPhoto is None:
            return ''
        return self.graph.label(self.currentPhoto,
                                # keep the title line taking up space
                                # so the image doesn't bounce around
                                # when there's no title
                                default=T.raw("&nbsp;"))

    def data_related(self, ctx, data):
        if self.currentPhoto is None:
            return


        def relQuery(rel):
            rows = self.graph.queryd("""
               SELECT DISTINCT ?d ?label WHERE {
                 ?img ?rel ?d .
                 OPTIONAL { ?d rdfs:label ?label }
               }""", initBindings={Variable("rel") : rel,
                                   Variable("img") : self.currentPhoto})
            for r in rows:
                if 'label' not in r:
                    r['label'] = r['d']
                yield r

        def setUrl(**params):
            params['current'] = self.currentPhoto
            return ('/set?' +
                    urllib.urlencode(params))

        for row in relQuery(FOAF.depicts):
            yield ('depicting', row['d'], row['label'])

        for row in relQuery(PHO.inDirectory):
            yield ('in directory', setUrl(dir=row['d']),
                   row['d'].split('/')[-2])

        for row in relQuery(DC.date):
           
            yield ('taken on', setUrl(date=row['d']), row['d'])

        for row in relQuery(SCOT.hasTag):
            yield ('with tag', setUrl(tag=row['label']), row['label'])

        # taken near xxxxx

    
    def data_photosInSet(self, ctx, data):
        return self.photos
    
    def render_thumb(self, ctx, data):
        cls = "not-current"
        thisThumbSrc = localSite(data)
        if data == self.currentPhoto:
            cls = "current"
            return T.span[
                T.img(class_=cls, src=[thisThumbSrc, "?size=thumb"]),
                ]

        return T.span[
            T.a(href=self.otherImageHref(ctx, data))[
            T.img(class_=cls, src=[thisThumbSrc, "?size=thumb"])]]

    def render_featured(self, ctx, data):
        if self.currentPhoto is None:
            return ''
        currentLocal = localSite(self.currentPhoto)
        _, next = self.prevNext()
        return T.a(href=self.otherImageHref(ctx, next))[
            T.img(src=[currentLocal, "?size=large"],
                  alt=self.graph.label(self.currentPhoto))]

    def render_stepButtons(self, ctx, data):
        p, n = self.prevNext()
        
        return T.div(class_="steps")[
            T.a(href=self.otherImageHref(ctx, p),
                title="Previous image (left arrow key)")[T.raw('&#11013;')], ' ',
            "change image",
            T.a(href=self.otherImageHref(ctx, n),
                title="Next image (click in the image, or press right arrow key)")[
                T.raw('&#10145;')],
            ]


    def render_prevNextDateButtons(self, ctx, data):
        showingDate = ctx.arg('date')
        if showingDate is None:
            if self.currentPhoto is None:
                return ''
                
            rows = self.graph.queryd("""
                   SELECT ?d ?label WHERE {
                     ?img dc:date ?d .
                   }""", initBindings={Variable("img") : self.currentPhoto})
            if not rows:
                return ''
            showingDate = rows[0]['d']
        
        dtd = parse_date(showingDate)
        try:
            prevDate = date_isoformat(nextDateWithPics(
                self.graph, dtd, -datetime.timedelta(days=1)))
            prev = T.a(href='/set?date=%s' % prevDate)[
                prevDate, T.raw(' &#8672;')]
        except ValueError:
            prev = ""

        try:
            nextDate = date_isoformat(nextDateWithPics(
                self.graph, dtd, datetime.timedelta(days=1)))
            next = T.a(href='/set?date=%s' % nextDate)[
                T.raw('&#8674; '), nextDate]
        except ValueError:
            next = ""
            
        return T.div(class_="dateChange")[
            prev,
            ' change date ',
            next]

    def prevNext(self):
        if self.currentPhoto is None:
            return None, None
        i = self.photos.index(self.currentPhoto)
        return (self.photos[max(0, i - 1)],
                self.photos[min(len(self.photos) - 1, i + 1)])

    def render_nextImagePreload(self, ctx, data):
        _, nextImg = self.prevNext()
        if nextImg is None:
            return ''
        return [localSite(nextImg), "?size=large"]

    def render_zipUrl(self, ctx, data):
        return [self.uri, "?archive=zip"]

    def render_link(self, ctx, data):
        src = [self.currentPhoto, '?size=large']
        return '<img src="', T.a(href=src)[src], '"/>'

    def render_otherSizeLinks(self, ctx, data):
        if self.currentPhoto is None:
            return ''
        
        return [[T.a(href=[localSite(self.currentPhoto), "?size=", s])[
            str(sizes[s]) if sizes[s] != Full else "Original"], " "]
                for s in 'medium', 'large', 'screen', 'full']

    def render_prevNextJs(self, ctx, data):
        prev, next = self.prevNext()
        
        return ctx.tag['var arrowPages = {prev : "',
                       self.otherImageHref(ctx, prev),'", next : "',
                       self.otherImageHref(ctx, next),'"}']

    def render_actionsAllowed(self, ctx, data):
        """should the actions section be displayed"""
        openid = inevow.IRequest(ctx).getHeader('x-openid-proxy')
        if openid is not None and URIRef(openid) in auth.superusers:
            return ctx.tag
        return ''

    def render_allowedToWriteMeta(self, ctx, data):
        agent = inevow.IRequest(ctx).getHeader('x-foaf-agent')
        if agent is not None and tagging.allowedToWrite(self.graph, URIRef(agent)):
            return ctx.tag
        return ''

    def render_uploadButton(self, ctx, data):
        if self.currentPhoto is None:
            return ''
        openid = inevow.IRequest(ctx).getHeader('x-openid-proxy')
        copy = self.graph.value(self.currentPhoto, PHO.flickrCopy)
        if copy is not None:
            # this html is a port of the same thing in imageSet.html
            return T.span(id="flickrUpload")[T.a(href=copy)["flickr copy"]]

        if openid is not None and URIRef(openid) in auth.superusers:
            return T.div(id="flickrUpload")[
                T.div[T.button(onclick="flickrUpload()")['Upload to flickr']],
                T.div[T.input(type="radio", name="size", value="large", id="ful",
                        checked="checked"),
                T.label(for_="ful")["large (fast)"]],
                T.div(style="opacity: .5")[
                T.input(type="radio", name="size", value="full size", id="fuf"),
                T.label(for_="fuf")["full (2+ min) ",
           T.a(href="http://www.flickr.com/help/photos/#89", style="font-size: 60%")["do not use full; flickr won't give you access to your own pic"]]]]
        
        return ''

    def render_tagListJs(self, ctx, data):
        freqs = tagging.getTagsWithFreqs(self.graph)
        return "var allTags=" + jsonlib.dumps(freqs.keys()) + ";"


    def render_public(self, ctx, data):
        # becomes a call to oneimage/viewPerm\
        
        if isPublic(self.graph, self.currentPhoto):
            return 'image is public'
        
        return T.button(class_="makePub")["Make public"]

    def render_facts(self, ctx, data):
        # todo: if user doesnt have perms to see the photo, he
        # shouldnt be able to see facts or tags either
        
        img = self.currentPhoto
        if img is None:
            return ''

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

        ago = int((now - sec) / 86400)
        if ago < 365:
            ago = '; %s days ago' % ago
        else:
            ago = ''
        lines.append("Picture taken %s%s" % (photoDate.replace('T', ' '), ago))

        for who, tag, birthday in [
            (URIRef("http://photo.bigasterisk.com/2008/person/apollo"),
            'apollo',
             '2008-07-22'),
            (URIRef("http://bigasterisk.com/foaf.rdf#drewp"),
             'drew', '1900-01-01'),
            ]:
            try:
                tag = URIRef('http://photo.bigasterisk.com/tag/%s' % tag)
                if (self.graph.contains((img, FOAF['depicts'], who)) or
                    self.graph.contains((img, SCOT.hasTag, tag))):
                    name = self.graph.value(
                        who, FOAF.name, default=self.graph.label(
                            who, default=tag))
                        
                    lines.append("%s is %s old. " % (
                        name, personAgeString(birthday, photoDate)))
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
        for pic in self.photos[-20:]: # no plan yet for the range. use paging i guess
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
          
class RandomImage(rend.Page):
    """redirect to any image with this topic.

    If you are making am XHR, we give you a {'Location' : 'http:...'}
    payload instead, so you can know what the image url turns out to
    be. But you have to put that location into the <img> tag yourself."""
    def __init__(self, graph, uri, ctx):
        self.graph, self.uri, self.ctx = graph, uri, ctx
        
    def renderHTTP(self, ctx):
        photos = photosWithTopic(self.graph, self.uri)

        newUrl = url.URL.fromString(str(random.choice(photos)))

        # todo: this should carry all args (except 'random')
        if ctx.arg('size'):
            newUrl = newUrl.add('size', ctx.arg('size'))

        req = inevow.IRequest(ctx)
        # XHR requests can't get the location; the redirect happens
        # automatically. So give them a payload and no location
        # header.
        if req.getHeader('X-Requested-With') == 'XMLHttpRequest':
            req.setHeader('content-type', 'application/json')
            return jsonlib.dumps({'Location' : str(newUrl)})
        
        req.redirect(newUrl)
        return ''
