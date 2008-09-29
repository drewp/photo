# the display part of this should merge back into search.py, and the
# edit part should be a mode that can be turned on

"""
                depicts:

filename [img]    [add column]

[add]
  class: Person
  label: Apollo
  uri: http://photo.bigasterisk.com/2008/person/apollo

"""
from twisted.python.util import sibpath
import datetime
from rdflib import URIRef, Namespace, Variable, Literal, Graph
from nevow import rend, loaders, tags as T, inevow, json, url
from urls import localSite

PHO = Namespace("http://photo.bigasterisk.com/0.1/")

class Edit(rend.Page):
    addSlash = True
    docFactory = loaders.xmlfile('edit.html')
    def __init__(self, ctx, graph):
        self.graph = graph

    def child_saveStatements(self, ctx):
        content = inevow.IRequest(ctx).content
        content.seek(0)
        stmts = json.parse(content.read())
        # save to new file web-2008-09-13T05:15:26.nt

        outFile = sibpath(__file__, "webinput/web-%s.n3" % datetime.datetime.now().isoformat())
        g = Graph()
        for s in statementsFromJsRdf(stmts):
            g.add(s)

        g.serialize(outFile, format='nt')
        return "wrote %s" % outFile

    brickColumns = 1

    def render_table(self, ctx, data):
        rows = []
        d = URIRef(ctx.arg('dir')) # "http://photo.bigasterisk.com/digicam/dl-2008-09-25")
        for i, (pic, filename) in enumerate(sorted(self.picsInDirectory(d))[:]):
            img = T.img(src=[localSite(pic), '?size=thumb'],
                        onclick='javascript:photo.showLarge("%s")' %
                        (localSite(pic) + "?size=large"))

            picCols = [''] * self.brickColumns
            for fill in range(i, self.brickColumns):
                picCols[fill] = T.td
            picCols[i % self.brickColumns] = T.td(rowspan=self.brickColumns)[img]
            
            rows.append(T.tr(subj=pic)[
                T.td[T.a(href=localSite(pic))[filename]],
                picCols,
                ])

        return rows

    def render_thead(self, ctx, data):
        return [T.td] * self.brickColumns
    
    def picsInDirectory(self, dirUri):
        for row in self.graph.queryd(
            """SELECT ?pic ?fn WHERE {
                 ?pic pho:inDirectory ?dirUri ;
                      pho:filename ?fn
               }""",
            initBindings={Variable("?dirUri") : dirUri} # rdflib 2.4.0 only
            ):
            yield row['pic'], row['fn']

    def render_chooseSet(self, ctx, data):
        """if there's no dir, list some"""
        if ctx.arg('dir'):
            return ''
        dirs = []
        for row in self.graph.queryd(
            """
            SELECT ?d ?f WHERE { ?d a pho:DiskDirectory; pho:filename ?f }
            """):
            dirs.append(T.li[T.a(href=url.here.add('dir', row['d']))[row['f']]])
        return T.ul[dirs]

#
# convertor from http://n2.talis.com/wiki/RDF_JSON_Specification to rdflib
# 
def _rdflibObj(jsObj):
    if jsObj['type'] == 'uri':
        return URIRef(jsObj['value'])
    elif jsObj['type'] == 'literal':
        if len(jsObj.keys()) != 2:
            raise NotImplementedError(jsObj)
        return Literal(jsObj['value'])
    raise NotImplementedError(jsObj)
        
def statementsFromJsRdf(jsArray):
    stmts = set()
    for row in jsArray:
        for subj, predObjs in row.items():
            for pred, objs in predObjs.items():
                for obj in objs:
                    stmts.add((URIRef(subj), URIRef(pred), _rdflibObj(obj)))
    return stmts

if 0:
    test = statementsFromJsRdf(
        [{u'http://photo.bigasterisk.com/2008/person/apollo':
          {u'a':
           [{u'type': u'uri', u'value': u'http://xmlns.com/foaf/0.1/Person'}],
           u'rdfs:label':
           [{u'type': u'literal', u'value': u'apollo'}]}},
         {u'http://photo.bigasterisk.com/IMG_1675.JPG':
          {u'http://foaf/depicts':
           [{u'type': u'uri', u'value':
             u'http://photo.bigasterisk.com/2008/person/apollo'}]}}])
    ref = set([
        (URIRef('http://photo.bigasterisk.com/2008/person/apollo'),
         URIRef('a'), # sic
         URIRef('http://xmlns.com/foaf/0.1/Person')),
        (URIRef('http://photo.bigasterisk.com/2008/person/apollo'),
         URIRef('rdfs:label'),
         Literal('apollo')),
        (URIRef('http://photo.bigasterisk.com/IMG_1675.JPG'),
         URIRef('http://foaf/depicts'),
         URIRef('http://photo.bigasterisk.com/2008/person/apollo')),
        ])
    assert test == ref, test
