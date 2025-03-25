import control
import sample
from clock import internal_clock, clock_running
import fx

ephemeral_start = False
sample.voice_on = True

class ButtonDown:
    ephemeral_start = False

    def __init__(self, cb = None):
        self.cb = cb

    def __call__(self):
        if self.cb:
            self.cb()

def create_button_down(i):
    def f():
        global ephemeral_start, current_sample
        if not clock_running():
            ephemeral_start = True
            internal_clock.start()
        # fx.button_latch.activate(i * 2, quantize=not ephemeral_start)
        current_sample = sample.samples[(control.rotary1.value() + i) % len(sample.samples)]
        sample.voice_on = True
    return f
def create_snare_down(i):
    def f():
        global ephemeral_start, current_sample
        if not clock_running():
            ephemeral_start = True
            internal_clock.start()
        fx.button_latch.activate(8, quantize=not ephemeral_start)
        current_sample = sample.samples[(control.rotary1.value() + i) % len(sample.samples)]
        sample.voice_on = True
    return f

def button_up():
    global ephemeral_start
    if hold or control.keypad.any_pressed(control.SOUND_KEYS):
        return
    if internal_clock.play_mode and ephemeral_start:
        internal_clock.stop()
        ephemeral_start = False
    # fx.button_latch.cancel()
    sample.voice_on = False
def snare_up():
    global ephemeral_start
    fx.button_latch.cancel()
    if hold or control.keypad.any_pressed(control.SOUND_KEYS):
        return
    if internal_clock.play_mode and ephemeral_start:
        internal_clock.stop()
        ephemeral_start = False
    sample.voice_on = False

hold = False
def toggle_hold():
    global hold
    hold = not hold

def init():
    for i, key in enumerate(control.SAMPLE_KEYS):
        control.keypad.on(key, create_button_down(i), button_up)
    for i, key in enumerate(control.SNARE_KEYS):
        control.keypad.on(key, create_snare_down(i), snare_up)

    control.keypad.on(control.PLAY_KEY, internal_clock.toggle)
    control.keypad.on(control.HOLD_KEY, toggle_hold)
