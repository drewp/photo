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

import boot
import subprocess, time, optparse, logging
from multiprocessing import Pool, Queue, Process
from photos import justCache
from urls import photoUri
from picdirs import picSubDirs
from scanFs import imageExtensions, videoExtensions

def ProgressReport(q, total):
    # unfinished.
    seen = 0
    lastReportStart = time.time()
    lastReportFiles = 0
    reportStep = 5
    
    for item in iter(q.get, 'END'):
        seen = seen + 1
        now = time.time()
        if now > lastReportStart + reportStep:
            perFile = (now - lastReportStart) / (seen - lastReportFiles)
            log.info("finished %s of %s: %s, est %s min left" % (seen, total, item, round((total - seen) * perFile / 60)))
            lastReportStart = now

def cacheFile((i, filename)):
    try:
        justCache(photoUri(filename),
                  grid=opts.grid, gridLogDir='/my/log/grid',
                  sizes=[75,250,600])
    except (subprocess.CalledProcessError, IOError), e:
        log.error("  failed: %s", e)
    progressQueue.put("%s" % filename)

def findFiles(opts):
    cmd = ["/usr/bin/find"]
    cmd += picSubDirs(quick=opts.quick)
    cmd += "-regextype posix-egrep -name .xvpics -prune -type f -o".split()
    cmd += ['(', '-iregex',
            r'.*\.(%s)' % '|'.join(e.strip('.') for e in imageExtensions + videoExtensions), ')']
    log.debug(repr(cmd))
    files = [f.strip() for f in subprocess.Popen(cmd,
                     stdout=subprocess.PIPE).communicate()[0].splitlines()]

    if opts.pat:
        log.info("found %s files, reducing to pattern", len(files))
        files = [f for f in files if opts.pat in f]
    return files

if __name__ == '__main__':
    parser = optparse.OptionParser()
    parser.add_option("--quick", action="store_true", help="only scan a few files")
    parser.add_option("--pat", help="only scan files with this substring")
    parser.add_option("-d", action="store_true", help="debug logs")
    parser.add_option("--grid", action="store_true", help="run resizes as jobs on SGE grid")
    opts, args = parser.parse_args()

    log = boot.log
    if not opts.d:
        log.setLevel(logging.INFO)

    files = findFiles(opts)

    progressQueue = Queue()
    Process(target=ProgressReport, args=(progressQueue, len(files))).start()

    pool = Pool(processes=4)
    result = pool.map(cacheFile, enumerate(files), chunksize=5)
    
    progressQueue.put('END')
    print "finished, %s results" % len(result)
