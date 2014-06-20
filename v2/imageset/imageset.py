#!../../bin/python
"""
main search/filter/pager that takes query params for describing a
set of images and returns json descriptions of them

query language in json:
{
  filter:
    (all non-null filters must be true for each image)
    (images you don't have access to are not visible)
    tags: [<strings, including '*'>]
    withoutTags: ['nsfw']
    type: 'video'|'image'
    dir: uri
    time: <yyyy-mm-dd>
      or  <yyyy-mm-dd>-<yyyy-mm-dd>
      or  put times on any of those values
    readableBy: <user or group>
    
  attrs:
    uri: true
    time: true
    acl: false # tbd
    tags: false
    
  sort:
    (default is [{time: 'asc'}])
    list can also have
     {uri: 'asc'}
     {random: <seed>}

  page:
    limit: <n>
    after: <uri>|None
      (or)
    skip: <count>
}

results:
{
  images: [
    {uri, type:video, ...}
  ],
  # tbd: how many excluded?
  paging:
    limit: <your limit>
    count: <len(images)>
    total: <n>
}

"""
from klein import run, route
import sys, json, itertools, datetime
from rdflib import Literal
sys.path.append("../..")

from db import getGraph
from requestprofile import timed
from oneimagequery import photoCreated

class ImageSet(object):
    def __init__(self, graph):
        self.graph = graph

    def request(self, query):
        paging = query.get('paging', {})
        limit = paging.get('limit', 10)
        skip = paging.get('skip', 0)
        images = []
        for rowNum, row in enumerate(self.graph.query("""
               SELECT DISTINCT ?uri WHERE {
                 ?uri a foaf:Image .
               } ORDER BY ?uri""")):
            if rowNum < skip:
                continue
            if len(images) >= limit:
                # keep counting rowNum
                continue

            images.append({
                'uri': row.uri,
                })
                
        #for row in rows:
        #    row['time'] = photoCreated(self.graph, row['uri'])
        
        return {
            'images': images,
            'paging': {
                'limit': limit,
                'skip': skip,
                'total': rowNum + 1,
            }
        }

        

def newestPics(graph):
    d = datetime.date.today()
    while True:
        rows = list(graph.queryd("""
               SELECT DISTINCT ?uri WHERE {
                 ?uri a foaf:Image; dc:date ?d .
               }""", initBindings={"d": Literal(d)}))
        for row in rows:
            row['time'] = photoCreated(graph, row['uri'])
        rows.sort(key=lambda row: row['time'], reverse=True)
        for row in rows:
            row['time'] = row['time'].isoformat()
            yield row
        d = d - datetime.timedelta(days=1)

if __name__ == '__main__':
    graph = getGraph()

    @route('/set.json')
    def main(request):
        if request.args['sort'] == ['new']:
            pics, elapsed = timed(lambda: list(itertools.islice(newestPics(graph), 0, 3)))
            return json.dumps({"newest": pics,
                               "profile": {"newestPics": elapsed}})
        else:
            raise NotImplementedError()

    run("0.0.0.0", 8035)
