from typing import Tuple
from adafruit_simplemath import map_range
from machine import Pin, ADC, Signal
from rotary_irq_rp2 import RotaryIRQ

JOYSTICK_X = Pin("A10")
JOYSTICK_Y = Pin("A11")
JOYSTICK_SEL = Pin("D30", Pin.IN, Pin.PULL_UP)

ADC_MAX = 65536


class Joystick:
    def __init__(self, x: Pin, y: Pin, sel: Pin):
        self.x = ADC(x)
        self.y = ADC(y)
        self.sel = Signal(sel, invert=True)

    def position(self) -> Tuple[float, float]:
        x = map_range(self.x.read_u16(), 0, ADC_MAX, -1, 1)
        y = map_range(self.y.read_u16(), 0, ADC_MAX, -1, 1)
        return round(x, 1), round(y, 1)

    def pressed(self) -> bool:
        return self.sel.value() is 1


joystick = Joystick(JOYSTICK_X, JOYSTICK_Y, JOYSTICK_SEL)


ROT_CLK = "D33"
ROT_DT = "D34"
rotary_button = Signal(Pin("D35", Pin.IN, Pin.PULL_UP), invert=True)

rotary = RotaryIRQ(ROT_CLK, ROT_DT)
def rotary_pressed():
    return rotary_button.value() is 1
