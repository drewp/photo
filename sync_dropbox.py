#!bin/python

"""
iphone has made images on dropbox named like
'2013-01-13 16.04.56.jpg'
'2013-01-11 15.10.03-1.jpg'

sync to shared disk with names like
'2013-01-13T16-04-56.jpg'
'2013-01-11T15-10-03-1.jpg'

"""
import boot
import sys, os, argparse, urllib
from twisted.python.filepath import FilePath, _secureEnoughString
import requests
from fileschanged import fileschanged
log = boot.log

def copy(source, dest, mock):
    if mock:
        log.info("would copy %s to %s" % (source.path, dest.path))
        return
        
    if dest.exists():
        if dest.getsize() == source.getsize():
            log.info("%s exists. no action." % dest.path)
            return

    try:
        os.makedirs(dest.dirname())
    except OSError:
        pass

    # dotfiles are ignored by the other fileschanged process that is
    # watching for files to ingest
    tempDest = dest.sibling("."+dest.basename()+_secureEnoughString(dest))
    source.copyTo(tempDest)
    tempDest.chmod(0644)
    os.utime(tempDest.path, (source.getModificationTime(),
                             source.getModificationTime()))
    tempDest.moveTo(dest)
    log.info("wrote %s" % dest.path)
    requests.post('http://bang:9042/', params={'file': dest.path})
    log.info("posted")

def sync(f, outDir, newerthan, mock):
    out = outDir.child(f.basename().replace(' ', 'T').replace('.', '-', 2))

    if newerthan and out.basename() <= newerthan:
        log.info("skipping file %s; older than cutoff" % out.path)
        return

    copy(f, out, mock)
    
parser = argparse.ArgumentParser(
    description='sync from dropbox to photo filesystem')
parser.add_argument('--newerthan',
    help="ignore files whose output names don't sort after this string")
parser.add_argument('--destdir', help='output dir')
parser.add_argument('--mock', action='store_true', help='mock mode')
parser.add_argument('--input', help='input filename or dir-to-watch')
args = parser.parse_args()

outDir = FilePath(args.destdir)

if not os.path.isdir(args.input):
    # single-file mode
    sync(FilePath(args.input), outDir, args.newerthan, args.mock)
else:
    for f in sorted(FilePath(args.input).children()):
        sync(f, outDir, args.newerthan, args.mock)

    def onChange(filename):
        sync(FilePath(filename), outDir, args.newerthan, args.mock)
    fileschanged([args.input], onChange)

