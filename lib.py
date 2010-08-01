# http://www.stokebloke.com/wordpress/2009/01/27/python-timing-decorator/
import time, logging
tlog = logging.getLogger('timing')
def print_timing(func):
  def wrapper(*arg, **kw):
    t1 = time.time()
    try:
        res = func(*arg, **kw)
        return res
    finally:
        t2 = time.time()
        tlog.info('%s took %0.3f ms', func.func_name, (t2-t1)*1000.0)
  return wrapper
