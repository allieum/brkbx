from control import RotaryKnob, sample_knob
import typing
import utility

logger = utility.get_logger(__name__)

class RotarySetting:
    SAMPLE = 0
    BPM = 1

class RotarySettings:
    settings = [RotarySetting.SAMPLE, RotarySetting.BPM]
    values = [0, 120]

    def __init__(self, rotary: RotaryKnob):
        self.setting = RotarySetting.SAMPLE
        self.was_pressed = False
        self.prev_value = 0
        self.position_offset = 0
        self.rotary = rotary

        #
        # example:
#    setting  |  rotary.value()  |  setting value
#    SAMPLE      0                  0
#    SAMPLE      1                  1
#    SAMPLE      2                  2
#    BPM         2                  0
#
#
#
    def update(self) -> typing.Any | None:
        if self.rotary.pressed() and not self.was_pressed:
            self.was_pressed = True
            self.setting = (self.setting + 1) % len(self.settings)
            logger.info(f"setting changed to {self.setting}")
        if not self.rotary.pressed():
            self.was_pressed = False
        current = self.rotary.value()
        delta = current - self.prev_value
        if delta == 0:
            return
        self.prev_value = current
        self.values[self.setting] += delta
        return self.values[self.setting]

    def set(self, setting, value):
        self.values[setting] = value

    def get(self, setting, value):
        return self.values[setting]
