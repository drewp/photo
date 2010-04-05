"""
browse directories and files on disk

fs scanner needs to make this:

 uri a foaf:Image
 uri inDir dir
 dir inDir dir
 uri filename basename

"""
from nevow import rend, loaders, json
from rdflib import Namespace, URIRef, RDF, Variable

PHO = Namespace("http://photo.bigasterisk.com/0.1/")
SITE = Namespace("http://photo.bigasterisk.com/")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")

class FileBrowse(rend.Page):
    docFactory = loaders.xmlfile("fileBrowse.html")
    addSlash = True

    def __init__(self, ctx, graph):
        self.graph = graph
    
    def child_treeData(self, ctx):
        """extjs tree makes POST requests with a 'node' arg, and
        expects child node definitions
        http://extjs.com/deploy/dev/docs/output/Ext.tree.TreeLoader.html
        """
        node = URIRef(ctx.arg('node'))

        ret = []

        q = "SELECT ?child WHERE { ?child pho:inDirectory ?node . } ORDER BY ?child"

        for row in self.graph.queryd(q,
                                     initBindings={Variable('node') : node}):
            child = row['child']
            leaf = not self.graph.contains((child, RDF.type,
                                            PHO['DiskDirectory']))
            fmt = u'%s'
            isImage = self.graph.contains((child, RDF.type, FOAF['Image']))
            viewable = self.graph.contains((child, PHO['viewableBy'], PHO['friends']))
            if isImage and not viewable:
                fmt = u'<span class="access">%s</span>'
            
            ret.append({u'id' : child,
                        u'text': fmt % self.graph.value(child, PHO['filename']),
                        u'leaf': leaf})
            
            if len(ret) > 500:
                ret.append({u'id' : u'',
                            u'text' : u'(too many to show)',
                            u'leaf' : True})
                break
            
        return json.serialize(ret)
