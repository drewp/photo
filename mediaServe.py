"""
requests for photos and videos are routed to this server

"""
import boot
import urllib, os, sys
from nevow import rend, inevow, static, appserver
from twisted.web import http
from twisted.internet import reactor
from photos import thumb, getRequestedSize
from db import getGraph
import access
from ns import RDF, SITE, PHO
from urls import absSiteHost

log = boot.log

class StaticCached(static.Data):
    """
    from http://twistedmatrix.com/pipermail/twisted-web/2005-March/001358.html
    """
    def __init__(self, data, mime, mtime):
        self.mtime = mtime
        static.Data.__init__(self, data, mime)
    def renderHTTP(self, ctx):
        request = inevow.IRequest(ctx)
        request.setLastModified(self.mtime)
        request.setHeader('Cache-Control', 'max-age=604800')
        # flickr uses an even longer maxage, and puts on a Expires:
        # Mon, 28 Jul 2014 23:30:00 GMT, and then they have a squid
        # cache providing the image

        # For public requests, it would be nice to omit this so a
        # cache can give the image to two listeners. 
        # Note that this header is the only thing 'securing'
        # non-public requests, and it has to work with trusted
        # intermediate caches that aren't reachable by users, which is
        # unrealistic security.
        request.setHeader('Vary', 'Cookie')      

        return static.Data.renderHTTP(self, ctx)

class Main(rend.Page):
    
    def __init__(self, graph):
        self.graph = graph

    def locateChild(self, ctx, segments):
        request = inevow.IRequest(ctx)
        if 1:
            request.setHost(*absSiteHost)

        uriSuffix = urllib.quote('/'.join(segments))
        # if you paste a url from a browser to another one, the first
        # one might have been sending %3A while the second one will
        # start sending :
        # This might be a chrome-only issue: http://code.google.com/p/chromium/issues/detail?id=64732
        uriSuffix = uriSuffix.replace(':', '%3A')
        uri = SITE[uriSuffix]

        # interim test version; skips all perm checks
        def returnVideo(filename):
            mtime = os.stat(filename).st_mtime
            return StaticCached(open(filename).read(), "video/ogg", mtime), ()

        if uri.endswith('dl-2010-02-06/DSC_5365.ogv'):
            return returnVideo("/my/pic/digicam/dl-2010-02-06/DSC_5365.ogv")
        if uri.endswith('dt/CIMG3501.ogv'):
            return returnVideo("/my/pic/phonecam/dt/CIMG3501.ogv") 
        if str(uri) == 'http://photo.bigasterisk.com/proj/giggles.ogv':
            return returnVideo('/my/pic/proj/giggles.ogv')

        return self.imageChild(ctx, uri)

    def imageResource(self, uri, ctx):
        size = getRequestedSize(ctx)

        log.debug("need thumb for %r", uri)
        # this ought to return a redirect to a static error image when it breaks
        jpg, mtime = thumb(uri, size)
        ct = "image/jpeg"
        if graph.contains((uri, RDF.type, PHO.Video)):
            ct = "video/webm"
        return StaticCached(jpg, ct, mtime)

    
    def imageChild(self, ctx, uri):
        """

        
        proxy openid; now compare that header to the allowed viewers. if header is missing or empty, that becomes the 'anonymous' user. other openids are just URIRefs in the graph, and you have to be able to get from the viewableBy link to that URIRef (via any number of groups)

        in the url, take a tag to show. Display a checkbutton of whether the current image has that tag. Take key input to toggle the button. Post button changes as graph edits. click on the tag to go to an imageset of that tag.
        """
        if not self.viewable(uri, ctx):
            request = inevow.IRequest(ctx)
            return self.nonViewable(request), ()

        if ctx.arg('page'): # old; use {img}/page now
            raise NotImplementedError("request routed to the wrong service")

        return self.imageResource(uri, ctx), ()
        
    def viewable(self, uri,  ctx):
        agent = access.getUser(ctx)
        return access.viewable(self.graph, uri, agent)

    def nonViewable(self, request):
        """
        this shouldn't reveal whether the image was real or not-- just
        that there's nothing you can get to at your access level.
        """
        accept = request.getHeader('accept')
        ua = request.getHeader('user-agent')

        if (accept.split(',')[0].startswith('image/') or
            # http://code.google.com/p/chromium/issues/detail?id=63173
            ('Chromium' in ua and accept == '*/*')):
            log.info("failing with image")
            return open("static/noaccess.png").read()
        
        request.setHeader('WWW-Authenticate', 'Basic realm="topsecret"')
        request.setResponseCode(http.UNAUTHORIZED)
        #request.setResponseCode(http.FORBIDDEN)
        log.info("failing with text")
        # todo: login prompt if they weren't logged in; apology if they were
        return "Authentication required."        

if __name__ == '__main__':
    graph = getGraph()

    site = appserver.NevowSite(Main(graph))

    # turn this on for a log line per request
    #from twisted.python import log as twlog
    #twlog.startLogging(sys.stdout)
    
    reactor.listenTCP(int(sys.argv[1]), site)
    reactor.run()
