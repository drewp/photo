import os.path
from twisted.python.filepath import FilePath


def picSubDirs(syncs=None, SesameSync=None, graph=None, quick=False):
    """return list of subdirs to watch for pics. We can also make
    SesameSync objects in the syncs dict"""
    subdirs = []
    top = FilePath(__file__).parent()
    for picRoot, prefix in [
        (top.child("input/").path, "http://photo.bigasterisk.com/internal/"),
        (top.child("webinput/").path, "http://photo.bigasterisk.com/webinput/"),
        ('/my/pic/', "http://photo.bigasterisk.com/"),
        ]:
        if syncs is not None:
            syncs[picRoot] = SesameSync(graph, inputDirectory=picRoot,
                                        contextPrefix=prefix,
                                        polling=False)
        subdirs.append(picRoot)

    # don't read /my/pic/~thumb
    subdirs.remove('/my/pic/')
    if quick:
        subdirs.append('/my/pic/flickr')
    else:
        subdirs.extend(['/my/pic/%s' % s
                        for s in os.listdir('/my/pic') if s != '~thumb'])

    return subdirs
