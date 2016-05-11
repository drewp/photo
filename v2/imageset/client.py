import urllib, logging
from cyclone.httpclient import fetch
import networking
log = logging.getLogger()

def changed(uri):
    """call this to rescan an image"""
    # errors?
    url = 'http://%s:%s/update' % networking.imageSet()
    log.info('post %r for index update', url)
    return fetch(url, method='POST', postdata=urllib.urlencode([('uri', str(uri))]))

def aclChanged(tbd):
    pass
