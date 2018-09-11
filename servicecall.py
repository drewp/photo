import time, logging, urllib
import restkit
import networking
from webuser import getUser
from twisted.web.client import getPage
log = logging.getLogger('svc')
log.setLevel(logging.WARN)

def serviceCall(ctx, name, uri):
    """
    deferred to result of calling this internal service on the image
    uri. user credentials are passed on
    """
    t1 = time.time()
    log.debug("serviceCall: %s %s", name, uri)
    def endTime(result):
        log.info("service call %r in %.01f ms", name, 1000 * (time.time() - t1))
        return result
    return getPage(str('%s?uri=%s' % (networking.serviceUrl(name),
                                      urllib.quote(uri, safe=''))),
            headers={'x-foaf-agent' : str(getUser(ctx)),
                       }).addCallback(endTime)

def serviceCallSync(agent, name, uri):
    if not uri:
        raise ValueError("no uri for service call to %s" % name)
    t1 = time.time()
    log.debug("serviceCall: %s %s", name, uri)
    svc = restkit.Resource(networking.serviceUrl(name))
    rsp = svc.get(uri=uri, headers={'x-foaf-agent' : str(agent)})
    log.info("timing: service call %r in %.01f ms", name, 1000 * (time.time() - t1))
    return rsp.body_string()


def plainCallSync(agent, name, uri):
    if not uri:
        raise ValueError("no uri for service call to %s" % name)
    t1 = time.time()
    log.debug("serviceCall: %s %s", name, uri)
    svc = restkit.Resource(networking.serviceUrl(name) + uri)
    rsp = svc.get(headers={'x-foaf-agent' : str(agent)})
    log.info("timing: service call %r in %.01f ms", name, 1000 * (time.time() - t1))
    return rsp.body_string()

