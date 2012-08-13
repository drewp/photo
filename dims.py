from __future__ import division
import subprocess, re

def fitSize(w, h, maxW, maxH):
    scl = min(maxW / w, maxH / h)
    return int(round(w * scl)), int(round(h * scl))

def avprobe(filename):
    return subprocess.Popen(['/usr/bin/avprobe', filename],
                             stderr=subprocess.PIPE).communicate()[1]

def videoSize(filename, probe=None):
    """also works for jpg. i'm not sure if it's slow"""
    if probe is None:
        probe = avprobe(filename)
    m = re.search(r'Video.*?(\d+)x(\d+)', probe)
    w, h = map(int, m.groups())
    return w, h
