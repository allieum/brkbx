import control
import sample
from sample import set_current_sample
from clock import internal_clock, clock_running, get_current_step
import fx

ephemeral_start = False
sample.voice_on = True

class ButtonDown:
    def __init__(self, i = None, cb = None):
        self.cb = cb
        self.i = i

    def __call__(self):
        self.down()
        if self.cb:
            self.cb()

    def down(self):
        global ephemeral_start
        if not clock_running():
            ephemeral_start = True
            internal_clock.start()
        # fx.button_latch.activate(i * 2, quantize=not ephemeral_start)
        if self.i:
            set_current_sample(control.rotary1.value() + self.i)
        sample.voice_on = True

class ButtonUp:
    def __init__(self, cb = None):
        self.cb = cb

    def __call__(self):
        self.up()
        if self.cb:
            self.cb()

    def up(self):
        global ephemeral_start
        if hold or control.keypad.any_pressed(control.SOUND_KEYS):
            return
        if internal_clock.play_mode and ephemeral_start:
            internal_clock.stop()
            ephemeral_start = False
        # fx.button_latch.cancel()

class SnareDown(ButtonDown):
    def cb(self):
        fx.button_latch.activate(8, quantize=not ephemeral_start)

class SnareUp(ButtonUp):
    def cb(self):
        fx.button_latch.cancel()

class SlowDown(ButtonDown):
    def cb(self):
        fx.button_stretch.get_slice(get_current_step(), 0.5)

class SlowUp(ButtonUp):
    def cb(self):
        fx.button_stretch.cancel()


hold = False
def toggle_hold():
    global hold
    hold = not hold

def init():
    for i, key in enumerate(control.SAMPLE_KEYS):
        control.keypad.on(key, ButtonDown(i), ButtonUp())
    for i, key in enumerate(control.SNARE_KEYS):
        control.keypad.on(key, SnareDown(i), SnareUp())

    control.keypad.on(control.PLAY_KEY, internal_clock.toggle)
    control.keypad.on(control.HOLD_KEY, toggle_hold)
    control.keypad.on(control.SLOW_KEY, SlowDown(), SlowUp())
