import os.path


def picSubDirs(syncs=None, SesameSync=None, graph=None, quick=False):
    """return list of subdirs to watch for pics. We can also make
    SesameSync objects in the syncs dict"""
    subdirs = []

    for picRoot, prefix in [
        (os.path.abspath("input/"), "http://photo.bigasterisk.com/internal/"),
        (os.path.abspath('webinput/'), "http://photo.bigasterisk.com/webinput/"),
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
