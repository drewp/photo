from __future__ import division
import subprocess, re

def fitSize(w, h, maxW, maxH):
    scl = min(maxW / w, maxH / h)
    outW, outH = int(round(w * scl)), int(round(h * scl))
    if outW % 2: outW += 1
    if outH % 2: outH += 1
    return outW, outH
    

def avprobe(filename):
    return subprocess.check_output(['/usr/bin/avprobe', filename],
                                   stderr=subprocess.STDOUT)

def videoSize(filename, probe=None):
    """also works for jpg. i'm not sure if it's slow"""
    if probe is None:
        probe = avprobe(filename)
    m = re.search(r'Video.*?([1-9]\d+)x(\d+)', probe)
    w, h = map(int, m.groups())
    return w, h
