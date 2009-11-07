"""
service to upload a photo to flickr from a url

POST /upload?source=http://source/image.jpg

Security is handled outside this service. If you got here, you will be
able to write to the flickr account. We might someday make this pick
which flickr account to use based on who is asking for the upload

Returns json:
  {flickrUrl: 'http://www.flickr.com/photos/12345/12345'}

"""
import web
import flickrapi
import restkit, tempfile, jsonlib
from rdflib.Graph import Graph
from rdflib import Namespace

PHO = Namespace("http://photo.bigasterisk.com/0.1/")

def fetchImageToTempfile(uri, size):
    tf = tempfile.NamedTemporaryFile()
    jpg = restkit.Resource(uri).get(size=size)
    tf.write(jpg)
    tf.flush()
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
        <div>uri: <input type="text" size="100" name="uri" value="http://photo.bigasterisk.com/digicam/dl-2009-10-07/DSC_2028.JPG"/></div>
        <div><input type="checkbox" name="test" id="test"/><label for="test">test mode, no flickr communication</label></div>
        <div><input type="submit"/></div>
        </form>
        </html>
        """
class upload(object):
    def POST(self):
        web.header('Content-type', 'application/json')
        i = web.input()
        uri = i['uri']
        size = 'large'

        tf = fetchImageToTempfile(uri, size)

        graph = getGraph()
        subj = PHO.flickrAccess

        flickr = flickrapi.FlickrAPI(graph.value(subj, PHO.key),
                                     graph.value(subj, PHO.secret))
        flickr.authenticate_console(perms='write')

        ret = {}
        if i.get('test', False):
            photoid = "12345"
            ret['test'] = True
        else:
            newPhotos = flickr.upload(filename=tf.name,
                                title="bigasterisk upload",
                                description="",
                                tags="bigasterisk")
            assert newPhotos[0].tag == 'photoid'
            photoid = newPhotos[0].text
            
        ret['flickrUrl'] = 'http://www.flickr.com/photos/%s/%s' % (
            graph.value(subj, PHO.username), photoid)

        return jsonlib.dumps(ret)

urls = (r'/', 'index',
        r'/upload', 'upload')
app = web.application(urls, globals())
                  
if __name__ == '__main__':
    app.run()

