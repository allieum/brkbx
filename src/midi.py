from machine import Pin
from machine import UART
from adafruit_midi import MIDI
from adafruit_midi.midi_continue import Continue
from adafruit_midi.spp import SPP
from adafruit_midi.timing_clock import TimingClock
from adafruit_midi.start import Start
from adafruit_midi.stop import Stop
from clock import midi_clock
from time import ticks_us
import asyncio
import audio
import utility

logger = utility.get_logger(__name__)

# MIDI config
midi_rx = Pin("D28", Pin.IN)
# TX_PIN = Pin("D29", Pin.IN)
LOOKAHEAD_SEC = 0.015
async def midi_receive():
    global started_preparing_next_step, step_start_bytes, bytes_written
    logger.info("midi hello")
    uart = UART(7)
    uart.init(31250, timeout=1, timeout_char=1)
    sreader = asyncio.StreamReader(uart)
    started_preparing_next_step = False
    i = 0
    # TODO: can't handle multibyte messages, increasing buffer size delays receipt of TimingClock so keep it fixed for now
    midi = MIDI(midi_in=sreader, midi_out=uart, in_buf_size=3)
    ticks = ticks_us()
    while True:
        msgs = await midi.receive()
        ticks = ticks_us()
        for msg in msgs:
            # logger.info(f"{i} message {msg}")
            if isinstance(msg, TimingClock):
                # logger.info(f"midi hello {msg}")
                step = midi_clock.process_clock(ticks)
                if step is None:
                    continue
                await audio.play_step(step, midi_clock.bpm)
            elif isinstance(msg, Start):
                midi_clock.start()
            elif isinstance(msg, Stop):
                midi_clock.stop()
            elif isinstance(msg, Continue):
                midi_clock.midi_continue()
                logger.info(f"received continue: {msg}")
            elif isinstance(msg, SPP):
                midi_clock.set_song_position(msg.position)
                logger.info(f"received spp: {msg.position}")
        i += 1
