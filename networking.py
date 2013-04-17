import os
from twisted.web.client import getPage
from restkit import request

serviceHost = os.environ.get('PHOTO_SERVICE_HOST', 'bang')

def getLoginBar(cookie=''):
    return getPage("http://%s:9023/_loginBar" % serviceHost,
                   headers={"Cookie" : cookie})

def getLoginBarSync(cookie=''):
    return request("http://%s:9023/_loginBar" % serviceHost,
                   headers={"Cookie" : cookie}).body_string()

def graphRepoRoot():
    return "http://%s:8080/openrdf-sesame/repositories" % serviceHost

def searchRoot():
    return os.environ.get('PHOTO_SEARCH',
                          "http://bang:9096/")

def shortenerRoot():
    return "http://%s:9079/" % serviceHost

def commentProxy():
    return serviceHost, 9031, "/comments"

def mediaServeProxy2():
    return serviceHost, 8032

def oneImageServer():
    return serviceHost, 9043, ""

def serviceUrl(name):
    return {
        'facts' : 'http://%s:9043/facts' % serviceHost,
        'links' : 'http://%s:9043/links' % serviceHost,
        'tags' : 'http://%s:9043/tags' % serviceHost,
        'comments' : 'http://%s:%s%s' % commentProxy(),
        }[name]

def jqueryLink(forwardedFor):
    if not forwardedFor or forwardedFor.startswith(('127.0.0.1', '10.1', '192.168')):
        # if local wifi users got routed through my squid cache,
        # this would be unnecessary, as I would have a local cache
        # of the google copy
        return "/static/jquery-1.6.4.min.js"
    else:
        return "//ajax.googleapis.com/ajax/libs/jquery/1.6.4/jquery.min.js"

