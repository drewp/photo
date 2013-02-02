#!bin/python

"""
iphone has made images on dropbox named like
'2013-01-13 16.04.56.jpg'
'2013-01-11 15.10.03-1.jpg'

sync to shared disk with names like
'2013-01-13T16-04-56.jpg'
'2013-01-11T15-10-03-1.jpg'


bin/python sync_dropbox.py /home/drewp/Dropbox/Camera\ Uploads\ from\ Kelsi /my/pic/phonecam/ki8



"""
import sys, os, argparse
from twisted.python.filepath import FilePath

def copy(source, dest, mock):
    if mock:
        print "would copy %s to %s" % (f.path, out.path)
        return
        
    if out.exists():
        if out.getsize() == source.getsize():
            print "%s exists. no action." % out.path
            return

    try:
        outDir.makedirs()
    except OSError:
        pass

    out.setContent(f.open().read())
    out.chmod(0644)
    os.utime(out.path, (f.getModificationTime(),
                        f.getModificationTime()))
    print "wrote %s" % out.path

def sync(f, outDir, newerthan, mock):
    out = outDir.child(f.basename().replace(' ', 'T').replace('.', '-', 2))

    if newerthan and out.basename() <= newerthan:
        print "skipping file %s; older than cutoff" % out.path
        continue

    copy(f, out, mock)
    
parser = argparse.ArgumentParser(
    description='sync from dropbox to photo filesystem')
parser.add_argument('--newerthan',
    help="ignore files whose output names don't sort after this string")
parser.add_argument('--destdir', help='output dir')
parser.add_argument('--mock', action='store_true', help='mock mode')
parser.add_argument('--input', help='input filename')
args = parser.parse_args()

outDir = FilePath(args.destdir)

if os.path.isdir(args.input):
    files = FilePath(args.input).children()
else:
    files = [FilePath(args.input)]

for f in files:
    sync(f, outDir, args.newerthan, args.mock)
