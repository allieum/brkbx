import control
from control import joystick, joystick_recording, record_current_history
from sequence import StepParams
from sample import CHUNKS, get_samples, set_current_sample, get_current_sample
from utility import get_logger
from ui import any_pressed_or_held

import random

logger = get_logger(__name__)


class Pitch:
    def __init__(self) -> None:
        self.semitones = 0

    def get(self, shift: int, limit = None):
        self.semitones += shift
        if limit and abs(self.semitones) > limit:
            self.semitones = 0
        return self.semitones

    def cancel(self):
        self.semitones = 0

class Gate:
    def __init__(self):
        self.period: int = 4
        self.ratio = 1.0
    def is_on(self, step):
        on_steps = self.ratio * self.period
        return step % self.period <= on_steps

class Latch:
    def __init__(self):
        self.step: int | None = None
        self.reps: int | None = None
        # self.length = 1
        self.count = 0
        self.start_step = None
        self.samples = []
        self.current_sample = 0

    def chain(self, sample):
        self.samples.append(sample)

    def unchain(self, sample):
        try:
            self.samples.remove(sample)
            self.current_sample %= len(self.samples)
        except:
            logger.error(f"couldn't remove sample from chain")

    def activate(self, step: int, quantize=True):
        # self.length = length
        delta = step % 4 if quantize else 0
        self.step = step - delta
        logger.info(f"latching on step {step} -> quantized to {self.step}")
        # self.step = step - step % length
        self.count = 0
        self.start_step = None

    def get(self, step: int | None, length: int, start_step = None, quantize=True) -> int:
        if step is None:
            return self.step if self.step else 0
        if self.step is None or self.reps and self.count >= self.reps * length:
            self.activate(step, quantize)
        if start_step:
            self.start_step = start_step
        if self.start_step is None:
            self.start_step = step
        self.count += 1
        if len(self.samples) > 1 and self.count % length == 0:
            s = self.samples[self.current_sample % len(self.samples)]
            logger.info(f"setting chained sample to {s}")
            set_current_sample(s)
            self.current_sample = (self.current_sample + 1) % len(self.samples)

        logger.info(f"self.step {self.step} step={step} start step = {self.start_step} length {length}")
        return self.step + (step - self.start_step) % length

    def is_active(self):
        return self.step is not None

    def cancel(self):
        if not self.is_active():
            return
        self.step = None
        self.count = 0
        self.samples = []
        logger.info("latch cancelled")

class Stretch:
    def __init__(self) -> None:
        self.stretch_start = None

    def get_slice(self, step: int, rate: float):
        if self.stretch_start is None:
            self.stretch_start = step
            self.stretch_start -= self.stretch_start % 8
        steps = (step - self.stretch_start) % (CHUNKS / rate)
        stretched_slice = (self.stretch_start + rate * steps) % CHUNKS
        if stretched_slice == round(stretched_slice):
            logger.info(f"stretched slice {stretched_slice}")
            return int(stretched_slice)
        else:
            return None

    def is_active(self):
        return self.stretch_start is not None

    def cancel(self):
        self.stretch_start = None

class SampleFlip:
    def __init__(self):
        self.flipping = False
        self.last_flip = None
        self.original_sample = None

    def flip_sample(self, step):
        first_time = self.last_flip is None
        if self.flipping and (first_time or step - self.last_flip >= control.flip_speed_fader.value()):
            # get a random one
            self.last_flip = step
            set_current_sample(random.randint(0, len(get_samples()) - 1))

    def cancel(self):
        self.flipping = False
        self.last_flip = 0
        if self.original_sample:
            set_current_sample(self.original_sample)

    def activate(self):
        self.flipping = True
        self.original_sample = get_current_sample().i
flip = SampleFlip()

class JoystickMode:
    def update(self, params: StepParams):
        pass

    def has_input(self, step = None):
        x, y = joystick.position(step)
        return abs(x) > 0.2 or abs(y) > 0.2

button_latch = Latch()
button_stretch = Stretch()
class GateRepeatMode(JoystickMode):
    def __init__(self):
        self.latch = Latch()
        self.gate = Gate()
        self.pitch = Pitch()
        self.stretch = Stretch()

    def update(self, params: StepParams):
        x, y = joystick.position(params.step)
        if joystick.pressed():
            record_current_history(params.step)
        base_length = control.latch_length_fader.value()
        length = 4 if x > 0.9 else 2 if x > 0.5 else 1
        length *= base_length


        # length = control.latch_length_fader.value()
        # logger.info(f"{length}")
        if x > 0.1:
            params.step = self.latch.get(params.step, length)
        if params.step % length != 0:
            params.alter_pitch(self.pitch.get(0))
        elif y < -0.7:
            params.alter_pitch(self.pitch.get(-1))
            # self.latch.reps = 4
        # elif y < -0.2
        #     params.set_pitch(self.pitch.get(-1, limit=length * 4))
        elif y > 0.7:
            params.alter_pitch(self.pitch.get(+1))

        x2, y2 = control.joystick2.position()
        if abs(x2) > 0.1 or abs(y2) > 0.1:
            pitch_mod = round(6 * (x2 + y2))
            params.alter_pitch(pitch_mod)

        button_length = length if x > 0.1 else control.latch_length_fader.value()
        if button_latch.is_active():
            params.step = button_latch.get(params.step, button_length)
        # elif y > 0.2:
        #     params.set_pitch(self.pitch.get(+1, limit=length * 4))
            # self.latch.reps = 2
        # else:
            # self.latch.reps = None
        if abs(x) <= 0.1:
            self.latch.cancel()
        if abs(y) <= 0.1:
            self.pitch.cancel()

        gate_knob = control.gate_fader.value()
        self.gate.ratio = 1 if x > 0.3 else 1.2 + x if x < -0.3 else gate_knob
        self.gate.period = 2 if y < -0.5 else 4 if y > 0.5 else control.gate_length_fader.value()
        if any_pressed_or_held(control.SNARE_KEYS):
            self.gate.period = length * max(1, len(button_latch.samples)) * (control.gate_length_fader.value() // 8 + 1)
        # self.gate.period //= 2
        # TODO !play_step could be expressed as params.step = None
        # if params.step:
        #     params.play_step = self.gate.is_on(params.step)
        if x < -0.1:
            rate = 0.5
            params.stretch_rate *= rate
            params.step = self.stretch.get_slice(params.step, rate)
        else:
            self.stretch.cancel()
        if button_stretch.is_active():
            params.step = button_stretch.get_slice(params.step or 0, 0.5)


class PitchStretchMode(JoystickMode):
    def __init__(self) -> None:
        self.stretch = Stretch()
        self.pitch = Pitch()
        self.latch = Latch()
    def update(self, params: StepParams):
        x, y = joystick.position()
        if x < -0.5:
            rate = 0.5
            params.stretch_rate *= rate
            params.step = self.stretch.get_slice(params.step, rate)
        else:
            self.stretch.cancel()

        if y < -0.5:
            params.alter_pitch(self.pitch.get(+1))
            params.step = self.latch.get(params.step, 1, params.step)
        elif y > 0.5:
            params.alter_pitch(self.pitch.get(-1))
            params.step = self.latch.get(params.step, 1, params.step)
        else:
            self.pitch.cancel()
            self.latch.cancel()


# joystick_mode = PitchStretchMode()
joystick_mode = GateRepeatMode()

def stretch_active():
    return joystick_mode.stretch.is_active() or button_stretch.is_active()
