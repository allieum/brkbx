import control
from display import post_param_update
from sequence import STEPS_PER_BAR
# from fractions import Fraction

class Param:
    def __init__(self, name, value_fn, printer = None, min_change = None):
        self.value_fn = value_fn
        self.prev = self.value_fn()
        self.name = name
        self.printer =  printer
        self.min_change = min_change

    def get(self):
        val = self.value_fn()
        if val != self.prev:
            if self.min_change is not None and abs(val - self.prev) < self.min_change:
                return self.prev
            if self.printer:
                post_param_update(self.name, self.printer(val))
            else:
                post_param_update(self.name, val)
            self.prev = val
        return val

def step_printer(steps):
    # length = Fraction(steps, STEPS_PER_BAR)
    return f"{steps}/{STEPS_PER_BAR}"

def ms_printer(seconds):
    return f"{round(seconds * 1000, 1)}ms"

params = [
    gate := Param("gate", control.gate_fader.value),
    gate_length := Param("gate length", control.gate_length_fader.value, step_printer),
    latch_length := Param("latch length", control.latch_length_fader.value, step_printer),
    flip_length := Param("flip length", control.flip_speed_fader.value, step_printer),
    volume := Param("volume", control.volume_knob.value, lambda x: round(x * 100), min_change=0.1),
    ts_grain := Param("TS grain", control.timestretch_grain_knob.value, ms_printer, min_change=0.01),
    bank := Param("bank", lambda: control.current_bank, lambda bank: bank + 1),
    lpf_hpf := Param("LPF/HPF", control.filter_knob.value)
    # todo banks, bpm, pitch stick
]
