from machine import Pin
from machine import UART
from adafruit_midi import MIDI
from adafruit_midi.midi_continue import Continue
from adafruit_midi.spp import SPP
from adafruit_midi.timing_clock import TimingClock
from adafruit_midi.start import Start
from adafruit_midi.stop import Stop
from adafruit_midi.program_change import ProgramChange
from time import ticks_us
import asyncio
import audio
import utility

logger = utility.get_logger(__name__)

# Respond to midi/stop start, but use internal timing rather than TimingClock messages
USE_INTERNAL_CLOCK = False

# MIDI config
midi_rx = Pin("D28", Pin.IN)
# TX_PIN = Pin("D29", Pin.IN)
LOOKAHEAD_SEC = 0.015
uart = UART(7)
uart.init(31250, timeout=1, timeout_char=1)
sreader = asyncio.StreamReader(uart)
i = 0
# TODO: can't handle multibyte messages, increasing buffer size delays receipt of TimingClock so keep it fixed for now
midi = MIDI(midi_in=sreader, midi_out=uart, in_buf_size=6, out_channel=15)
async def midi_receive():
    from clock import midi_clock, internal_clock
    logger.info("midi hello")
    ticks = ticks_us()
    clock = internal_clock if USE_INTERNAL_CLOCK else midi_clock
    while True:
        msgs = await midi.receive()
        ticks = ticks_us()
        for msg in msgs:
            # logger.info(f"{i} message {msg}")
            if not USE_INTERNAL_CLOCK and isinstance(msg, TimingClock):
                # logger.info(f"midi hello {msg}")
                step = clock.process_clock(ticks)
                # logger.info(f"got TC")
                if step is None:
                    continue
                await audio.play_step(step, clock.bpm)
            elif isinstance(msg, ProgramChange):
                logger.info(f"got progam change")
            elif isinstance(msg, Start):
                clock.start(ticks)
            elif isinstance(msg, Stop):
                clock.stop()
            elif isinstance(msg, Continue):
                clock.midi_continue()
                logger.info(f"received continue: {msg}")
            elif isinstance(msg, SPP):
                clock.set_song_position(msg.position)
                logger.info(f"received spp: {msg.position}")
            # else:
            #     logger.info(f"got unknown message")
