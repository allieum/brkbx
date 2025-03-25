import time
from adafruit_midi import MIDI
from adafruit_midi.midi_continue import Continue
from adafruit_midi.spp import SPP
from adafruit_midi.timing_clock import TimingClock
from adafruit_midi.start import Start
from adafruit_midi.stop import Stop

import asyncio
import os
from machine import I2C
from machine import Pin
from machine import SDCard, PWM
from machine import UART
from sgtl5000 import CODEC
from time import ticks_us, ticks_diff

import audio
from audio import play_step, prepare_step, audio_out
from clock import internal_clock, midi_clock, get_running_clock
from control import joystick, rotary1, log_joystick
import control
import fx
import sample
import ui
from sample import BYTES_PER_SAMPLE, Sample, samples
from sequence import StepParams
from settings import RotarySetting, RotarySettings
import utility


logger = utility.get_logger(__name__)

sd = SDCard(1)  # Teensy 4.1: sck=45, mosi=43, miso=42, cs=44
os.mount(sd, "/sd")

ui.init()

# ===== mysteriously, keypad module only works when these are defined here =========
Pin("D1", Pin.IN, Pin.PULL_DOWN)
Pin("D2", Pin.IN, Pin.PULL_DOWN)
Pin("D3", Pin.IN, Pin.PULL_DOWN)
Pin("D4", Pin.IN, Pin.PULL_DOWN)

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
    prev_step = None
    prev_write = None
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
                await play_step(step, midi_clock.bpm)
            elif isinstance(msg, Start):
                midi_clock.start()
                started = True
            elif isinstance(msg, Stop):
                midi_clock.stop()
                started = False
            elif isinstance(msg, Continue):
                midi_clock.midi_continue()
                started = True
                logger.info(f"received continue: {msg}")
            elif isinstance(msg, SPP):
                midi_clock.set_song_position(msg.position)
                logger.info(f"received spp: {msg.position}")
            # else:
            #     logger.info(f"unknown msg: {msg}")
            # await asyncio.sleep(0)
        i += 1
        # await asyncio.sleep_ms(5)
async def run_internal_clock():
    while True:
        # todo only do this frequently if clock is running
        await asyncio.sleep_ms(1 if internal_clock.play_mode else 5)
        step = internal_clock.process_clock(ticks_us())
        if step is None:
            continue
        await play_step(step, internal_clock.bpm)


# https://docs.micropython.org/en/latest/mimxrt/pinout.html#mimxrt-uart-pinout
# UART7 is pins 28, 29

# codec = CODEC(0x0A, i2c)
# # codec = CODEC(0x0A, i2c, sample_rate=22050, mclk_mode=3)
# codec.mute_dac(False)
# codec.dac_volume(0.9, 0.9)
# codec.headphone_select(0)
# codec.mute_headphone(False)
# codec.volume(0.9, 0.9)
# codec.adc_high_pass_filter(enable=False)
# codec.audio_processor(enable=False)
# audio_out = I2S(
#     I2S_ID,
#     sck=Pin(SCK_PIN),
#     ws=Pin(WS_PIN),
#     sd=Pin(SD_PIN),
#     mck=Pin(MCK_PIN),
#     mode=I2S.TX,
#     bits=WAV_SAMPLE_SIZE_IN_BITS,
#     format=FORMAT,
#     # rate=44100,
#     rate=SAMPLE_RATE_IN_HZ,
#     ibuf=BUFFER_LENGTH_IN_BYTES,
# )

# samples = load_samples("/sd/")
# wav = open("/sd/{}".format(WAV_FILE), "rb")
# # TODO: 44 is not safe assumption, could parse file, see https://stackoverflow.com/questions/19991405/how-can-i-detect-whether-a-wav-file-has-a-44-or-46-byte-header
# _ = wav.seek(44)  # advance to first byte of Data section in WAV file

# # allocate sample array
# # memoryview used to reduce heap allocation
# wav_samples = bytearray(1000)
# wav_samples_mv = memoryview(wav_samples)

# continuously read audio samples from the WAV file
# and write them to an I2S DAC
logger.info("==========  START PLAYBACK ==========")
started = False

silence = bytearray(0 for _ in range(2))
# def i2s_irq(i2s):
#     logger.warning("irq triggered")
# audio_out.irq(i2s_irq)
# audio_out.write(zeros)
midi_clock.bpm_changed = lambda _: asyncio.create_task(prepare_step(0)) if not midi_clock.play_mode else ()

# WAV file strategy:
# 1) calculate offsets into file for each beat
# 2) trigger those on the proper midi step
# 3) figure out time stretching or w/e
# current_sample = samples[rotary1.value() % len(samples)]
current_sample = samples[35 % len(samples)]
rotary_settings = RotarySettings(rotary1)


async def main():
    global current_sample, bytes_written
    audio.started_preparing_next_step = False
    asyncio.create_task(midi_receive())
    asyncio.create_task(run_internal_clock())
    current_sample = samples[rotary1.value() % len(samples)]
    prev_step = None
    until_step = None
    control.rotary2.button.down_cb = internal_clock.toggle

    await prepare_step(0)
    try:
        while True:
            clock = get_running_clock()
            control.print_controls()
            control.keypad.read_keypad()
            # print(f"{control.joystick2.position(), control.joystick2.pressed()}")
            if clock and not audio.started_preparing_next_step and (until_step := ticks_diff(clock.predict_next_step_ticks(), ticks_us()) / 1000000) <= LOOKAHEAD_SEC:
                logger.debug(f"starting to prepare step {clock.song_position + 1} {until_step}s from now")
                audio.started_preparing_next_step = True
                await prepare_step(clock.song_position + 1)

            await asyncio.sleep(0.005)
            if (new_val := rotary_settings.update()) is not None:
                if rotary_settings.setting == RotarySetting.BPM:
                    internal_clock.bpm = new_val
                    logger.info(f"internal bpm set to {new_val}")
                elif rotary_settings.setting == RotarySetting.SAMPLE:
                    current_sample = samples[new_val % len(samples)]
                    logger.info(f"switched to sample {current_sample.name}")
            if (delta := control.rotary2.poll()) != 0:
                new_bpm = internal_clock.bpm + delta
                logger.info(f"internal bpm set to {new_bpm}")
                internal_clock.bpm = new_bpm
            if any([b.poll() for b in control.buttons]) and not midi_clock.play_mode and not internal_clock.play_mode:
                internal_clock.start()
    except (KeyboardInterrupt, Exception) as e:
        print("caught exception {} {}".format(type(e).__name__, e))
        os.umount("/sd")
        sd.deinit()
        audio_out.deinit()
        print("Done")

def run():
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, Exception) as e:
        print("caught exception {} {}".format(type(e).__name__, e))
    finally:
        logger.error(f"interrupted")
        # run()

run()
