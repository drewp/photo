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

