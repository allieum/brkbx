# workaround because pyright finds cpython logging instead of micropython-logging
# pyright: reportIncompatibleMethodOverride = false
import logging
import time

# teensy4.1 only has seconds in time.time() so use an alt Formatter
# as a hack to include more fine grained (relative) time
class UsFormatter(logging.Formatter):
    def formatTime(self, datefmt, record):
        return time.ticks_us() / 1000000

format_str = '%(asctime)s - %(name)s - %(levelname)s: %(message)s'
level = logging.INFO
handler = logging.StreamHandler()
handler.setLevel(level)
handler.setFormatter(UsFormatter(format_str))
def get_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)
    return logger
