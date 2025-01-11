from control import joystick, joystick_recording, record_current_history
from sequence import StepParams
from sample import CHUNKS
from utility import get_logger

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

    def get(self, step: int | None, length: int) -> int:
        if step is None:
            return self.step if self.step else 0
        if self.step is None or self.reps and self.count >= self.reps * length:
            # self.length = length
            self.step = step - step % 4
            # self.step = step - step % length
            self.count = 0
        self.count += 1
        return self.step + step % length

    def cancel(self):
        self.step = None
        self.count = 0

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

class JoystickMode:
    def update(self, params: StepParams):
        pass

    def has_input(self, step = None):
        x, y = joystick.position(step)
        return abs(x) > 0.2 or abs(y) > 0.2

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
        if x > 0.2:
            length = 4 if x > 0.9 else 2 if x > 0.5 else 1
            params.step = self.latch.get(params.step, length)
            if params.step % length != 0:
                params.set_pitch(self.pitch.get(0))
            elif y < -0.7:
                params.set_pitch(self.pitch.get(-1))
                # self.latch.reps = 4
            # elif y < -0.2:
            #     params.set_pitch(self.pitch.get(-1, limit=length * 4))
            elif y > 0.7:
                params.set_pitch(self.pitch.get(+1))
            # elif y > 0.2:
            #     params.set_pitch(self.pitch.get(+1, limit=length * 4))
                # self.latch.reps = 2
            else:
                self.latch.reps = None
        else:
            self.latch.cancel()
            self.pitch.cancel()

        self.gate.ratio = 1 if x > 0 else 1 + x
        self.gate.period = 2 if y < -0.5 else 8 if y > 0.5 else 4
        self.gate.period //= 2
        # TODO !play_step could be expressed as params.step = None
        # if params.step:
        #     params.play_step = self.gate.is_on(params.step)
        if x < -0.1:
            rate = 0.5
            params.stretch_rate *= rate
            params.step = self.stretch.get_slice(params.step, rate)
        else:
            self.stretch.cancel()


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
            params.set_pitch(self.pitch.get(+1))
            params.step = self.latch.get(params.step, 1)
        elif y > 0.5:
            params.set_pitch(self.pitch.get(-1))
            params.step = self.latch.get(params.step, 1)
        else:
            self.pitch.cancel()
            self.latch.cancel()


# joystick_mode = PitchStretchMode()
joystick_mode = GateRepeatMode()
