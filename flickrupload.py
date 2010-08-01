"""
service to upload a photo to flickr from a url

POST /upload?source=http://source/image.jpg

Security is handled outside this service. If you got here, you will be
able to write to the flickr account. We might someday make this pick
which flickr account to use based on who is asking for the upload

We reuse incoming cookies for our image fetch.

Returns json:
  {flickrUrl: 'http://www.flickr.com/photos/12345/12345'}

"""
import web, time, logging, os
import flickrapi
import restkit, tempfile, jsonlib
from rdflib.Graph import Graph
from rdflib import Namespace, URIRef, Literal
from xml.utils import iso8601
from photos import sizes
from edit import writeStatements
PHO = Namespace("http://photo.bigasterisk.com/0.1/")
DCTERMS = Namespace("http://purl.org/dc/terms/")
log = logging.getLogger()

def fetchImageToTempfile(uri, size, cookie):
    tf = tempfile.NamedTemporaryFile()
    res = restkit.Resource(uri)
    # this hangs on 4MB images, possibly because of thread problems with web.py
    jpg = res.get(size=size, headers={"Cookie" : cookie}).body
    log.info("got %s byte image" % len(jpg))
    tf.write(jpg)
    tf.flush()
    return tf

# alternate version with security holes, but that doesn't hang. You
# should only get here via openid_proxy, which only allows a few users
# for this service, so I am less worried about the shell attacks. This
# whole service should be ported to twisted or maybe mulib, so its
# http client and server don't fight.
def fetchImageToTempfile(uri, size, cookie):
    tf = tempfile.NamedTemporaryFile()

    cmd = "curl -H 'Cookie: %s' %s?size=%s > %s" % (cookie, uri, size, tf.name)
    log.info(cmd)
    os.system(cmd)

    return tf

def getGraph():
    graph = Graph()
    graph.parse("input/passwd.n3", format="n3")
    return graph

class index(object):
    def GET(self):
        return """<html>
        <form method="POST" action="upload">
        <h1>Fetch image at the given uri and upload it to a flickr account</h1>
        <div>img uri: <input type="text" size="100" name="img" value="http://photo.bigasterisk.com/digicam/dl-2009-10-07/DSC_2028.JPG"/></div>
        <div><input type="checkbox" name="test" id="test"/><label for="test">test mode, no flickr communication</label></div>
        <div><input type="submit"/></div>
        </form>
        </html>
        """
class upload(object):
    def POST(self):
        web.header('Content-type', 'application/json')
        i = web.input()
        uri = i['img']
        size = i.get('size', 'large')
        if size not in sizes:
            raise ValueError("size must be one of %r" % sizes.keys())

        log.info("fetch %s" % uri)
        tf = fetchImageToTempfile(uri, size, web.ctx.environ['HTTP_COOKIE'])

        log.info("connect to flickr")
        graph = getGraph()
        subj = PHO.flickrAccess

        flickr = flickrapi.FlickrAPI(graph.value(subj, PHO.key),
                                     graph.value(subj, PHO.secret))
        flickr.authenticate_console(perms='write')

        ret = {}
        if i.get('test', False):
            log.info("test mode: no upload")
            photoid = "12345"
            ret['test'] = True
        else:
            log.info("flickr.upload %r" % tf.name)
            newPhotos = flickr.upload(filename=tf.name,
                                title="bigasterisk upload",
                                description="",
                                tags="bigasterisk")
            assert newPhotos[0].tag == 'photoid'
            photoid = newPhotos[0].text
            
        ret['flickrUrl'] = 'http://www.flickr.com/photos/%s/%s' % (
            graph.value(subj, PHO.username), photoid)

        log.info("write rdf graph")

        writeStatements([
            (URIRef(uri), PHO.flickrCopy, URIRef(ret['flickrUrl'])),
            (URIRef(ret['flickrUrl']), DCTERMS.created, 
             Literal(iso8601.tostring(time.time(), timezone=time.altzone))),
            (URIRef(ret['flickrUrl']), DCTERMS.creator,
             URIRef(web.ctx.environ.get('HTTP_X_FOAF_AGENT',
                                        'http://example.com/unknown'))),
            ])


        return jsonlib.dumps(ret)

urls = (r'/', 'index',
        r'/upload', 'upload')
app = web.application(urls, globals())

if __name__ == '__main__':
    logging.basicConfig()
    log.setLevel(logging.INFO)
    app.run()

