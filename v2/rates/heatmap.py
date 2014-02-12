from __future__ import division
import math,  tempfile
import rpy2.robjects as ro
from rpy2.robjects.packages import importr
from rpy2.robjects.lib import grid

def makeImage(rates):
    out = tempfile.NamedTemporaryFile(suffix='.png')

    grdevices = importr('grDevices')
    grdevices.png(file=out.name, width=512, height=512)
    try:
        grid.newpage()
        lt = grid.layout(1, 1)
        vp = grid.viewport(layout = lt)
        vp.push()

        vp = grid.viewport(**{'layout.pos.col':1, 'layout.pos.row': 1})

        for row, (year, count) in enumerate(sorted(rates['byYear'].items())):
            grid.rect(x=grid.unit(.5, "npc"),
                      y=grid.unit(row / len(rates['byYear']), "npc"),
                      width=grid.unit(count / 15000, "npc"),
                      height=grid.unit(.95 / len(rates['byYear']), "npc"),
                      vp = vp).draw()
        
    finally:
        grdevices.dev_off()
    return open(out.name).read()
