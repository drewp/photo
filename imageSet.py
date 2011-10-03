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
import logging, zipfile, datetime, json, urllib, random, time, traceback, simplejson, restkit
from StringIO import StringIO
from nevow import loaders, rend, tags as T, inevow, url, flat
from rdflib import URIRef, Literal
from zope.interface import implements
from twisted.python.components import registerAdapter, Adapter
from twisted.internet.defer import inlineCallbacks, returnValue, DeferredList
from twisted.web.client import getPage
from isodate.isodates import parse_date, date_isoformat
from photos import Full, thumb, sizes, getSize
from urls import localSite, absoluteSite
from imageurl import ImageSetDesc, photosWithTopic, NoSetUri
from edit import writeStatements
from search import nextDateWithPics
import tagging, networking
import auth, access
from access import getUser
from shorturl import hasShortUrlSync
from lib import print_timing
from scanFs import videoExtensions
log = logging.getLogger()
from ns import PHO, FOAF, RDF, RDFS
import pystache.view # needs a git version newer than 0.3.1. easy_install https://github.com/defunkt/pystache/tarball/f543efac93b753914a20b9daaf84a51382fba445 or newer. Then you need to remove a patch if https://github.com/defunkt/pystache/issues/25 hasn't been addressed already

@print_timing
def photoDate(graph, img):
    for q in [
        """SELECT ?d WHERE {
             ?img dc:date ?d .
           }""",
        """SELECT ?d WHERE {
             ?img dcterms:date ?d .
           }""",
        """SELECT ?d WHERE {
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

        self.desc = ImageSetDesc(graph, agent, uri)

    @print_timing
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

        ret = View(self.graph, self.desc,
                   params=dict(date=ctx.arg('date'), star=ctx.arg('star')),
                   cookie=req.getHeader("cookie") or '',
                   agent=getUser(ctx),
                   openidProxyHeader=req.getHeader('x-openid-proxy'),
                   forwardedFor=req.getHeader('x-forwarded-for')).render()
        req.setHeader("Content-Type", "application/xhtml+xml")
        return ret.encode('utf8')

class View(pystache.view.View):
    template_name = "imageSet"

    def __init__(self, graph, desc, params, cookie, agent,
                 openidProxyHeader, forwardedFor):
        pystache.view.View.__init__(self)
        self.graph = graph
        self.desc = desc
        self.params, self.cookie, self.agent = params, cookie, agent
        self.openidProxyHeader = openidProxyHeader
        self.forwardedFor = forwardedFor

    def title(self):
        # why not setLabel?
        return self.graph.label(self.desc.topic)
        
    def bestJqueryLink(self):
        return networking.jqueryLink(self.forwardedFor)
        
    def setLabel(self):
        return self.desc.label()

    def storyModeUrl(self):
        # only works on topic?edit=1 urls, not stuff like
        # set?tag=foo. error message is poor.

        # need something on desc
        return url.here.clear('edit')

    def intro(self):
        intro = self.graph.value(self.desc.topic, PHO['intro'])
        if intro is not None:
            intro = intro.replace(r'\n', '\n') # rdflib parse bug?
            return {'html' : intro}
        else:
            return ''

    def currentLabel(self):
        if self.desc.currentPhoto() is None:
            return ''
        return self.graph.label(self.desc.currentPhoto(),
                                # keep the title line taking up space
                                # so the image doesn't bounce around
                                # when there's no title
                                default=None)

    def prevNextDateButtons(self):
        showingDate = self.params['date']
        if showingDate is None:
            if self.desc.currentPhoto() is None:
                return ''

            try:
                showingDate = photoDate(self.graph, self.desc.currentPhoto())
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
            
        return flat.flatten(T.div(class_="dateChange")[
            prev,
            ' change date ',
            next])

    def stepButtons(self):
        p, n = self.prevNext()
        return dict(p=self.desc.otherImageUrl(p),
                    n=self.desc.otherImageUrl(n))

    def featured(self):
        current = self.desc.currentPhoto()
        if current is None:
            return ''
        currentLocal = localSite(current)
        _, nextUri = self.prevNext()
        if self.graph.contains((current, RDF.type, PHO.Video)):
            return dict(video=dict(src=currentLocal+"?size=video2"))
        else:
            try:
                size = getSize(current, sizes["large"])
            except (ValueError, IOError):
                size = (0,0)
            marg = (600 - 2 - size[0]) // 2
            return dict(image=dict(
                nextClick=self.desc.otherImageUrl(nextUri),
                src=currentLocal+"?size=large",
                w=size[0], h=size[1],
                marg=marg,
                alt=self.graph.label(current),
                ))

    def loginWidget(self):
        return networking.getLoginBarSync(self.cookie)

    def actionsAllowed(self):
        """should the actions section be displayed"""
        return self.agent is not None and self.agent in auth.superagents

    @print_timing
    def aclWidget(self):
        if not self.desc.currentPhoto():
            return ''
        import access
        reload(access)
        return access.accessControlWidget(self.graph, self.agent,
                                          self.desc.currentPhoto()).decode('utf8')

    def uploadButton(self):
        if self.desc.currentPhoto() is None:
            return ''
        copy = self.graph.value(self.desc.currentPhoto(), PHO.flickrCopy)
        if copy is not None:
            # this html is a port of the same thing in imageSet.html
            return flat.flatten(T.span(id="flickrUpload")[T.a(href=copy)["flickr copy"]])

        if self.openidProxyHeader is not None and URIRef(self.openidProxyHeader) in auth.superusers:
            return flat.flatten(T.div(id="flickrUpload")[
                T.div[T.button(onclick="flickrUpload()")['Upload to flickr']],
                T.div[T.input(type="radio", name="size", value="large", id="ful",
                        checked="checked"),
                T.label(for_="ful")["large (fast)"]],
                T.div(style="opacity: .5")[
                T.input(type="radio", name="size", value="full size", id="fuf"),
                T.label(for_="fuf")["full (2+ min) ",
           T.a(href="http://www.flickr.com/help/photos/#89", style="font-size: 60%")["do not use full; flickr won't give you access to your own pic"]]]])
        
        return ''

    @print_timing
    def publicShareButton(self):
        if self.desc.currentPhoto() is None:
            return ''

        # not absoluteSite() here, since i didn't want to make
        # separate shortener entries for test sites and the real one
        target = self.desc.currentPhoto()+"/single"
        if access.viewable(self.graph, self.desc.currentPhoto(), FOAF.Agent):
            short = hasShortUrlSync(target)
            if short:
                return flat.flatten(T.a(href=short)["Public share link"])
        return flat.flatten(T.button(onclick="makePublicShare()")["Make public share link"])

    def otherSizeLinks(self):
        if self.desc.currentPhoto() is None:
            return []
        return [
            dict(href="%s?size=%s" % (localSite(self.desc.currentPhoto()), s),
                 label=str(sizes[s]) if sizes[s] != Full else "Original")
            for s in 'medium', 'large', 'screen', 'full']

    def link(self):
        current = self.desc.currentPhoto()
        if current is None:
            return None
        if self.graph.contains((current, RDF.type, PHO.Video)):
            return dict(video=dict(uri=current + '?size=video2'))
        # should put sizes in this link(s)
        return dict(image=dict(uri=current + '?size=large'))

    def allowedToWriteMeta(self):
        return (self.agent is not None and
                tagging.allowedToWrite(self.graph, self.agent))

    @print_timing
    def setAclWidget(self):
        """
        access for the whole displayed set
        """
        try:
            setUri = self.desc.canonicalSetUri()
        except NoSetUri:
            return ''
        import access
        reload(access)
        return T.raw(access.accessControlWidget(
            self.graph, self.agent,
            setUri)).decode('utf8')
   
    def starLinkAll(self):
        if self.params['star'] is None:
            return ''
        else:
            return dict(href=self.desc.altUrl(star='all'))

    def starLinkOnly(self):
        if self.params['star'] == 'only':
            return ''
        else:
            return dict(href=self.desc.altUrl(star='only'))

    def recentLinks(self):
        raise NotImplementedError
        choices = []
        for opt in [10, 50, 100]:
            url = self.desc.altUrl(recent=str(opt))
            choices.append(T.a(href=url)[opt])
        choices.append(T.a(href=self.desc.altUrl(recent=''))['all'])
        return ['show only the ', [[c, ' '] for c in choices],
                ' most recent of these']

    @print_timing
    def photosInSet(self):
        uris = self.desc.photos()

        @print_timing
        def _isVideo():
            return dict(zip(uris,
                     fastAsk(self.graph, [(uri, RDF.type, PHO.Video)
                                          for uri in uris])))
        isVideo = _isVideo()

        def _thumb(data):
            thisThumbSrc = localSite(data)
            if data == self.desc.currentPhoto():
                cls = "current"
                wrap = lambda x: x
            else:
                cls = "not-current"
                wrap = lambda x: T.a(href=self.desc.otherImageUrl(data))[x]

            if isVideo[data]:
                cls += " video"
                _wrap = wrap
                wrap = lambda x: _wrap([x, T.div(class_="ovl")])

            # if we think the client already has the thumb in-cache, it is
            # poor to use delaysrc here.
            return T.span(class_=cls)[wrap(T.img(
                                     #src="/static/loading.jpg",
                                     src=[thisThumbSrc, "?size=thumb"]
                                     ))]

        @print_timing
        def thumbs():
            return map(_thumb, self.desc.photos())

        return [dict(thumb=flat.flatten(t)) for t in thumbs()]

    def zipUrl(self):
        return "%s?archive=zip" % self.desc.topic
    
    def zipSizeWarning(self):
        mb = 17.3 / 9 * len(self.desc.photos())
        secs = mb * 1024 / 40 
        return "(file will be roughly %d MB and take %d mins to download)" % (mb, secs / 60)

    @print_timing
    def pageJson(self):
        prev, next = self.prevNext()

        picInfo = json.dumps(self.picInfoJson())
        arrowPages = T.raw(simplejson.dumps({
            "prev" : str(self.desc.otherImageUrl(prev)),
            "next" : str(self.desc.otherImageUrl(next))}))
        preloadImg = T.raw(simplejson.dumps(
            self.nextImagePreload()))

        if self.agent is not None and tagging.allowedToWrite(self.graph, self.agent):
            allTags = T.raw(simplejson.dumps(self.tagList()))
        else:
            allTags = T.raw(simplejson.dumps([]))
        
        return flat.flatten(T.script(type="text/javascript")[
            T.raw("""
            // <![CDATA[
            var picInfo = """), picInfo,";",
            "var arrowPages = ", arrowPages, ";",
            "var preloadImg = ", preloadImg, ";",
            "var allTags = ", allTags, ";",
            T.raw("""
            // ]]>""")])

    @print_timing
    def picInfoJson(self):
        # vars for the javascript side to use
        current = self.desc.currentPhoto()
        if current is None:
            return {}

        # multiprocessing pool didn't go faster. i forget how to do
        # async requests with restkit
        results = map(serviceCallSync, [(self.agent, name, current)
                                        for name in ['links', 'facts', 'tags']])

        def readOrError(js):
            try:
                return json.loads(js)
            except Exception, e:
                log.error(traceback.format_exc())
                return {'error' : str(e)}

        ret = dict(
            relCurrentPhotoUri=localSite(current),
            currentPhotoUri=current,
            links=readOrError(results[0]),
            facts=readOrError(results[1]),
            tags=readOrError(results[2]),
            )
        return ret

    def nextImagePreload(self):
        _, nextImg = self.prevNext()
        if nextImg is None:
            return ''
        # must always return a string, for json encoding below
        preloadSize = "large"
        if nextImg.lower().endswith(videoExtensions):
            # sloppy; this should use the presence of "a pho:Video" in the graph.
            # also, i'm still stuffing this in an img tag, which may
            # or may not trigger a convert or load
            preloadSize = "video2"
        return localSite(nextImg) + "?size=" + preloadSize

########################################################
                
    def otherImageHref(self, ctx, img):
        return self.desc.otherImageUrl(img)

    def render_standardSite(self, ctx, data):
        return T.a(href=self.otherImageHref(ctx, self.currentPhoto).replace('tablet', '0'))[
            "Standard site"]

    def render_rssHref(self, ctx, img):
        href = self.otherImageHref(ctx, img)
        return href.remove('current').add('rss', '1')

    def jsonContent(self):
        return json.dumps({'photos' : self.photos})

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

        return json.dumps({
            "msg": "tagged %s images: <a href=\"%s\">view your new set</a>" %
            (len(imgStatements), newUri)
            })
        
    def archiveZip(self, ctx):
        f = StringIO('')
        zf = zipfile.ZipFile(f, 'w', zipfile.ZIP_DEFLATED)
        for photo in self.photos:
            data, mtime = thumb(photo, maxSize=Full)
            zf.writestr(str(photo.split('/')[-1]), data)

        zf.close()
        request = inevow.IRequest(ctx)
        request.setHeader("Content-Type", "multipart/x-zip")

        downloadFilename = self.desc.topic.split('/')[-1] + ".zip"
        request.setHeader("Content-Disposition",
                          "attachment; filename=%s" %
                          downloadFilename.encode('ascii'))

        return f.getvalue()

    def prevNext(self):
        photos = self.desc.photos()
        if self.desc.currentPhoto() is None:
            return None, None
        i = photos.index(self.desc.currentPhoto())
        return (photos[max(0, i - 1)],
                photos[min(len(photos) - 1, i + 1)])

    @print_timing
    def tagList(self):
        freqs = tagging.getTagsWithFreqs(self.graph)
        return freqs.keys()   
    
    def photoRss(self, ctx):
        request = inevow.IRequest(ctx)

        # this should be making atom!
        # it needs to return the most recent pics, with a link to the next set!

        # copied from what flickr emits
        request.setHeader("Content-Type", "text/xml; charset=utf-8")

        items = [T.Tag('title')["bigasterisk %s photos" % self.graph.label(self.desc.topic)]]
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
    log.debug("serviceCall: %s %s", name, uri)
    def endTime(result):
        log.info("service call %r in %.01f ms", name, 1000 * (time.time() - t1))
        return result
    return getPage(str('%s?uri=%s' % (networking.serviceUrl(name),
                                      urllib.quote(uri, safe=''))),
            headers={'x-foaf-agent' : str(getUser(ctx)),
                       }).addCallback(endTime)

def serviceCallSync((agent, name, uri)):
    t1 = time.time()
    log.debug("serviceCall: %s %s", name, uri)
    svc = restkit.Resource(networking.serviceUrl(name))
    rsp = svc.get(uri=uri, headers={'x-foaf-agent' : str(agent)})
    log.info("service call %r in %.01f ms", name, 1000 * (time.time() - t1))
    return rsp.body_string()

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
            return json.dumps({'Location' : str(newUrl)})
        
        req.redirect(newUrl)
        return ''

# candidate for sparqlhttp
def fastAsk(graph, stmts, batch=6):
    """result of mapping self.graph.contains over stmts, but
    is faster if the answers are mostly false. Combines
    requests into 'batch' at a time"""
    if len(stmts) > batch:
        return sum((fastAsk(graph, stmts[x:x+batch])
                    for x in range(0, len(stmts), batch)),
                   [])

    if len(stmts) == 1:
        return [graph.contains(stmts[0])]

    def clause(stmt):
        return "{ %s %s %s . }" % (
            stmt[0].n3(), stmt[1].n3(), stmt[2].n3()
            ) # n3 is not sparql; literals may not quote right :(
    
    unions = " UNION ".join(map(clause, stmts))
    combined = "ASK { %s }" % unions
    if graph.queryd(combined) == False:
        return [False] * len(stmts)
    else:
        return [fastAsk(graph, [stmt])[0] for stmt in stmts]
