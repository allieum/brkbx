import utility
from collections import deque
from time import ticks_add, ticks_us, ticks_diff
import midi

logger = utility.get_logger(__name__, "DEBUG")

class InternalClock:
    RESET_START_INTERVAL = 1024

    def __init__(self):
        self.song_position = 0
        self.play_mode = False
        self.bpm = 136
        self.start_ticks = None
        self.step_count = 0
        self.bpm_changed = lambda _: ()
        self.clock_count = 0

    def set_song_position(self, spp):
        self.song_position = 2 * spp - 1

    def start(self):
        if midi_clock.play_mode:
            logger.error(f"can't start internal clock when midi clock is running")
        logger.info("starting internal clock")
        self.song_position = -1
        self.prev_ticks = None
        self.start_ticks = ticks_us()
        self.step_count = 0
        self.play_mode = True
        self.clock_count = 0
        # self.prev_ticks = ticks_us()

    def midi_continue(self):
        """ proceess midi start message """
        logger.info("received midi start")
        self.play_mode = True
        self.step_count = -1

    def stop(self):
        """ proceess midi stop message """
        if not self.play_mode:
            return
        logger.info("stopping internal clock")
        self.play_mode = False

    def toggle(self, *_):
        if self.play_mode:
            self.stop()
        else:
            self.start()

    def predict_next_step_ticks(self):
        ticks_per_beat = 60 / self.bpm * 1000000
        ticks_per_step = round(ticks_per_beat / 8)
        # logger.info(f"{self.last_step_ticks + ticks_per_step}")
        result = ticks_add(self.start_ticks, ticks_per_step * self.step_count)
        # logger.info(f"next step predicted for {result}")
        return result

    # For generating midi TimingClock, 24ppq
    def predict_next_clock_ticks(self):
        ticks_per_beat = 60 / self.bpm * 1000000
        ticks_per_clock = round(ticks_per_beat / 24)
        # logger.info(f"{self.last_step_ticks + ticks_per_step}")
        result = ticks_add(self.start_ticks, ticks_per_clock * self.clock_count)
        # logger.info(f"next step predicted for {result}")
        return result


    def process_clock(self, ticks) -> int | None:
        """ update internal clock state
        :returns which 32nd note step clock has landed on, if any
        """
        if self.play_mode and ticks >= self.predict_next_clock_ticks():
            self.clock_count += 1
            # midi.midi.send(midi.TimingClock())
        if ticks < self.predict_next_step_ticks() or not self.play_mode:
            return None
        if (diff := ticks_diff(ticks, self.predict_next_step_ticks()) / 1000000) > 0.005:
            logger.error(f"step was {diff} late")
        if self.step_count >= self.RESET_START_INTERVAL:
            self.step_count = 0
            # normalize ticks to bpm to preserve start time , prevent drift?
            self.start_ticks = ticks
        self.song_position += 1
        self.step_count += 1
        return self.song_position


    # todo update_bpm method which resets start_ticks and step_count, on next step (?)
    # def update_bpm(self, bpm):
    #     self.bpm = bpm

class MidiClock:
    BPM_INTERVAL = 48
    ACTIVE_MS = 1000

    def __init__(self):
        self.clock_count = 0
        self.song_position = 0
        self.play_mode = False
        self.last_clock_ticks = 0
        self.last_step_ticks = 0
        self.bpm = 143
        self.prev_bpm = self.bpm
        self.clock_buffer = deque([0], 24)
        self.prev_ticks = None
        self.start_ticks = None
        self.bpm_changed = lambda _: ()

    def start(self):
        if internal_clock.play_mode:
            internal_clock.stop()
        self.song_position = -1
        self.midi_continue()
        self.last_clock_ticks = 0
        self.last_step_ticks = 0
        self.prev_ticks = None
        self.start_ticks = None
        # self.prev_ticks = ticks_us()

    def midi_continue(self):
        """ proceess midi start message """
        logger.info("received midi start")
        self.play_mode = True
        self.clock_count = -1

    def set_song_position(self, spp):
        self.song_position = 2 * spp - 1

    def stop(self):
        """ proceess midi stop message """
        logger.info("received midi stop")
        self.play_mode = False

    def update_bpm(self, ticks) -> int:
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

    def predict_next_step_ticks(self):
        ticks_per_beat = 60 / self.bpm * 1000000
        ticks_per_step = round(ticks_per_beat / 8)
        # logger.info(f"{self.last_step_ticks + ticks_per_step}")
        return ticks_add(self.last_step_ticks, ticks_per_step)

    def is_active(self):
        return ticks_diff(ticks_us(), self.last_clock_ticks) <= self.ACTIVE_MS * 1000

    # add logging to measure drift for playing steps
    def process_clock(self, ticks) -> int | None:
        """ process midi timing clock message
        :returns which 32nd note step clock message lands on, if any
        """
        # TODO some kinda proper bpm smoothing. unfuck below
        self.clock_count += 1
        # secs_per_tick = ticks_diff(ticks, self.last_clock_ticks) / 1000000
        # if secs_per_tick > 0.025 or secs_per_tick < 0.015:
        #     logger.warning(f"weird time since last TC: {secs_per_tick}")

        # avg_secs_per_tick = sum(self.clock_buffer) / len(self.clock_buffer)
        # secs_per_beat = avg_secs_per_tick * 24
            # logger.debug(f"bpm changed to {bpm} {list(self.clock_buffer)}")
        # if bpm != 0:
        #     self.bpm = bpm
        # logger.info(f"secs per clock: {secs_per_tick}")
        self.last_clock_ticks = ticks
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
            self.last_step_ticks = ticks
            # logger.info(f"predicted {predicted_ticks}, actual {actual_ticks}")
            lag = ticks_diff(predicted_ticks, actual_ticks) / 1000000
            if lag < 0:
                pass
                # logger.info(f"lag is {ticks_diff(predicted_ticks, actual_ticks) / 1000000}")
        if self.clock_count % self.BPM_INTERVAL == 0:
            bpm = self.update_bpm(ticks)
            if bpm != self.bpm and bpm == self.prev_bpm and bpm >= 40 and bpm < 300:
                self.bpm = bpm
                logger.debug(f"bpm changed to {bpm}")
                self.bpm_changed(bpm)
            self.prev_bpm = bpm
        elif self.clock_count < self.BPM_INTERVAL:
            bpm = self.estimate_bpm(ticks)
            if bpm != self.bpm and bpm == self.prev_bpm and bpm >= 40 and bpm < 300:
                self.bpm = bpm
                logger.debug(f"bpm estimated as {bpm}")
                self.bpm_changed(bpm)
            self.prev_bpm = bpm
        return new_position

internal_clock = InternalClock()
midi_clock = MidiClock()

def get_running_clock():
    clock = midi_clock if midi_clock.play_mode else internal_clock if internal_clock.play_mode else None
    return clock

def clock_running():
    return get_running_clock() is not None

def get_current_step():
    return 0 if (clock := get_running_clock()) is None else clock.song_position

def toggle_clock(*_):
    clock = get_running_clock()
    logger.info(f"toggling clock {clock} to stop")
    if clock:
        clock.stop()
    else:
        midi_clock.start() if midi_clock.is_active() else internal_clock.start()
