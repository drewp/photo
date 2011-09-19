from genshi import Markup
from genshi.template import TemplateLoader
from genshi.output import XHTMLSerializer
import networking, photos
from urls import localSite

loader = TemplateLoader(".", auto_reload=True)
serializer = XHTMLSerializer()

class ShareSingle(object):
    """
    image page that features one main image (but maybe has links to
    related ones) and is designed for casual or new users who don't
    know anything about the photo site. The viewer may not be logged in.
    """
    def __init__(self, graph, uri):
        self.graph, self.uri = graph, uri

    def render(self, cookie, forwardedFor):

        size = photos.getSize(self.uri, photos.sizes["screen"])
        
        tmpl = loader.load("sharesingle.html")
        stream = tmpl.generate(
            title="photo",
            greet="Kelsi has shared a picture with you",
            bestJqueryLink=networking.jqueryLink(forwardedFor),
            featuredImg=Markup('<img src="%s" width="%s" height="%s"/>' %
                               (localSite(self.uri)+"?size=screen",
                                size[0], size[1])),
            loginWidget=Markup(networking.getLoginBarSync(cookie)),
            actionsAllowed=[],
            otherSizeLinks=[],
            link="l",
            allowedToWriteMeta=False,
            pageJson="",
            )
        return (''.join(serializer(stream))).encode('utf8')

