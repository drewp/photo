SITE = "http://photo.bigasterisk.com/"

def localSite(url):
    if url.startswith(SITE):
        return url[len(SITE)-1:]
    return url

def absoluteSite(url):
    """
    >>> absoluteSite('http://photo.bigasterisk.com/foo')
    'http://localhost:8080/foo'
    or
    'http://photo.bigasterisk.com/foo'
    """
    # would it help to pass ctx? still might not be enough info unless
    # i use vhost monster style
    return 'http://photo.bigasterisk.com' + localSite(url)
