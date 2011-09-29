import json, urllib
import networking
from twisted.web.client import getPage

def hasShortUrl(longUri):
    def fail(failure):
        # only meant for 404, but maybe it's not getting called at all?
        return None
    return getPage(networking.shortenerRoot()+"shortLinkTest?%s" %
                urllib.urlencode([('long', longUri)])).addCallbacks(
        lambda result: 'http://bigast.com/_%s' % json.loads(result)['short'],
        fail)

