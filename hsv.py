import numpy

def hsv_from_rgb(image):
    # http://stackoverflow.com/questions/4890373/detecting-thresholds-in-hsv-color-space-from-rgb-using-python-pil
    r, g, b = image[:,:,0], image[:,:,1], image[:,:,2]
    m, M = numpy.min(image[:,:,:3], 2), numpy.max(image[:,:,:3], 2)
    d = M - m

    # Chroma and Value
    c = d
    v = M

    # Hue
    h = numpy.select([c == 0, r == M, g == M, b == M],
                     [0,
                      ((g - b) / c) % 6,
                      (2 + ((b - r) / c)),
                      (4 + ((r - g) / c))],
                     default=0) * 60

    # Saturation
    s = numpy.select([c == 0, c != 0], [0, c/v])

    return numpy.array([h, s, v]).transpose((1,2,0))
