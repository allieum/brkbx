from sample import Sample


STEPS_PER_BAR = 32

class StepParams:
    def __init__(self, step, pitch_rate, stretch_rate, sample):
        self.step = step
        self.pitch_rate = pitch_rate
        self.stretch_rate = stretch_rate
        self.play_step = True
        self.sample: Sample = sample

    def modulate(self, joystick_mode):
        """
        JoystickMode from fx.py
        """
        joystick_mode.update(self)

    def alter_pitch(self, semitones):
        """
        alter pitch chromatically without affecting length
        """
        halfstep_ratio = 1.05946  # 12th root of 2
        shift_rate = halfstep_ratio ** semitones
        self.pitch_rate *= shift_rate
        self.stretch_rate /= shift_rate
