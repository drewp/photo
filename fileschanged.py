"""
wrapper for the fileschanged command
"""
import os, subprocess, logging
log = logging.getLogger('fileschanged')

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
        callback(filename)

def allFiles(topDirs, callback):
    """call callback on every file under all the given dirs. Skips dot files."""
    for topDir in topDirs:
        for root, dirs, files in os.walk(topDir):
            for filename in files:
                # the dot hides emacs partial-save files, which i
                # didn't notice anyway
                if filename.startswith('.'):
                    continue
                filename = os.path.join(root, filename)
                callback(filename)
