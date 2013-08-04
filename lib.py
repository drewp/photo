# http://www.stokebloke.com/wordpress/2009/01/27/python-timing-decorator/
import time, logging
tlog = logging.getLogger('timing')
stack = 0
def print_timing(func):
  def wrapper(*arg, **kw):
    global stack
    indent = '  ' * stack
    label = '%s (%s:%s)' % (func.func_name,
                  func.func_code.co_filename,
                  func.func_code.co_firstlineno)
    t1 = time.time()
    tlog.info('%s%s start' % (indent, label))
    try:
        stack = stack + 1
        res = func(*arg, **kw)
        return res
    finally:
        stack = stack - 1
        t2 = time.time()
        tlog.info('%s%s took %0.3f ms', indent, label, (t2-t1)*1000.0)
  return wrapper
