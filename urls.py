SITE = "http://photo.bigasterisk.com/"

def localSite(url):
    if url.startswith(SITE):
        return url[len(SITE)-1:]
    return url
