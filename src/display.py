from machine import I2C, Pin
from ssd1306 import SSD1306_I2C
from utility import get_logger
from clock import get_running_clock
import asyncio

logger = get_logger(__name__)

DISABLE_DISPLAY = False

W = 128
H = 64
CHAR_SIZE = 8
MAX_HORZ_CHARS = W // CHAR_SIZE
oled = None
def init():
    global oled
    if DISABLE_DISPLAY:
        logger.info("running without display because DISABLE_DISPLAY flag is set")
        return
    try:
        i2c = I2C(id=0)
        oled = SSD1306_I2C(W, H, i2c, addr=0x3d)
        oled.fill(0)
        # center_text("hello worldzo ok")
        oled.show()
        logger.info("initialized oled display")
    except Exception as e:
        logger.error(f"failed to set up display:\n{e}")

def center_text(msg):
    if not oled:
        return
    y = H // 2 - CHAR_SIZE
    x = W // 2 - len(msg) * CHAR_SIZE // 2
    oled.text(msg, x, y)

pending_update = None
def post_param_update(name, value):
    global pending_update
    pending_update = (name, value)
    logger.info(f"posting param update {name}: {value}")

def show_param_update(name, value):
    length = len(f"{name} {value}")
    padding = MAX_HORZ_CHARS - length
    if padding < 0:
        name = name[:padding]
        padding = 0
    if padding > 4:
        padding -= 4
    center_text(f"{name}{' ' * (padding + 1)}{value}")

DISPLAY_UPDATE_INTERVAL = 0.3  # seconds between display checks
DISPLAY_MESSAGE_DURATION = 3.0  # seconds to show message
DISPLAY_STEPS = int(DISPLAY_MESSAGE_DURATION / DISPLAY_UPDATE_INTERVAL)

async def update_display():
    global pending_update
    if not oled:
        return
    while True:
        # workaround: only update display when clock isn't running, avoid 28ms wrench
        if pending_update and get_running_clock() is None:
            logger.info(f"updating display with param update")
            name, value = pending_update
            oled.fill(0)
            show_param_update(name, value)
            oled.show()
            pending_update = None

            logger.info(f"finished updating display with param update")
            for _ in range(DISPLAY_STEPS):
                if pending_update:
                    break
                await asyncio.sleep(DISPLAY_UPDATE_INTERVAL)

            if not pending_update:
                logger.info(f"clearing screen")
                oled.fill(0)
                oled.show()
                logger.info(f"done clearing screen")

        await asyncio.sleep(DISPLAY_UPDATE_INTERVAL)
