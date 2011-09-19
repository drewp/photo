import urllib, logging
from ns import SITE

log = logging.getLogger()


def localSite(url):
    if url.startswith('/'):
        return url
    if url.startswith(SITE):
        return url[len(SITE)-1:]
    raise ValueError("%s not on site" % url)

absSiteHost = "photo.bigasterisk.com", 80

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
    return ('http://' +
            absSiteHost[0] +
            (":%d" % absSiteHost[1] if absSiteHost[1] != 80 else "") +
            localSite(url))

def photoUri(filename):
    assert filename.startswith('/my/pic/')
    return SITE[urllib.quote(filename[len("/my/pic/"):])]

