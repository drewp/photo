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
import logging, zipfile, datetime, json, urllib, random, time, restkit, subprocess
from StringIO import StringIO
from nevow import loaders, rend, tags as T, inevow, url, flat
from rdflib import URIRef, Literal
from twisted.web.client import getPage
from isodate.isodates import parse_date, date_isoformat
from mediaresource import Full, sizes, MediaResource, Done
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
from mediaresource import Video2
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

        if (req.getHeader('accept') == 'application/json' and
            not ctx.arg("jsonUpdate") and not ctx.arg('setList')): # approximage parse
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

        view = View(self.graph, self.desc,
                   params=dict(date=ctx.arg('date'), star=ctx.arg('star')),
                   cookie=req.getHeader("cookie") or '',
                   agent=getUser(ctx),
                   openidProxyHeader=req.getHeader('x-openid-proxy'),
                   forwardedFor=req.getHeader('x-forwarded-for'))

        if ctx.arg("jsonUpdate"):
            req.setHeader("Content-Type", "application/json")
            return json.dumps(self.templateData(view))

        if ctx.arg("setList"):
            req.setHeader("Content-Type", "application/json")
            return json.dumps(view.photosInSetPlus())
          
        
        ret = view.render()
        print "rendered view is %s" % len(ret)
        # after 65k, this gets truncated somewhere! get a new web server
        req.setHeader("Content-Type", "application/xhtml+xml")
        return ret.encode('utf8')

    def templateData(self, view):
        def v(keys):
            return dict((k, getattr(view, k)()) for k in keys)
        return {
            'topBar' : v("setLabel storyModeUrl intro".split()),
            'featured' : v("currentLabel prevNextDateButtons stepButtons featured actionsAllowed aclWidget uploadButton publicShareButton related otherSizeLinks link debugRdf ".split()),
            'featuredMeta' : v("facts allowedToWriteMeta".split()),
            # this one should be omitted when the client already had the right set
            'photosInSet' : v(" starLinkAll starLinkOnly photosInSet setAclWidget".split()),
            'pageJson' : v(["pageJson"]),
            # putting comments in here too would be nice
            # maybe spell out the images that will be needed for this page, for the preload queue?
            }

    def jsonContent(self):
        return json.dumps({'photos' : self.desc.photos()})
        
    def archiveZip(self, ctx):
        raise NotImplementedError("bitrotted- needs fixing")
        f = StringIO('')
        zf = zipfile.ZipFile(f, 'w', zipfile.ZIP_DEFLATED)
        for photo in self.desc.photos():
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

    def postTagRange(self, ctx):
        # security?

        p = self.desc.photos()
        i1 = p.index(URIRef(ctx.arg('start')))
        i2 = p.index(URIRef(ctx.arg('end')))

        newUri = URIRef(ctx.arg('uri'))

        imgStatements = [(img, FOAF.depicts, newUri)
                         for img in p[i1:i2+1]]
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
    
    def photoRss(self, ctx):
        request = inevow.IRequest(ctx)

        # this should be making atom!
        # it needs to return the most recent pics, with a link to the next set!

        # copied from what flickr emits
        request.setHeader("Content-Type", "text/xml; charset=utf-8")

        items = [T.Tag('title')["bigasterisk %s photos" %
              self.desc.determineLabel(self.desc.graph, self.desc.topicDict)]]
        for pic in self.desc.photos()[-50:]: # no plan yet for the range. use paging i guess
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

        return """<?xml version="1.0" encoding="utf-8" standalone="yes"?>
        <rss version="2.0" 
          xmlns:media="http://search.yahoo.com/mrss"
          xmlns:atom="http://www.w3.org/2005/Atom">
            <channel>
            """ + flat.flatten(items) + """
            </channel>
        </rss>
        """


class View(pystache.view.View):
    template_name = "imageSet"
    template_path = "template"

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
        return self.desc.determineLabel(self.desc.graph, self.desc.topicDict)
    
    def bestJqueryLink(self):
        return networking.jqueryLink(self.forwardedFor)
        
    def setLabel(self):
        return self.desc.label()

    def storyModeUrl(self):
        # only works on topic?edit=1 urls, not stuff like
        # set?tag=foo. error message is poor.

        # need something on desc
        try:
            return self.desc.storyModeUrl()
        except ValueError:
            return None

    def intro(self):
        intro = self.graph.value(self.desc.topicDict['topic'], PHO['intro'])
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
                return None

            try:
                showingDate = photoDate(self.graph, self.desc.currentPhoto())
            except ValueError:
                return None
        
        dtd = parse_date(showingDate)
        try:
            prev = dict(prevDate=date_isoformat(nextDateWithPics(
                self.graph, dtd, -datetime.timedelta(days=1))))
        except ValueError:
            prev = None

        try:
            next = dict(nextDate=date_isoformat(nextDateWithPics(
                self.graph, dtd, datetime.timedelta(days=1))))
        except ValueError:
            next = None
            
        return dict(prev=prev, next=next)

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

        feat = MediaResource(self.graph, current)

        if feat.isVideo():
            feat.requestVideo()
            progress = feat.videoProgress()
            if progress is Done:
                w, h = feat.getSize(Video2)
                return dict(video=dict(src=currentLocal+"?size=video2",
                                       width=600,
                                       height=600 / w * h))
            else:
                return dict(videoNotReady=dict(progress=progress))
        else:
            try:
                size = feat.getSize(sizes["large"])
            except (ValueError, IOError):
                size = (0,0)
            marg = (602 - 2 - size[0]) // 2
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
                                          self.desc.currentPhoto())

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
        return access.accessControlWidget(self.graph, self.agent, setUri)

    def uploadButton(self):
        if self.desc.currentPhoto() is None:
            return ''
        copy = self.graph.value(self.desc.currentPhoto(), PHO.flickrCopy)
        if copy is not None:
            return dict(copied=dict(uri=copy))

        if self.openidProxyHeader is not None and URIRef(self.openidProxyHeader) in auth.superusers:
            return dict(mayCopy=dict(show=True))
        
        return None

    @print_timing
    def publicShareButton(self):
        if self.desc.currentPhoto() is None:
            return None

        # not absoluteSite() here, since i didn't want to make
        # separate shortener entries for test sites and the real one
        target = self.desc.currentPhoto()+"/single"
        if access.viewable(self.graph, self.desc.currentPhoto(), FOAF.Agent):
            short = hasShortUrlSync(target)
            if short:
                return dict(hasLink=dict(short=short))
        return dict(makeLink=dict(show=True))

    def related(self):
        try:
            js = serviceCallSync(self.agent, 'links', self.desc.currentPhoto())
        except ValueError:
            return []

        ret = []
        for kind, links in json.loads(js)['links']:
            for link in links:
                ret.append(dict(kind=kind, uri=link['uri'],
                                label=link['label']))
        return ret

    def facts(self, p=None):
        try:
            js = serviceCallSync(self.agent, 'facts', p or self.desc.currentPhoto())
        except ValueError:
            return {}
        return json.loads(js)
    
    def otherSizeLinks(self):
        if self.desc.currentPhoto() is None:
            return []

        isVideo = self.desc.isVideo(self.desc.currentPhoto())

        if isVideo:
            avail = ['video2', 'full']
        else:
            avail = ['medium', 'large', 'screen', 'full']
            
        return [
            dict(href="%s?size=%s" % (localSite(self.desc.currentPhoto()), s),
                 label={'video2' : '320 (webm)',
                        'full' : ('Original size and format' if isVideo else
                                'Original'),
                        }.get(s, str(sizes[s])))
            for s in avail]

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
            href = self.desc.altUrl(recent=str(opt))
            choices.append(T.a(href=href)[opt])
        choices.append(T.a(href=self.desc.altUrl(recent=''))['all'])
        return ['show only the ', [[c, ' '] for c in choices],
                ' most recent of these']

    @print_timing
    def photosInSet(self):
        desc = self.desc
        return [dict(thumb=dict(
            link=desc.otherImageUrl(p),
            uri=p,
            cls=(("current" if p == desc.currentPhoto() else "not-current")
                 + (" video" if desc.isVideo(p) else '')),
            src="%s?size=thumb" % localSite(p),
            isVideo=desc.isVideo(p)))
                for p in desc.photos()]

    def photosInSetPlus(self):
        """for use by other tools who want to draw some photos
        """
        out = []
        for p in self.desc.photos():
            r = MediaResource(self.graph, p)
            try:
                s = r.getSize(sizes["thumb"])
                thumbSize = {"thumbSize" : dict(w=s[0], h=s[1])}
            except (ValueError, IOError, subprocess.CalledProcessError):
                thumbSize = {}
            out.append(dict(
                link=absoluteSite(self.desc.otherImageUrl(p)),
                uri=p,
                facts=self.facts(p),
                thumb="%s?size=thumb" % p,
                screen="%s?size=screen" % p,
                isVideo=self.desc.isVideo(p)
                ))
            out[-1].update(thumbSize)
        return out
        

    def zipUrl(self):
        return "%s?archive=zip" % self.desc.topic
    
    def zipSizeWarning(self):
        mb = 17.3 / 9 * len(self.desc.photos())
        secs = mb * 1024 / 40 
        return "(file will be roughly %d MB and take %d mins to download)" % (mb, secs / 60)

    @print_timing
    def pageJson(self):
        prev, next = self.prevNext()
        allTags = self.tagList() if (
            self.agent is not None and
            tagging.allowedToWrite(self.graph, self.agent)) else []

        return dict(picInfo=json.dumps(self.picInfoJson()),
                    prev=json.dumps(self.desc.otherImageUrl(prev)),
                    next=json.dumps(self.desc.otherImageUrl(next)),
                    preloadImg=json.dumps(self.nextImagePreload()),
                    allTags=json.dumps(allTags),
                    )

    @print_timing
    def picInfoJson(self):
        # vars for the javascript side to use
        current = self.desc.currentPhoto()
        if current is None:
            return {}

        try:
            js = serviceCallSync(self.agent, 'tags', current)
            tags = json.loads(js)
        except restkit.RequestFailed, e:
            tags = {"error" : str(e)}
            
        return dict(relCurrentPhotoUri=localSite(current),
                    currentPhotoUri=current,
                    tags=tags)

    def debugRdf(self):
        current = self.desc.currentPhoto()
        if not current:
            return None
        return 'http://bang:8080/openrdf-workbench/repositories/photo/explore?' +urllib.urlencode([('resource', '<'+current+'>')])

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
                
    # for tablet, incomplete
    def render_standardSite(self, ctx, data):
        return T.a(href=url.URL.fromString(self.desc.otherImageUrl(self.currentPhoto)).replace('tablet', '0'))[
            "Standard site"]

    def rssHref(self):
        photos = self.desc.photos()
        if not photos:
            return "incomplete"
        href = url.URL.fromString(self.desc.otherImageUrl(photos[0]))
        return href.remove('current').add('rss', '1')

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

def serviceCallSync(agent, name, uri):
    if not uri:
        raise ValueError("no uri for service call to %s" % name)
    t1 = time.time()
    log.debug("serviceCall: %s %s", name, uri)
    svc = restkit.Resource(networking.serviceUrl(name))
    rsp = svc.get(uri=uri, headers={'x-foaf-agent' : str(agent)})
    log.info("timing: service call %r in %.01f ms", name, 1000 * (time.time() - t1))
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
