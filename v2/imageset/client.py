import urllib
from cyclone.httpclient import fetch
import networking

def changed(uri):
    """call this to rescan an image"""
    # errors?
    return fetch('http://%s:%s/update' % networking.imageSet(),
                 method='POST', postdata=urllib.urlencode([('uri', str(uri))]))

def aclChanged(tbd):
    pass
