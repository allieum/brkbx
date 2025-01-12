from typing import Tuple
from adafruit_simplemath import map_range
from machine import Pin, ADC, Signal
from rotary_irq_rp2 import RotaryIRQ
from collections import deque
import utility

logger = utility.get_logger(__name__)

KNOB1 = Pin("A0")
KNOB2 = Pin("A2")
KNOB3 = Pin("A3")
KNOB4 = Pin("A1")

JOYSTICK_X = Pin("A10")
JOYSTICK_Y = Pin("A11")
JOYSTICK_SEL = Pin("D30", Pin.IN, Pin.PULL_UP)

ADC_MAX = 65536
JOYSTICK_RECORD_LEN = 32

class Button:
    def __init__(self, pin: Pin | Signal, down_cb=None, up_cb=None):
        self.pin = pin
        self.down_cb = down_cb
        self.up_cb = up_cb
        self.prev_value = self.pin.value()

    def poll(self) -> bool | None:
        new_state = None
        if (value := self.pin.value()) != self.prev_value:
            if new_state := self.pin.value() is 1:
                self.down()
            else:
                self.up()
        self.prev_value = value
        return new_state

    def down(self):
        logger.info(f"button {self.pin} pressed")
        if self.down_cb is not None:
            self.down_cb()

    def up(self):
        logger.info(f"button {self.pin} released")
        if self.up_cb is not None:
            self.up_cb()

class Joystick:
    def __init__(self, x: Pin, y: Pin, sel: Pin):
        self.x = ADC(x)
        self.y = ADC(y)
        self.sel = Signal(sel, invert=True)

    def position(self, step = None) -> Tuple[float, float]:
        if step and (rec := joystick_recording[step % len(joystick_recording)]) is not None:
            return rec
        x = map_range(self.x.read_u16(), 0, ADC_MAX, -1, 1)
        y = map_range(self.y.read_u16(), 0, ADC_MAX, -1, 1)
        return round(x, 1), round(y, 1)

    def pressed(self) -> bool:
        return self.sel.value() is 1


joystick = Joystick(JOYSTICK_X, JOYSTICK_Y, JOYSTICK_SEL)
joystick_history = deque([], 8)
joystick_recording = [None] * JOYSTICK_RECORD_LEN

def log_joystick():
    joystick_history.append(joystick.position())

def record_current_history(step):
    i = 0
    while len(joystick_history) > 0:
        entry = joystick_history.pop()
        entry_step = (step - i) % JOYSTICK_RECORD_LEN
        i += 1
        joystick_recording[entry_step] = entry

ROT_CLK = "D33"
ROT_DT = "D34"
rotary_button_1 = Button(Signal(Pin("D35", Pin.IN, Pin.PULL_UP), invert=True))
rotary_button_2 = Button(Signal(Pin("D36", Pin.IN, Pin.PULL_UP), invert=True))

buttons = [
    Button(Signal(Pin("D1", Pin.IN, Pin.PULL_UP), invert=True)),
    Button(Signal(Pin("D2", Pin.IN, Pin.PULL_UP), invert=True)),
    Button(Signal(Pin("D3", Pin.IN, Pin.PULL_UP), invert=True)),
    Button(Signal(Pin("D4", Pin.IN, Pin.PULL_UP), invert=True)),
]

class RotaryKnob:
    def __init__(self, enc: RotaryIRQ, button: Button):
        self.enc = enc
        self.button = button
        self.prev_value = self.enc.value()

    def pressed(self):
        return self.button.pin.value() is 1

    def poll(self) -> int:
        delta = (value := self.enc.value()) - self.prev_value
        self.prev_value = value
        self.button.poll()
        return delta

    def value(self):
        return self.enc.value()

rotary1 = RotaryKnob(RotaryIRQ(ROT_CLK, ROT_DT), rotary_button_1)
rotary2 = RotaryKnob(RotaryIRQ("D32", "D31", pull_up=True), rotary_button_2)
