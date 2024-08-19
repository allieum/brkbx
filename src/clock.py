import utility
from time import ticks_us, ticks_diff

logger = utility.get_logger(__name__, "DEBUG")


class MidiClock:
    def __init__(self):
       self.clock_count = 0
       self.song_position = 0
       self.play_mode = False
       self.last_clock_ticks = 0

    def start(self):
        """ proceess midi start message """
        logger.info("received midi start")
        self.play_mode = True
        self.clock_count = -1
        self.song_position = -1

    def stop(self):
        """ proceess midi stop message """
        logger.info("received midi stop")
        self.play_mode = False

    def process_clock(self) -> int | None:
        """ process midi timing clock message """
        self.clock_count += 1
        ticks = ticks_us()
        secs_per_tick = ticks_diff(ticks, self.last_clock_ticks) / 1000000
        secs_per_beat = secs_per_tick * 24
        bpm = round(60 / secs_per_beat)
        # logger.debug(f"bpm is {bpm}")
        self.last_clock_ticks = ticks
        if self.play_mode and self.clock_count % 6 == 0:
            self.song_position += 1
            logger.debug(f"song position {self.song_position}")
            return self.song_position
        return None
