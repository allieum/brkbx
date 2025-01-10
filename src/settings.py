from control import rotary, rotary_pressed
import typing
import utility

logger = utility.get_logger(__name__)

class RotarySetting:
    SAMPLE = 0
    BPM = 1

class RotarySettings:
    settings = [RotarySetting.SAMPLE, RotarySetting.BPM]
    values = [0, 120]

    def __init__(self):
        self.setting = RotarySetting.SAMPLE
        self.was_pressed = False
        self.prev_value = 0
        self.position_offset = 0

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
        if rotary_pressed() and not self.was_pressed:
            self.was_pressed = True
            self.setting = (self.setting + 1) % len(self.settings)
            logger.info(f"setting changed to {self.setting}")
        if not rotary_pressed():
            self.was_pressed = False
        current = rotary.value()
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
