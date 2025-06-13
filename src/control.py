from typing import Tuple
from adafruit_simplemath import map_range
from keypad import Keypad
from machine import Pin, ADC, Signal
from rotary_irq_rp2 import RotaryIRQ, Rotary
from collections import deque
import utility

logger = utility.get_logger(__name__)

KNOB1 = Pin("A0")
KNOB2 = Pin("A1")
KNOB3 = Pin("A2")
KNOB4 = Pin("A3")

JOYSTICK_X = Pin("A10")
JOYSTICK_Y = Pin("A11")
JOYSTICK_SEL = Pin("D30", Pin.IN, Pin.PULL_UP)

JOYSTICK2_X = Pin("D40")
JOYSTICK2_Y = Pin("D41")
JOYSTICK2_SEL = Pin("D35", Pin.IN, Pin.PULL_UP)

FADER1 = Pin("A12")
FADER2 = Pin("A13")
FADER3 = Pin("D38")
FADER4 = Pin("D39")

LEDS = [
    SLOW_LED := Pin("D5", Pin.OUT),
    FLIP_LED := Pin("D6", Pin.OUT),
    HOLD_LED := Pin("D23", Pin.OUT),
    PLAY_LED := Pin("D22", Pin.OUT),
]
PLAY_LED.value(0)


ADC_MAX = 65536
JOYSTICK_RECORD_LEN = 32

KEY_ROWS = [Pin("D1", Pin.IN, Pin.PULL_DOWN), Pin("D2", Pin.IN, Pin.PULL_DOWN), Pin("D3", Pin.IN, Pin.PULL_DOWN), Pin("D4", Pin.IN, Pin.PULL_DOWN)]
KEY_COLS = [Pin("D9"), Pin("D10"), Pin("D11"), Pin("D12"), Pin("D0")]


SAMPLE_KEYS = [0, 1, # 2,
               3,
               8, 9, 10, 11]
SNARE_KEYS = [4, 5, # 6,
              7,
              12, 13, 14, 15]
SLOW_KEY = 16
FLIP_KEY = 17
HOLD_KEY = 18
PLAY_KEY = 19
SOUND_KEYS = range(16)
HOLDABLE_KEYS = range(18)
BANK_SIZE = len(SAMPLE_KEYS)
keypad = Keypad(KEY_ROWS, KEY_COLS)

class Pot:
    def __init__(self, pin: Pin, start_val, end_val, continuous: bool, digits = 1):
        self.adc = ADC(pin)
        self.start_val = start_val
        self.end_val = end_val
        self.continuous = continuous
        self.digits = digits

    def value(self):
        val = map_range(self.adc.read_u16(), 0, ADC_MAX, self.start_val, self.end_val)
        if not self.continuous:
            val = round(val)
        return round(val, self.digits)

class SelectorPot():
    def __init__(self, pin: Pin, choices):
        self.choices = choices
        self.knob = Pot(pin, 0, len(choices) - 1, continuous=False)

    def value(self):
        return self.choices[self.knob.value()]

gate_fader = Pot(FADER1, 0, 1, continuous=True)
gate_length_fader = SelectorPot(FADER2, [2, 4, 8, 16, 32])
latch_length_fader = SelectorPot(FADER3, [1, 2, 3, 4, 6, 8, 16, 32])
flip_speed_fader = SelectorPot(FADER4, [1, 2, 4, 8, 16, 32])

timestretch_grain_knob = Pot(KNOB1, 0.0001, 0.080, continuous=True, digits=4)
filter_knob = Pot(KNOB2, -1, 1, continuous=True, digits=2)
knob3 = Pot(KNOB3, -1, 1, continuous=True)
volume_knob = Pot(KNOB4, 0, 1, continuous=True, digits=2)


class Button:
    id = 0

    def __init__(self, pin: Pin | Signal, down_cb=None, up_cb=None):
        self.pin = pin
        self.down_cb = down_cb
        self.up_cb = up_cb
        self.prev_value = self.pin.value()
        self.id = Button.id
        Button.id += 1

    def poll(self) -> bool | None:
        # logger.info(f"polling button {self.id} {self.pin.value()}")
        new_state = None
        if (value := self.pin.value()) != self.prev_value:
            if new_state := self.pin.value() is 1:
                self.down()
            else:
                self.up()
        self.prev_value = value
        return new_state

    def down(self):
        logger.debug(f"button {self.id} pressed")
        if self.down_cb is not None:
            self.down_cb()

    def up(self):
        logger.debug(f"button {self.id} released")
        if self.up_cb is not None:
            self.up_cb()

    def pressed(self):
        return self.pin.value() is 1

class Joystick:
    def __init__(self, x: Pin, y: Pin, sel: Pin):
        self.x = ADC(x)
        self.y = ADC(y)
        self.sel = Signal(sel, invert=True)

    def position(self, step = None) -> Tuple[float, float]:
        # if step and (rec := joystick_recording[step % len(joystick_recording)]) is not None:
        #     return rec
        x = map_range(self.x.read_u16(), 0, ADC_MAX, -1, 1)
        y = map_range(self.y.read_u16(), 0, ADC_MAX, -1, 1)
        return round(x, 1), round(y, 1)

    def pressed(self) -> bool:
        return self.sel.value() is 1


joystick = Joystick(JOYSTICK_X, JOYSTICK_Y, JOYSTICK_SEL)
joystick2 = Joystick(JOYSTICK2_X, JOYSTICK2_Y, JOYSTICK2_SEL)
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
rotary_button_1 = Button(Signal(Pin("D36", Pin.IN, Pin.PULL_UP), invert=True))
rotary_button_2 = Button(Signal(Pin("D37", Pin.IN, Pin.PULL_UP), invert=True))

buttons = [
    # Button(Signal(Pin("D1", Pin.IN, Pin.PULL_UP), invert=True)),
    # Button(Signal(Pin("D2", Pin.IN, Pin.PULL_UP), invert=True)),
    # Button(Signal(Pin("D3", Pin.IN, Pin.PULL_UP), invert=True)),
    # Button(Signal(Pin("D4", Pin.IN, Pin.PULL_UP), invert=True)),
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

NBANKS = 2 # hack
sample_knob = RotaryKnob(RotaryIRQ("D32", "D31",
                                   min_val=0,
                                   max_val=BANK_SIZE * (NBANKS - 1),
                                   range_mode=Rotary.RANGE_BOUNDED,
                                   incr=BANK_SIZE), rotary_button_1)
rotary2 = RotaryKnob(RotaryIRQ(ROT_CLK, ROT_DT, pull_up=True), rotary_button_2)

current_bank = 0
def switch_bank():
    global current_bank
    current_bank = (current_bank + 1) % NBANKS
    # logger.info(f"sample offset set to {current_bank}")
rotary_button_2.down_cb = switch_bank

prev_controls = ()
def print_controls():
    global prev_controls
    values = 1
    # values = timestretch_grain_knob.value()
    # values = (gate_fader.value(), latch_length_fader.value(), fader3.value(), fader4.value(),
    #           gate_length_fader.value(), knob2.value(), knob3.value(), knob4.value())
    if values == prev_controls:
        return
    logger.info(f"faders: {values}")
    prev_controls = values
