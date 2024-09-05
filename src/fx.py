# let's do timestretch and pitch mod next :)


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
