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
from machine import I2S
from machine import Pin
from machine import SDCard, PWM
from machine import UART
from sgtl5000 import CODEC
from time import ticks_us, ticks_diff

from clock import InternalClock, MidiClock
from control import joystick, rotary1, log_joystick
import control
import fx
from sample import BYTES_PER_SAMPLE, Sample, load_samples
from sequence import StepParams
from settings import RotarySetting, RotarySettings
import utility

import native_wav

logger = utility.get_logger(__name__)

sd = SDCard(1)  # Teensy 4.1: sck=45, mosi=43, miso=42, cs=44
os.mount(sd, "/sd")

# ===== mysteriously, keypad module only works when these are defined here =========
Pin("D1", Pin.IN, Pin.PULL_DOWN)
Pin("D2", Pin.IN, Pin.PULL_DOWN)
Pin("D3", Pin.IN, Pin.PULL_DOWN)
Pin("D4", Pin.IN, Pin.PULL_DOWN)

# ======= I2S CONFIGURATION =======
SCK_PIN = 'D21'
WS_PIN = 'D20'
SD_PIN = 'D7'
MCK_PIN = 'D23'
I2S_ID = 1
BUFFER_LENGTH_IN_BYTES = 40000
# ======= I2S CONFIGURATION =======
# mclk = PWM(Pin(MCK_PIN), 10000000)

# ======= AUDIO CONFIGURATION =======
WAV_FILE = "think.wav"
WAV_SAMPLE_SIZE_IN_BITS = 16
FORMAT = I2S.MONO
SAMPLE_RATE_IN_HZ = 44100
# ======= AUDIO CONFIGURATION =======

stretch_write = 0
last_input_step = 0
PLAY_WINDOW = 2
async def play_step(step, bpm):
    global started_preparing_next_step, last_input_step, stretch_write
    # put the rest of this in function.
    started_preparing_next_step = False
    # if fx.joystick_mode.has_input(step):
    #     last_input_step = step
    # in_play_window = step - last_input_step < PLAY_WINDOW
    if not fx.joystick_mode.gate.is_on(step):
        stretch_write = 0
        return

    # logger.info(f"writing step {step} to i2s...")
    step_bytes = round(60 / bpm / 8 * SAMPLE_RATE_IN_HZ) * 2
    if fx.joystick_mode.stretch.is_active():
        # logger.info(f"stretch writing {stretch_write}:{stretch_write+step_bytes}, bytes_written={bytes_written}")
        await write_audio(step, stretch_write, stretch_write + step_bytes)
        stretch_write += step_bytes
        if stretch_write + step_bytes > bytes_written:
            stretch_write = 0
    else:
        stretch_write = 0
        # logger.info(f"about to write_audio")
        await write_audio(step, 0, bytes_written)
    # logger.info(f"wrote step {step} to i2s")

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
internal_clock = InternalClock()
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


audio_out = I2S(
    I2S_ID,
    sck=Pin(SCK_PIN),
    ws=Pin(WS_PIN),
    sd=Pin(SD_PIN),
    mck=Pin(MCK_PIN),
    mode=I2S.TX,
    bits=WAV_SAMPLE_SIZE_IN_BITS,
    format=FORMAT,
    rate=SAMPLE_RATE_IN_HZ,
    ibuf=BUFFER_LENGTH_IN_BYTES,
)
def init_audio(i2s):
    i2s.init(
        sck=Pin(SCK_PIN),
        ws=Pin(WS_PIN),
        sd=Pin(SD_PIN),
        mck=Pin(MCK_PIN),
        mode=I2S.TX,
        bits=WAV_SAMPLE_SIZE_IN_BITS,
        format=FORMAT,
        rate=SAMPLE_RATE_IN_HZ,
        ibuf=BUFFER_LENGTH_IN_BYTES,
    )

# configure the SGTL5000 codec
i2c = I2C(0, freq=400000)
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

samples = load_samples("/sd/samples/ESSENTIAL DRUM BREAKS")
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
midi_clock = MidiClock()
midi_clock.bpm_changed = lambda _: asyncio.create_task(prepare_step(0)) if not midi_clock.play_mode else ()

# WAV file strategy:
# 1) calculate offsets into file for each beat
# 2) trigger those on the proper midi step
# 3) figure out time stretching or w/e
# current_sample = samples[rotary1.value() % len(samples)]
current_sample = samples[35 % len(samples)]
rotary_settings = RotarySettings(rotary1)

swriter = asyncio.StreamWriter(audio_out)
audio_out_buffer = bytearray(22124)
audio_out_mv = memoryview(audio_out_buffer)
bytes_written = 0
target_samples = 0

# size = native_wav.write(audio_out_buffer)
# logger.info(f"buffer size from c world: {size}")
# @utility.timed_function
# def write_test():
#     size = native_wav.write(audio_out_buffer)
# write_test()


async def prepare_step(step) -> None:
    global target_samples, bytes_written, step_start_bytes
    ticks = ticks_us()
    # logger.info(f"{ticks_diff(ticks, last_step) / 1000000}")
    last_step = ticks
    # logger.info(f"getting step {step}"
    # logger.info(f"playing samples for step {step}")
    # rate = midi_clock.bpm / current_sample.bpm
    clock = get_running_clock()
    if clock is None:
        logger.error(f"no clock running?")
        bpm = 143
        return
    else:
        bpm = clock.bpm
    # stretch_rate = 1
    stretch_rate = bpm / current_sample.bpm
    pitch_rate = 1
    # pitch_rate = clock.bpm / current_sample.bpm
    params = StepParams(step, pitch_rate, stretch_rate)
    fx.joystick_mode.update(params)
    log_joystick()
    play_step = sample_voice_on or fx.joystick_mode.has_input()
    if params.step is None or not play_step:
        # logger.info(f"step {step} params.step is None")
        return
    chunk_samples = current_sample.get_chunk(params.step)
    stretch_block_length = 0.015 # in seconds
    stretch_block_input_samples = round(SAMPLE_RATE_IN_HZ * stretch_block_length)
    pitched_samples = round(current_sample.samples_per_chunk / params.pitch_rate)
    if stretch_block_input_samples > pitched_samples:
        logger.warning(f"stretch block bigger than sample chunk {stretch_block_input_samples} vs {current_sample.samples_per_chunk}, using smaller")
        stretch_block_input_samples = pitched_samples
    stretch_block_output_samples = round(1 / params.stretch_rate * stretch_block_input_samples)
    # logger.info(f"play rate for step {step} is {rate}")
    effective_rate = params.stretch_rate * params.pitch_rate
    target_samples = round(current_sample.samples_per_chunk / effective_rate)
    # i2s_chunk_size = 256
    # step_samples = round(60 / midi_clock.bpm / 8 * SAMPLE_RATE_IN_HZ)

    # if bytes_written + target_samples * 2 > len(audio_out_buffer):
    #     logger.info(f"rolling over audio out buffer, setting bytes_written = 0")
    #     bytes_written = 0
    # step_start_bytes = bytes_written
    # logger.info(f"step {step} total bytes {target_samples * 2} [{step_start_bytes}: {step_start_bytes + target_samples * 2}]")
    # bytes_written = 0

    # samples_written = 0
    # last_write_index = 0
    # prev_j = -1
    # logger.info(f"starting write step {step}")
    write_begin = time.ticks_us()
    # FADE_SAMPLES = 10
    # prev_length = None
    # prev_write = write_begin
    logger.debug(f"preamble for {step} took {ticks_diff(write_begin, ticks) / 1000000}s")
    # logger.info(f"{step_samples} vs {target_samples}")
    if params.play_step:
        bytes_written = native_wav.write(audio_out_buffer, chunk_samples, stretch_block_input_samples, stretch_block_output_samples, target_samples, pitched_samples, params.pitch_rate)
        logger.debug(f"finished writing {step} res={bytes_written}, took {ticks_diff(ticks_us(), write_begin) / 1000000}s")

async def write_audio(step, start, end):
    swriter.out_buf = audio_out_mv[start: end]
    logger.debug(f"{step} writing audio from {start} to {end}")
    await swriter.drain()
    audio_len = (end - start) / 2 / SAMPLE_RATE_IN_HZ
    logger.debug(f"{step} finished writing {audio_len}s of audio")

def get_running_clock():
    clock = midi_clock if midi_clock.play_mode else internal_clock if internal_clock.play_mode else None
    return clock

def clock_running():
    return get_running_clock() is not None

ephemeral_start = False
sample_voice_on = False
def create_button_down(i):
    def f():
        global ephemeral_start, sample_voice_on, current_sample
        if not clock_running():
            ephemeral_start = True
            internal_clock.start()
        # fx.button_latch.activate(i * 2, quantize=not ephemeral_start)
        current_sample = samples[(rotary1.value() + i) % len(samples)]
        sample_voice_on = True
    return f

def button_up():
    global ephemeral_start, sample_voice_on
    if control.keypad.any_pressed(control.SAMPLE_KEYS):
        return
    if internal_clock.play_mode and ephemeral_start:
        internal_clock.stop()
        ephemeral_start = False
    # fx.button_latch.cancel()
    sample_voice_on = False

for key in control.SAMPLE_KEYS:
    control.keypad.on(key, create_button_down(key), button_up)

control.keypad.on(control.PLAY_KEY, internal_clock.toggle)

async def main():
    global current_sample, started_preparing_next_step, bytes_written
    started_preparing_next_step = False
    asyncio.create_task(midi_receive())
    asyncio.create_task(run_internal_clock())
    current_sample = samples[rotary1.value() % len(samples)]
    prev_step = None
    until_step = None
    control.rotary2.button.down_cb = internal_clock.toggle

    internal_clock.start()
    await prepare_step(0)
    try:
        while True:
            clock = get_running_clock()
            control.print_controls()
            control.keypad.read_keypad()
            # print(f"{control.joystick2.position(), control.joystick2.pressed()}")
            if clock and not started_preparing_next_step and (until_step := ticks_diff(clock.predict_next_step_ticks(), ticks_us()) / 1000000) <= LOOKAHEAD_SEC:
                logger.debug(f"starting to prepare step {clock.song_position + 1} {until_step}s from now")
                started_preparing_next_step = True
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
