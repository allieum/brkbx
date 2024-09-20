import utility
from collections import deque
from time import ticks_us, ticks_diff

logger = utility.get_logger(__name__, "DEBUG")


class MidiClock:
    BPM_INTERVAL = 96

    def __init__(self):
        self.clock_count = 0
        self.song_position = 0
        self.play_mode = False
        self.last_clock_ticks = 0
        self.last_step_ticks = 0
        self.bpm = 143
        self.clock_buffer = deque([0], 24)
        self.prev_ticks = None
        self.start_ticks = None

    def start(self):
        """ proceess midi start message """
        logger.info("received midi start")
        self.play_mode = True
        self.clock_count = -1
        self.song_position = -1
        self.last_clock_ticks = 0
        self.last_step_ticks = 0
        self.prev_ticks = None
        self.start_ticks = None
        # self.prev_ticks = ticks_us()

    def stop(self):
        """ proceess midi stop message """
        logger.info("received midi stop")
        self.play_mode = False

    def update_bpm(self, step, ticks) -> int:
        # interval_steps = step % self.BPM_INTERVAL
        bpm = self.bpm
        if self.prev_ticks:
            interval_time = ticks_diff(ticks, self.prev_ticks) / 1000000
            secs_per_tick = interval_time / self.BPM_INTERVAL
            secs_per_beat = secs_per_tick * 24
            # logger.info(f"beat interval {secs_per_beat}")
            bpm = round(60 / secs_per_beat)
        self.prev_ticks = ticks
        return bpm

    def estimate_bpm(self, ticks):
        interval_time = ticks_diff(ticks, self.prev_ticks) / 1000000
        secs_per_tick = interval_time / self.clock_count
        secs_per_beat = secs_per_tick * 24
        # logger.info(f"beat interval {secs_per_beat}")
        bpm = round(60 / secs_per_beat)
        return bpm



    # add logging to measure drift for playing steps
    def process_clock(self, ticks) -> int | None:
        """ process midi timing clock message
        :returns which 32nd note step clock message lands on, if any
        """
        # TODO some kinda proper bpm smoothing. unfuck below
        self.clock_count += 1
        # secs_per_tick = ticks_diff(ticks, self.last_clock_ticks) / 1000000

        # avg_secs_per_tick = sum(self.clock_buffer) / len(self.clock_buffer)
        # secs_per_beat = avg_secs_per_tick * 24
            # logger.debug(f"bpm changed to {bpm} {list(self.clock_buffer)}")
        # if bpm != 0:
        #     self.bpm = bpm
        # logger.info(f"secs per clock: {secs_per_tick}")
        # self.last_clock_ticks = ticks
        if self.start_ticks is None:
            self.start_ticks = ticks
        new_position = None
        if self.play_mode and self.clock_count % 3 == 0:
            self.song_position += 1
            # logger.debug(f"song position {self.song_position} (diff {ticks_diff(ticks, self.last_step_ticks
            # )})")
            # secs_per_tick = ticks_diff(ticks, self.last_step_ticks) / 1000000
            # secs_per_beat = secs_per_tick * 8
            # self.bpm = round(60 / secs_per_beat)
            # bpm = round(60 / secs_per_beat)
            # self.last_step_ticks = ticks
            # # logger.debug(f"bpm is {bpm}")
            # if bpm != 0 and bpm != self.bpm:
            #     self.bpm = bpm
                # logger.debug(f"bpm changed to {bpm}")
            new_position = self.song_position
            predicted_ticks = round(self.clock_count / 24 / self.bpm * 60 * 1000000)
            actual_ticks = ticks_diff(ticks, self.start_ticks)
            # logger.info(f"predicted {predicted_ticks}, actual {actual_ticks}")
            lag = ticks_diff(predicted_ticks, actual_ticks) / 1000000
            if lag < 0:
                pass
                # logger.info(f"lag is {ticks_diff(predicted_ticks, actual_ticks) / 1000000}")
        if self.clock_count % self.BPM_INTERVAL == 0:
            bpm = self.update_bpm(self.song_position, ticks)
            if bpm != 0 and bpm != self.bpm:
                self.bpm = bpm
                logger.debug(f"bpm changed to {bpm}")
        elif self.clock_count < self.BPM_INTERVAL:
            bpm = self.estimate_bpm(ticks)
            if bpm != 0 and bpm != self.bpm:
                self.bpm = bpm
                logger.debug(f"bpm estimated as {bpm}")
        return new_position
