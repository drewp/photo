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
import logging, zipfile, datetime, jsonlib, urllib, random, time, traceback
from StringIO import StringIO
from nevow import loaders, rend, tags as T, inevow, url
from rdflib import Namespace, Variable, URIRef, RDF, RDFS, Literal
from zope.interface import implements
from twisted.python.components import registerAdapter, Adapter
from twisted.internet.defer import inlineCallbacks, returnValue, DeferredList
from twisted.web.client import getPage
from isodate.isodates import parse_date, date_isoformat
from photos import Full, thumb, sizes
from urls import localSite, absoluteSite
from imageurl import ImageSetDesc, photosWithTopic
from edit import writeStatements
from search import nextDateWithPics
import tagging, networking
import auth
from access import getUser, accessControlWidget
from lib import print_timing
log = logging.getLogger()
PHO = Namespace("http://photo.bigasterisk.com/0.1/")
SITE = Namespace("http://photo.bigasterisk.com/")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")
EXIF = Namespace("http://www.kanzaki.com/ns/exif#")
SCOT = Namespace("http://scot-project.org/scot/ns#")
DC = Namespace("http://purl.org/dc/elements/1.1/")
DCTERMS = Namespace("http://purl.org/dc/terms/")
XS = Namespace("http://www.w3.org/2001/XMLSchema#")


## class StringIOView(Adapter):
##     implements(inevow.IResource)
##     def locateChild(ctx, segments):
##         return None, []
##     def renderHTTP(self, ctx):
##         return str(self.original.getvalue())
## try: registerAdapter(StringIOView, StringIO, inevow.IResource)
## except ValueError: pass

@print_timing
def photoDate(graph, img):
    for q in [
        """SELECT ?d ?label WHERE {
             ?img dc:date ?d .
           }""",
        """SELECT ?d ?label WHERE {
             ?img dcterms:date ?d .
           }""",
        """SELECT ?d ?label WHERE {
             ?email a pho:Email ; dcterms:created ?d ; dcterms:hasPart ?img .
           }""",
        
        ]:
        log.info("photodate query: %s", q.replace("\n", " "))
        rows = graph.queryd(q, initBindings={"img" : img})
        if rows:
            break
    else:
        raise ValueError("can't find date for %r" % img)

    log.info("found %s date row matches", len(rows))
    return rows[0]['d']


class ImageSet(rend.Page):
    """
    multiple images, with one currently-featured one. Used for search results
    """
    docFactory = loaders.xmlfile("imageSet.html")
    @print_timing
    def __init__(self, ctx, graph, uri, **kw):
        """
        uri is the whole page load (relative) uri
        """
        self.graph, self.uri = graph, uri
        agent = getUser(ctx)

        self.desc = desc = ImageSetDesc(graph, agent, uri)
        self.topic = desc.topic
        self.photos = desc.photos()
        self.currentPhoto = desc.currentPhoto()
        
    @inlineCallbacks
    def render_picInfoJson(self, ctx, data):
        # vars for the javascript side to use
        if self.currentPhoto is None:
            returnValue("{}")
        results = yield DeferredList([
            serviceCall(ctx, 'links', self.currentPhoto),
            serviceCall(ctx, 'facts', self.currentPhoto),
            serviceCall(ctx, 'tags', self.currentPhoto)])

        def readOrError(js):
            try:
                return jsonlib.read(js)
            except Exception, e:
                log.error(traceback.format_exc())
                return jsonlib.write({'error' : str(e)})

        ret = jsonlib.write(dict(
            relCurrentPhotoUri=localSite(self.currentPhoto),
            currentPhotoUri=self.currentPhoto,
            links=readOrError(results[0][1]),
            facts=readOrError(results[1][1]),
            tags=readOrError(results[2][1]),
            ))
        returnValue(ret)
        
    def render_setLabel(self, ctx, data):
        return self.desc.label()
                
    def otherImageHref(self, ctx, img):
        return self.desc.otherImageUrl(img)

    def render_standardSite(self, ctx, data):
        return T.a(href=self.otherImageHref(ctx, self.currentPhoto).replace('tablet', '0'))[
            "Standard site"]

    def render_storyModeUrl(self, ctx, data):
        # only works on topic?edit=1 urls, not stuff like
        # set?tag=foo. error message is poor.
        return url.here.clear('edit')

    def render_rssHref(self, ctx, img):
        href = self.otherImageHref(ctx, img)
        return href.remove('current').add('rss', '1')

    def renderHTTP(self, ctx):
        req = inevow.IRequest(ctx)

        if req.getHeader('accept') == 'application/json': # approximage parse
            return self.jsonContent()
        
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

    def jsonContent(self):
        return jsonlib.write({'photos' : self.photos})

    def postTagRange(self, ctx):
        # security?
        
        i1 = self.photos.index(URIRef(ctx.arg('start')))
        i2 = self.photos.index(URIRef(ctx.arg('end')))

        newUri = URIRef(ctx.arg('uri'))

        imgStatements = [(img, FOAF.depicts, newUri)
                         for img in self.photos[i1:i2+1]]
        if (ctx.arg('label') or '').strip():
            imgStatements.append((newUri, RDFS.label, Literal(ctx.arg('label'))))
        writeStatements([
            (newUri, RDF.type, URIRef(ctx.arg('rdfClass'))),
            #(newUri, DC.created, Literal now
            ] + imgStatements)

        return jsonlib.dumps({
            "msg": "tagged %s images: <a href=\"%s\">view your new set</a>" %
            (len(imgStatements), newUri)
            })

    def render_loginWidget(self, ctx, data):
        return networking.getLoginBar(inevow.IRequest(ctx).getHeader("cookie") or '').addCallback(T.raw)

    def render_aclWidget(self, ctx, data):
        if not self.currentPhoto:
            return ''
        import access
        reload(access)
        return T.raw(access.accessControlWidget(self.graph, getUser(ctx),
                                                self.currentPhoto))
    def render_setAclWidget(self, ctx, data):
        """
        access for the whole displayed set
        """
        import access
        reload(access)
        req = inevow.IRequest(ctx)
        return T.raw(access.accessControlWidget(
            self.graph, getUser(ctx),
            self.desc.canonicalSetUri()))
        
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

        downloadFilename = self.topic.split('/')[-1] + ".zip"
        request.setHeader("Content-Disposition",
                          "attachment; filename=%s" %
                          downloadFilename.encode('ascii'))

        return f.getvalue()
        
    def render_title(self, ctx, data):
        # why not setLabel?
        return self.graph.label(self.topic)

    def render_intro(self, ctx, data):
        intro = self.graph.value(self.topic, PHO['intro'])
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
    
    def data_photosInSet(self, ctx, data):
        return self.photos
    
    def render_thumb(self, ctx, data):
        thisThumbSrc = localSite(data)
        if data == self.currentPhoto:
            cls = "current"
            wrap = lambda x: x
        else:
            cls = "not-current"
            wrap = lambda x: T.a(href=self.otherImageHref(ctx, data))[x]

        # if we think the client already has the thumb in-cache, it is
        # poor to use delaysrc here.
        return T.span[wrap(T.img(class_=cls,
                                 #src="/static/loading.jpg",
                                 src=[thisThumbSrc, "?size=thumb"]
                                 ))]

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


    @print_timing
    def render_prevNextDateButtons(self, ctx, data):
        showingDate = ctx.arg('date')
        if showingDate is None:
            if self.currentPhoto is None:
                return ''

            try:
                showingDate = photoDate(self.graph, self.currentPhoto)
            except ValueError:
                return ''
        
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
        return [self.topic, "?archive=zip"]

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

    def render_recentLinks(self, ctx, data):
        choices = []
        for opt in [10, 50, 100]:
            url = self.desc.altUrl(recent=str(opt))
            choices.append(T.a(href=url)[opt])
        choices.append(T.a(href=self.desc.altUrl(recent=''))['all'])
        return ['show only the ', [[c, ' '] for c in choices],
                ' most recent of these']

    def render_actionsAllowed(self, ctx, data):
        """should the actions section be displayed"""
        agent = getUser(ctx)
        if agent is not None and agent in auth.superagents:
            return ctx.tag
        return ''

    def render_allowedToWriteMeta(self, ctx, data):
        agent = getUser(ctx)
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

    def render_sflyUploadButton(self, ctx, data):
        return T.button(onclick="sflyUpload()")["Upload to ShutterFly"]

    @print_timing
    def render_tagListJs(self, ctx, data):
        freqs = tagging.getTagsWithFreqs(self.graph)
        return "var allTags=" + jsonlib.dumps(freqs.keys()) + ";"

    def render_bestJqueryLink(self, ctx, data):
        req = inevow.IRequest(ctx)
        ip = req.getHeader('x-forwarded-for')
        if ip and ip.startswith(('10.1', '192.168')):
            # if local wifi users got routed through my squid cache,
            # this would be unnecessary, as I would have a local cache
            # of the google copy
            src = "/static/jquery-1.4.2.min.js"
        else:
            src = "http://ajax.googleapis.com/ajax/libs/jquery/1.4.2/jquery.min.js"
        return T.script(type='text/javascript', src=src)
    
    def render_starLinkAll(self, ctx, data):
        if ctx.arg('star') is None:
            return ''
        else:
            return T.a(href=self.desc.altUrl(star='all'))[ctx.tag]
    def render_starLinkOnly(self, ctx, data):
        if ctx.arg('star') == 'only':
            return ''
        else:
            return T.a(href=self.desc.altUrl(star='only'))[ctx.tag]
    
    def photoRss(self, ctx):
        request = inevow.IRequest(ctx)

        # this should be making atom!
        # it needs to return the most recent pics, with a link to the next set!

        # copied from what flickr emits
        request.setHeader("Content-Type", "text/xml; charset=utf-8")

        items = [T.Tag('title')["bigasterisk %s photos" % self.graph.label(self.topic)]]
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

def serviceCall(ctx, name, uri):
    """
    deferred to result of calling this internal service on the image
    uri. user credentials are passed on
    """
    t1 = time.time()
    def endTime(result):
        log.info("service call %r in %.01f ms", name, 1000 * (time.time() - t1))
        return result
    return getPage(str('%s?uri=%s' % (networking.serviceUrl(name),
                                      urllib.quote(uri, safe=''))),
            headers={'x-foaf-agent' : str(getUser(ctx)),
                       }).addCallback(endTime)

class ImageSetTablet(ImageSet):
    docFactory = loaders.xmlfile("tablet.html")
          
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
