import boot
import web
from genshi import Markup
from genshi.template import TemplateLoader
from genshi.output import XHTMLSerializer
import networking, photos
from urls import localSite
from oneimagequery import photoCreated
import db
from ns import SITE

log = boot.log
loader = TemplateLoader(".", auto_reload=True)
serializer = XHTMLSerializer()

class Index(object):
    def GET(self):
        return "sharesingle"

class ShareSingle(object):
    """
    image page that features one main image (but maybe has links to
    related ones) and is designed for casual or new users who don't
    know anything about the photo site. The viewer may not be logged
    in. It has already been determined that this user may see this
    image.
    """
    def GET(self, relImageUri):
        uri = SITE[relImageUri]
        print "abs", uri
        size = photos.getSize(uri, photos.sizes["screen"])

        try:
            created = photoCreated(graph, uri)
            prettyDate = created.date().isoformat()
        except ValueError:
            prettyDate = "(unknown date)"
            
        tmpl = loader.load("sharesingle.html")
        stream = tmpl.generate(
            title="photo",
            prettyDate=prettyDate,
            bestJqueryLink=networking.jqueryLink(
                web.ctx.environ.get('HTTP_X_FORWARDED_FOR', '')),
            featuredImg=Markup('<img src="%s" width="%s" height="%s"/>' %
                               (localSite(uri)+"?size=screen",
                                size[0], size[1])),
            loginWidget=Markup(networking.getLoginBarSync(
                web.ctx.environ.get('HTTP_COOKIE', ''))),
            actionsAllowed=[],
            otherSizeLinks=[],
            link="l",
            allowedToWriteMeta=False,
            pageJson="",
            )
        return (''.join(serializer(stream))).encode('utf8')


graph = db.getGraph()
app = web.application((
    r'/', 'Index',
    r'/(.*)/single', 'ShareSingle',
    ), globals())
application = app.wsgifunc()

