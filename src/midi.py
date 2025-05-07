from machine import Pin
from machine import UART
from adafruit_midi import MIDI
from adafruit_midi.midi_continue import Continue
from adafruit_midi.spp import SPP
from adafruit_midi.timing_clock import TimingClock
from adafruit_midi.start import Start
from adafruit_midi.stop import Stop
from adafruit_midi.program_change import ProgramChange
from clock import midi_clock
from time import ticks_us
import asyncio
import audio
import utility
from usb.device.midi import MIDIInterface
import usb.device

logger = utility.get_logger(__name__)

class USBMidi(MIDIInterface):
    def on_midi_event(self, cin, midi0, midi1, midi2):
        logger.info(f"got usb midi event {cin} {midi0} {midi1} {midi2}")

async def usb_midi_receive():
    # usb_midi = USBMidi()
    # usb.device.get().init(usb_midi, builtin_driver=True)
    # logger.info(f"waiting for usb midi host...")
    # while not usb_midi.is_open():
    #     asyncio.sleep_ms(1000)
    # logger.info(f"start usb midi receive loop")
    # while usb_midi.is_open():
    #     asyncio.sleep_ms(1000)
    logger.info(f"end usb midi receive loop")


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
    midi = MIDI(midi_in=sreader, midi_out=uart, in_buf_size=6, out_channel=15)
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
            elif isinstance(msg, ProgramChange):
                logger.info(f"got progam change")
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
