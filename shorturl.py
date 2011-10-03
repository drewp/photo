import json, urllib
import networking
from twisted.web.client import getPage
import restkit

pat = 'http://bigast.com/_%s'

def hasShortUrl(longUri):
    def fail(failure):
        # only meant for 404, but maybe it's not getting called at all?
        return None
    return getPage(networking.shortenerRoot()+"shortLinkTest?%s" %
                urllib.urlencode([('long', longUri)])).addCallbacks(
        lambda result: pat % json.loads(result)['short'],
        fail)

def hasShortUrlSync(longUri):
    try:
        result = json.loads(restkit.Resource(networking.shortenerRoot()).get("shortLinkTest", long=longUri).body_string())
    except restkit.ResourceNotFound:
        return None
    return pat % result['short']
