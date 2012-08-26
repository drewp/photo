
def findAltRoot(graph, img):
    """
    if this img has alternates or is an alternate, return the root of
    the alt tree and a string describing the tree; else None
    """
    
    for row in graph.queryd("""
       SELECT ?alt ?tag WHERE {
         ?img pho:alternate ?alt .
         OPTIONAL { ?alt pho:tag ?tag }
       }""", initBindings={'img' : img}):
        return img, "has %s" % (row['tag'] or 'alts')
    for row in graph.queryd("""
        SELECT ?root WHERE {
          ?root pho:alternate ?img .
        }""", initBindings={'img' : img}):
        return row['root'], 'has alts'
    return None

def findCompleteAltTree(graph, root):
    """
    all alternates (recursively) from this root
    """
    ret = [root]
    for row in graph.queryd("""
       SELECT ?alt ?tag WHERE {
         ?img pho:alternate ?alt .
       }""", initBindings={'img' : root}):
        ret.extend(findCompleteAltTree(graph, row['alt']))
    
    return ret
