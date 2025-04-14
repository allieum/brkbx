from machine import I2C
from ssd1306 import SSD1306_I2C

W = 128
H = 64
CHAR_SIZE = 8

i2c = I2C(id=0)
oled = SSD1306_I2C(W, H, i2c, addr=0x3d)

def center_text(msg):
    y = H // 2 - CHAR_SIZE
    x = W // 2 - len(msg) * CHAR_SIZE // 2
    oled.text(msg, x, y)

oled.fill(0)
# center_text("hello worldzo ok")
oled.show()
