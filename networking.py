from twisted.web.client import getPage

serviceHost = 'bang'

def getLoginBar(cookie=''):
    return getPage("http://%s:9023/_loginBar" % serviceHost,
                   headers={"Cookie" : cookie})

def graphRepoRoot():
    return "http://%s:8080/openrdf-sesame/repositories" % serviceHost

def commentProxy():
    return serviceHost, 9031, "/comments"

def oneImageServer():
    return serviceHost, 9043, ""

def serviceUrl(name):
    return {
        'facts' : 'http://%s:9043/facts' % serviceHost,
        'links' : 'http://%s:9043/links' % serviceHost,
        'tags' : 'http://%s:9043/tags' % serviceHost,
        'comments' : 'http://%s:%s%s' % commentProxy(),
        }[name]
