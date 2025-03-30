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

    def __call__(self, key):
        self.down(key)
        self.action()

    def action(self):
        pass

    def down(self, key):
        global ephemeral_start, hold_only_press
        if held[key]:
            held[key] = False
            borrowed_cbs.remove((key, control.keypad.up_cb[key]))
        if control.keypad.any_pressed([control.HOLD_KEY]):
            held[key] = True
            hold_only_press = False
        if not clock_running():
            ephemeral_start = True
            internal_clock.start()
        # fx.button_latch.activate(i * 2, quantize=not ephemeral_start)
        if self.i:
            set_current_sample(control.rotary1.value() + self.i)
        sample.voice_on = True

class ButtonUp:
    def __call__(self, key):
        if held[key]:
            borrowed_cbs.append((key, control.keypad.up_cb[key]))
            return
        self.up()
        self.action()

    def action(self):
        pass

    def up(self):
        global ephemeral_start
        if (i := active_sample_key()) is not None:
            set_current_sample(control.rotary1.value() + i)
        if any_pressed_or_held(control.SOUND_KEYS):
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
        logger.info(f"activated sample flip")
        fx.flip.activate()

class FlipUp(ButtonUp):
    def action(self):
        logger.info(f"cancelled sample flip")
        fx.flip.cancel()

held = [False] * len(control.HOLDABLE_KEYS)
borrowed_cbs = []
hold_only_press = False
def hold_down(*_):
    global borrowed_cbs, hold_only_press
    hold_only_press = True

    for pressed in control.keypad.any_pressed(control.HOLDABLE_KEYS):
        held[pressed] = True
        hold_only_press = False

def hold_up(*_):
    global borrowed_cbs, hold_only_press
    if not hold_only_press:
        return
    for key in [k for k in control.HOLDABLE_KEYS if held[k]]:
        held[key] = False
    for key, cb in borrowed_cbs:
        cb(key)
    borrowed_cbs = []

def active_sample_key() -> None | int:
    for key in control.keypad.any_pressed(control.SAMPLE_KEYS):
        return key
    for key in control.keypad.any_pressed(control.SNARE_KEYS):
        return key - control.SNARE_OFFSET
    for key in control.SAMPLE_KEYS:
        if held[key]:
            return key
    for key in control.SNARE_KEYS:
        if held[key]:
            return key - control.SNARE_OFFSET
    return None

def any_pressed_or_held(keys):
    return control.keypad.any_pressed(keys) or any(held[k] for k in keys)

def update_leds():
    control.PLAY_LED.value(clock_running())
    control.HOLD_LED.value(any(held[k] for k in control.HOLDABLE_KEYS))
    control.FLIP_LED.value(fx.flip.flipping)
    control.SLOW_LED.value(fx.button_stretch.is_active())

def init():
    for i, key in enumerate(control.SAMPLE_KEYS):
        control.keypad.on(key, ButtonDown(i), ButtonUp())
    for i, key in enumerate(control.SNARE_KEYS):
        control.keypad.on(key, SnareDown(i), SnareUp())

    control.keypad.on(control.PLAY_KEY, internal_clock.toggle)
    control.keypad.on(control.HOLD_KEY, hold_down)
    control.keypad.on(control.SLOW_KEY, SlowDown(), SlowUp())
    control.keypad.on(control.FLIP_KEY, FlipDown(), FlipUp())
