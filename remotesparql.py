from rdflib.Graph import Graph

import sys
sys.path.insert(0, "/home/drewp/projects/wesabe/py-restclient/build/lib")
import restclient

restclient.RequestFailed.__str__ = lambda self: self.message

sys.path.append("/home/drewp/projects/ffg/sparqlhttp")
sys.path.append("/my/proj/ffg/sparqlhttp")
from sparqlhttp.sparqlxml import parseSparqlResults
from sparqlhttp.dictquery import Graph2
from sparqlhttp.remotegraph import interpolateSparql


def allegroCall(call, *args, **kwargs):
    """allegro POST requests finish with an error I don't understand"""
    try:
        return call(*args, **kwargs)
    except restclient.RequestError, e:
        if e[0][0][1] != 'transfer closed with outstanding read data remaining':
            raise

class RemoteSparql(Graph2):
    """compatible with sparqlhttp.Graph2, but talks to a
    sesame/allegro-style HTTP sparql endpoint. This version is
    synchronous."""
    def __init__(self, repoUrl, repoName, initNs={}):
        """
        repoUrl ends with /repositories
        repoName is the repo to create/use
        initNs = dict of namespace prefixes to use on all queries
        """
        self.root = restclient.Resource(repoUrl)
        self.repoName = repoName
        self.initNs = initNs
        self.sparqlHeader = ''.join('PREFIX %s: <%s>\n' % (p, f)
                                    for p,f in initNs.items())

        if 'openrdf-sesame' in repoUrl:
            pass
        else:
            allegroCall(self.root.post, id=self.repoName,
                        directory='/tmp/agraph-catalog',
                        **{'if-exists' : 'open'})

    def queryd(self, query, initBindings={}):
        # initBindings keys can be Variable, but they should not
        # include the questionmark or else they'll get silently
        # ignored
        interpolated = interpolateSparql(query, initBindings)
        #print interpolated
        query = self.sparqlHeader + interpolated
        xml = self.root.get('/' + self.repoName,
                            query=query, queryLn='SPARQL',
                            headers={'Accept' :
                                     'application/sparql-results+xml'}
                            )
        return parseSparqlResults(xml)

    def safeParse(self, source, publicID=None, format="xml"):

        graph = Graph()
        graph.parse(source, publicID=publicID, format=format)

        data = open(source).read()
        allegroCall(self.root.put, '/%s/statements' % self.repoName,
                    context=publicID.n3(),
                    payload=graph.serialize(format='xml'),
                    headers={'Content-Type' : 'application/rdf+xml'})

        self._graphModified()
        

    def remove(self, *triples, **context):
        """graph.get_context(context).remove(stmt)"""
        self._graphModified()
        for stmt in triples:
            params = {'context' : context.get('context')}
            for x, param in zip(stmt, ['subj', 'pred', 'obj']):
                if x is not None:
                    params[param] = x.n3()
            allegroCall(self.root.delete,
                        '/%s/statements' % self.repoName, **params)


    def add(self, *triples, **context):
        """takes multiple triples at once (to reduce RPC calls).
        context arg is required"""
        try:
            context = context['context']
        except KeyError:
            raise TypeError("'context' named argument is required")

        graph = Graph()
        for p, f in self.initNs.items():
            graph.bind(p, f)
        for s in triples:
            graph.add(s)

        allegroCall(self.root.post, '/%s/statements' % self.repoName,
                    context=context.n3(),
                    payload=graph.serialize(format='xml'),
                    headers={'Content-Type' : 'application/rdf+xml'})
        triples

        self._graphModified()
        

    def commit(self):
        pass
