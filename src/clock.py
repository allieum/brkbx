import utility

logger = utility.get_logger(__name__, "DEBUG")


class MidiClock:
    def __init__(self):
       self.clock_count = 0
       self.song_position = 0
       self.play_mode = False

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

    def process_clock(self):
        """ process midi timing clock message """
        self.clock_count += 1
        if self.play_mode and self.clock_count % 6 == 0:
            self.song_position += 1
            logger.debug(f"song position {self.song_position}")
