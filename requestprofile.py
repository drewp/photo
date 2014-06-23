import time

def timed(func, *args, **kw):
    t1 = time.time()
    result = func(*args, **kw)
    return result, time.time() - t1

