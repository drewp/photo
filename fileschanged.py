"""
wrapper for the fileschanged command
"""
import time, os, subprocess, logging, traceback
log = logging.getLogger('fileschanged')
log.setLevel(logging.DEBUG)

def fileschanged(topDirs, callback):
    """watch dirs (recursively), calling the given function with the
    name of any file created/modified/deleted. Note that there may be
    a big delay (as if we ran 'find' on all the dirs) before the
    scanning starts to work."""
    
    proc = subprocess.Popen("/usr/bin/fileschanged --recursive --timeout=2 --show=created,changed,deleted".split() + list(topDirs),
                            stdout=subprocess.PIPE)
    # proc.stdout iterator doesn't work
    for line in iter(proc.stdout.readline, None):
        filename = line.strip()
        log.debug("fileschanged: %s" % filename)
        try:
            callback(filename)
        except Exception, e:
            log.error("Error during callback for %s" % filename)
            traceback.print_exc()

def fileschanged_gamin(topDirs, callback):
    """version using gamin, which does not have recursive support. I'd
    have to find subdirs, then add dynamic watches to any new dirs
    that show up."""
    import gamin
    mon = gamin.WatchMonitor()
    def cb(path, event, data):
        fullpath = os.path.join(data, path)
        log.debug("fileschanged: %s" % fullpath)
        return callback(fullpath)
    for d in topDirs:
        mon.watch_directory(d, cb, d)
    while 1:
        mon.handle_events()
        time.sleep(1)
    print "done"


def allFiles(topDirs, callback):
    """call callback on every file under all the given dirs. Skips dot files."""
    for topDir in topDirs:
        for root, dirs, files in os.walk(topDir):
            log.debug("allFiles: %s" % root)
            for filename in files:
                # the dot hides emacs partial-save files, which i
                # didn't notice anyway. todo: this isn't finding dot-directories
                if filename.startswith('.'):
                    continue
                filename = os.path.join(root, filename)
                try:
                    callback(filename)
                except Exception, e:
                    log.error("Error during callback for %s" % filename)
                    traceback.print_exc()
                    
