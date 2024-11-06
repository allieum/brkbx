# workaround because pyright finds cpython logging instead of micropython-logging
# pyright: reportIncompatibleMethodOverride = false
import logging
import time

_level_dict = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
    "NOTSET": logging.NOTSET,
}
# teensy4.1 only has seconds in time.time() so use an alt Formatter
# as a hack to include more fine grained (relative) time
class UsFormatter(logging.Formatter):
    def formatTime(self, *_):
        return f"{time.ticks_us() / 1000000:10.6f}"

format_str = '%(asctime)s - %(name)s - %(levelname)s: %(message)s'
level = logging.INFO
def get_logger(name, level_str="INFO"):
    level = _level_dict[level_str]
    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(UsFormatter(format_str))
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)
    return logger

logger = get_logger(__name__)

def timed_function(f, *args, **kwargs):
    myname = str(f).split(' ')[1]
    def new_func(*args, **kwargs):
        t = time.ticks_us()
        result = f(*args, **kwargs)
        delta = time.ticks_diff(time.ticks_us(), t)
        logger.info('Function {} took {:6.3f}ms'.format(myname, delta/1000))
        return result
    return new_func

