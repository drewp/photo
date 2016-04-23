#!/usr/bin/python

"""
make sure we have the thumb+large sizes of all /my/pic/digicam jpgs
ready for serving. Photo site can make its own if any are missing, but
that will be slower.

this should be run after new photos are imported, and maybe every
night to catch strays.

it would be faster to make the 75px images out of the 600px
images. photos.py should just remember and use its last one resize,
and then we can ask for 600 followed by 75.

testing? use this to remove the last 24h of thumbs:
  find /my/pic/~thumb -mtime -1 -type f -delete
"""
import sys
sys.path.append("/my/site/photo")
import boot
import subprocess, time, optparse, logging, traceback
from multiprocessing.dummy import Pool, Queue, Process

from urls import photoUri
from picdirs import picSubDirs
from scanFs import imageExtensions, videoExtensions
from mediaresource import MediaResource
from db import getGraph

def ProgressReport(q, total):
    # unfinished.
    seen = 0
    lastReportStart = time.time()
    lastReportFiles = 0
    reportStep = 5
    try:
        for item in iter(q.get, 'END'):
            seen = seen + 1
            now = time.time()
            if now > lastReportStart + reportStep:
                perFile = (now - lastReportStart) / (seen - lastReportFiles)
                log.info("finished %s of %s: %s, est %s min left" %
                         (seen, total, item, round((total - seen) * perFile / 60)))
                lastReportStart = now
    except Exception:
        traceback.print_exc()
        raise
        
    log.info("reporter is done")

def findFiles(opts):
    cmd = ["/usr/bin/find"]
    cmd += picSubDirs(quick=opts.quick)
    cmd += "-regextype posix-egrep -name .xvpics -prune -type f -o".split()
    exts = videoExtensions if opts.video else (imageExtensions + videoExtensions)
    cmd += ['(', '-iregex',
            r'.*\.(%s)' % '|'.join(e.strip('.') for e in exts), ')']
    log.debug(repr(cmd))
    files = [f.strip() for f in subprocess.Popen(cmd,
                     stdout=subprocess.PIPE).communicate()[0].splitlines()]

    if opts.pat:
        log.info("found %s files, reducing to pattern", len(files))
        files = [f for f in files if opts.pat in f]
    return files


class Build(object):
    def __init__(self):

        pool = Pool(processes=2)
        self.graph = getGraph()

        files = findFiles(opts)

        self.progressQueue = Queue()
        reporter = Process(target=ProgressReport,
                           args=(self.progressQueue, len(files)))
        reporter.start()
        result = pool.map(self.cacheFile, enumerate(files), chunksize=5)
        self.progressQueue.put('END')
        log.info("finished, %s results", len(result))
        reporter.join()

    def cacheFile(self, (i, filename)):
        log.debug("cacheFile %s" % filename)
        try:
            uri = photoUri(filename)
            m = MediaResource(self.graph, uri)
            # video extension but not isVideo? where do we correct that?
            m.cacheAll()
        except Exception:
            traceback.print_exc()
            
        self.progressQueue.put("%s" % filename)


if __name__ == '__main__':
    parser = optparse.OptionParser()
    parser.add_option("--quick", action="store_true", help="only scan a few files")
    parser.add_option("--pat", help="only scan files with this substring")
    parser.add_option("-d", action="store_true", help="debug logs")
    parser.add_option("--video", action="store_true", help="just videos")
    opts, args = parser.parse_args()

    log = boot.log
    if opts.d:
        log.setLevel(logging.DEBUG)

    Build()
