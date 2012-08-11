from __future__ import division

def fitSize(w, h, maxW, maxH):
    scl = min(maxW / w, maxH / h)
    return int(round(w * scl)), int(round(h * scl))
