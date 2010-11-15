import urllib, logging
from rdflib import URIRef

SITE = "http://photo.bigasterisk.com/"

log = logging.getLogger()


def localSite(url):
    if url.startswith('/'):
        return url
    if url.startswith(SITE):
        return url[len(SITE)-1:]
    raise ValueError("%s not on site" % url)


def absoluteSite(url):
    """
    not correctly implemented yet
    
    >>> absoluteSite('http://photo.bigasterisk.com/foo')
    'http://localhost:8080/foo'
    or
    'http://photo.bigasterisk.com/foo'
    """
    # would it help to pass ctx? still might not be enough info unless
    # i use vhost monster style
    return 'http://photo.bigasterisk.com' + localSite(url)

def photoUri(filename):
    assert filename.startswith('/my/pic/')
    return URIRef(SITE + urllib.quote(filename[len("/my/pic/"):]))

