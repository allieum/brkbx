import control
import sample
from sample import set_current_sample
from clock import internal_clock, clock_running, get_current_step
import fx
import utility

logger = utility.get_logger(__name__)

ephemeral_start = False
sample.voice_on = True

class ButtonDown:
    def __init__(self, i = None):
        self.i = i

    def __call__(self):
        self.down()
        self.action()

    def action(self):
        pass

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
    def __call__(self):
        self.up()
        self.action()

    def action(self):
        pass

    def up(self):
        global ephemeral_start
        if hold or control.keypad.any_pressed(control.SOUND_KEYS):
            return
        if internal_clock.play_mode and ephemeral_start:
            internal_clock.stop()
            ephemeral_start = False
        sample.voice_on = False

class SnareDown(ButtonDown):
    def action(self):
        logger.info(f"snare callback")
        fx.button_latch.activate(8, quantize=not ephemeral_start)

class SnareUp(ButtonUp):
    def action(self):
        fx.button_latch.cancel()

class SlowDown(ButtonDown):
    def action(self):
        fx.button_stretch.get_slice(get_current_step(), 0.5)

class SlowUp(ButtonUp):
    def action(self):
        fx.button_stretch.cancel()

class FlipDown(ButtonDown):
    def action(self):
        fx.flip.activate()

class FlipUp(ButtonUp):
    def action(self):
        fx.flip.cancel()

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
