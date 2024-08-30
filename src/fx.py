class Gate:
    def __init__(self):
        self.period = 4
        self.ratio = 1.0


# next, allow different lengths! then can change length while step stays the same?
class Latch:
    def __init__(self):
        self.step: int | None = None
        self.reps: int | None = None
        self.count = 0

    def get(self, step: int) -> int:
        if self.step is None or self.reps and self.count >= self.reps:
            self.step = step
            self.count = 0
        self.count += 1
        return self.step

    def cancel(self):
        self.step = None
        self.count = 0
