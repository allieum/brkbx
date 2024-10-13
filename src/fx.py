# let's do timestretch and pitch mod next :)
from control import joystick
from sequence import StepParams

class Gate:
    def __init__(self):
        self.period = 4
        self.ratio = 1.0

class Latch:
    def __init__(self):
        self.step: int | None = None
        self.reps: int | None = None
        # self.length = 1
        self.count = 0

    def get(self, step: int, length: int) -> int:
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

class JoystickMode:
    def update(self, params: StepParams):
        pass

class GateRepeatMode(JoystickMode):
    def __init__(self):
        self.latch = Latch()
        self.gate = Gate()

    def update(self, params: StepParams):
        x, y = joystick.position()
        if x > 0.2:
            length = 4 if x > 0.9 else 2 if x > 0.5 else 1
            params.step = self.latch.get(params.step, length)
            if y < -0.5:
                self.latch.reps = 4
            elif y > 0.5:
                self.latch.reps = 2
            else:
                self.latch.reps = None
        else:
            self.latch.cancel()

        self.gate.ratio = 1 if x > 0 else 1 + x
        self.gate.period = 2 if y < -0.5 else 8 if y > 0.5 else 4
        on_steps = self.gate.ratio * self.gate.period
        params.play_step = params.step % self.gate.period <= on_steps
joystick_mode = GateRepeatMode()


