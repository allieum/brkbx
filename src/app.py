# The MIT License (MIT)
# Copyright (c) 2022 Mike Teachman
# https://opensource.org/licenses/MIT

# Purpose:  Play a WAV audio file using the Teensy Audio Shield, Rev D
#
# - read audio samples from a WAV file on SD Card
# - write audio samples to a SGTL5000 codec on the Teensy Audio Shield
# - the WAV file will play continuously in a loop until
#   a keyboard interrupt is detected or the board is reset
#
# blocking version
# - the write() method blocks until the entire sample buffer is written to the I2S interface
#
# requires a MicroPython driver for the SGTL5000 codec
import math
import time
from adafruit_midi import MIDI
from adafruit_midi.timing_clock import TimingClock
from adafruit_midi.start import Start
from adafruit_midi.stop import Stop

import asyncio
import os
from machine import I2C
from machine import I2S
from machine import Pin
from machine import SDCard
from machine import UART
from sgtl5000 import CODEC
from time import ticks_us, ticks_diff

from clock import MidiClock
from control import joystick, rotary, rotary_pressed
import fx
from sample import Sample, load_samples
from sequence import StepParams
import utility

logger = utility.get_logger(__name__)

sd = SDCard(1)  # Teensy 4.1: sck=45, mosi=43, miso=42, cs=44
os.mount(sd, "/sd")

# ======= I2S CONFIGURATION =======
SCK_PIN = 'D21'
WS_PIN = 'D20'
SD_PIN = 'D7'
MCK_PIN = 'D23'
I2S_ID = 1
BUFFER_LENGTH_IN_BYTES = 40000
# ======= I2S CONFIGURATION =======

# ======= AUDIO CONFIGURATION =======
WAV_FILE = "think.wav"
WAV_SAMPLE_SIZE_IN_BITS = 16
FORMAT = I2S.MONO
SAMPLE_RATE_IN_HZ = 44100
# ======= AUDIO CONFIGURATION =======

# MIDI config
midi_rx = Pin("D28", Pin.IN)
# TX_PIN = Pin("D29", Pin.IN)

async def midi_receive():
    logger.info("midi hello")
    uart = UART(7)
    uart.init(31250, timeout=1, timeout_char=1)
    sreader = asyncio.StreamReader(uart)
    prev_step = None
    i = 0
    # TODO: can't handle multibyte messages, increasing buffer size delays receipt of TimingClock so keep it fixed for now
    midi = MIDI(midi_in=sreader, midi_out=uart, in_buf_size=3)
    ticks = 0
    while True:
        # data = await sreader.read(3)
        # logger.info(f"after await: {uart.any()}, data length {len(data)}")
        # logger.info(f"midi receive: got {data}")
        # msg = midi.receive(data)
        # logger.info(f"midi hello {msg}")
        # logger.info(f"midi_receive spent {ticks_diff(ticks_us(), ticks) / 1000000}s")
        msgs = await midi.receive()
        # logger.info(f"after await: {uart.any()}")
        ticks = ticks_us()
        # if len(msgs) > 1:
        #     logger.info(f"got {len(msgs)} midi messages")
        for msg in msgs:
            # logger.info(f"{i} message {msg}")
            if isinstance(msg, TimingClock):
                # logger.info(f"midi hello {msg}")
                step = midi_clock.process_clock(ticks)
                if step is not None and not writing_audio:
                    if prev_step and not fx.joystick_mode.has_input():
                        prev_step.cancel()
                    prev_step = asyncio.create_task(play_step(step))
            elif isinstance(msg, Start):
                midi_clock.start()
                started = True
            elif isinstance(msg, Stop):
                midi_clock.stop()
                started = False
            # await asyncio.sleep(0)
        i += 1
        # await asyncio.sleep_ms(5)


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
codec = CODEC(0x0A, i2c)
codec.mute_dac(False)
codec.dac_volume(0.9, 0.9)
codec.headphone_select(0)
codec.mute_headphone(False)
codec.volume(0.9, 0.9)
codec.adc_high_pass_filter(enable=False)
codec.audio_processor(enable=False)

samples = load_samples("/sd/samples")
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

# WAV file strategy:
# 1) calculate offsets into file for each beat
# 2) trigger those on the proper midi step
# 3) figure out time stretching or w/e
rotary_position = rotary.value()
current_sample = samples[rotary_position % len(samples)]

writing_audio = False
swriter = asyncio.StreamWriter(audio_out)
last_step = ticks_us()
audio_out_buffer = bytearray(44100)
audio_out_mv = memoryview(audio_out_buffer)
bytes_written = 0
async def play_step(step):
    global writing_audio, last_step, bytes_written
    if writing_audio:
        return
    ticks = ticks_us()
    # logger.info(f"{ticks_diff(ticks, last_step) / 1000000}")
    last_step = ticks
    # logger.info(f"getting step {step}"
    # logger.info(f"playing samples for step {step}")
    # rate = midi_clock.bpm / current_sample.bpm
    stretch_rate = 1
    # stretch_rate = midi_clock.bpm / current_sample.bpm
    # pitch_rate = 1
    pitch_rate = midi_clock.bpm / current_sample.bpm
    params = StepParams(step, pitch_rate, stretch_rate)
    fx.joystick_mode.update(params)
    if params.step is None:
        return
    chunk_samples = current_sample.get_chunk(params.step)
    stretch_block_length = 0.030 # in seconds
    stretch_block_samples = round(SAMPLE_RATE_IN_HZ * stretch_block_length)
    pitched_samples = round(current_sample.samples_per_chunk / params.pitch_rate)
    if stretch_block_samples > pitched_samples:
        logger.warning(f"stretch block bigger than sample chunk {stretch_block_samples} vs {current_sample.samples_per_chunk}, using smaller")
        stretch_block_samples = pitched_samples
    samples_per_stretch_block = round(1 / params.stretch_rate * stretch_block_samples)
    # logger.info(f"play rate for step {step} is {rate}")
    effective_rate = params.stretch_rate * params.pitch_rate
    target_samples = round(current_sample.samples_per_chunk / effective_rate)

    # logger.info(f"start write {step}")
    # TODO this is probably causing us to miss clocks since it takes ~20ms. think about this.
    # at 32nd notes this gate is kinda choppy nonsense. could work at meta level.

    # writing_audio = True
    i2s_chunk_size = 1024
    # i2s_chunk_size = current_sample.samples_per_chunk * 4
    bytes_written = 0
    # logger.info(f"writing in chunks of length {i2s_chunk_size / 4 / 44100}s")
    # logger.info(f"{step} prewrite")
    # for i in range(target_samples):
    #     j = round(i * rate)
    #     # if i / target_samples < gate:
    #     # if play_step:
    #     #     audio_out.write(chunk_samples[j * 4: j * 4 + 4])
    #     # else:
    #     #     audio_out.write(silence)
    #     audio_data = chunk_samples[j * 4: j * 4 + 4] if play_step else silence
    #     swriter.write(audio_data)
    #     bytes_written += 4
    #     if (bytes_written >= i2s_chunk_size):
    #         # logger.info(f"{step} draining")
    #         await swriter.drain()
    #         bytes_written = 0
    # logger.info(f"{step} postwrite")
    # await swriter.drain()
    #
    #

# NEW ARCHITECTURE:
# one task writes as fast as possible, another prepares steps in advance
# keeping the buffer full

    samples_written = 0
    last_write_index = 0
    prev_j = -1
    # logger.info(f"starting write step {step}")
    write_begin = time.ticks_us()
    FADE_SAMPLES = 10
    prev_length = None
    prev_write = write_begin
    for stretch_block_offset in range(0, pitched_samples, stretch_block_samples):
        # logger.info(f"stretch block offset: {stretch_block_offset}")
        for i in range(samples_per_stretch_block):
            block_i = i % min(stretch_block_samples, pitched_samples - stretch_block_offset)
            j = round((stretch_block_offset + block_i) * params.pitch_rate)
            # fadein_factor = FADE_SAMPLES - block_i
            # fadeout_factor = block_i - (stretch_block_samples - FADE_SAMPLES)
            # gain = 1
            # # next: record to visualize data, might be missing end fade
            # if fadein_factor > 0:
            #     gain = 1 / fadein_factor
            # if fadeout_factor > 0:
            #     gain = 1 / fadeout_factor
            # gain = 1
            # # logger.info(f"j: {j}")
            # # if j != prev_j + 1:
            # #     logger.info(f"j went from {prev_j} to {j}")
            # prev_j = j
            audio_data = chunk_samples[j * 2: j * 2 + 2] if params.play_step else silence
            # if gain != 1:
            #     for k in range(0, len(audio_data), 2):
            #         val = int.from_bytes(audio_data[k:k + 2], "little")
            #         newval = math.floor(val * gain)
            #         sb = bytes([newval &0xff, (newval >> 8) & 0xff])
            #         swriter.write(sb)
            # else:
            #     # swriter.write(audio_data)
            if len(audio_data) < 2:
                logger.warning(f"invalid data {list(audio_data)} j={j} i={i} {len(chunk_samples)} {samples_per_stretch_block} {params.pitch_rate} {stretch_block_offset}")
            for i in range(len(audio_data)):
                audio_out_buffer[bytes_written + i] = audio_data[i]
            bytes_written += 2
            samples_written += 1
            done = samples_written == target_samples
            if (bytes_written - last_write_index >= i2s_chunk_size or done):
                # next: switch to 22050 squeeze out the juiiiiice
                audio_len = (bytes_written - last_write_index) / 2 / 44100
                now = time.ticks_us()
                # logger.info(f"{step} pausing {bytes_written}, preparing {audio_len}s took {ticks_diff(ticks_us(), write_begin) / 1000000}s")
                elapsed = ticks_diff(now, prev_write) / 1000000
                # logger.info(f"{step} prepared {prev_length}s of audio {elapsed}s ago")
                if prev_length and elapsed > prev_length:
                    logger.warning(f"lagging behind audio buffer by {elapsed - prev_length}s")
                prev_length = audio_len
                prev_write = now
                # asyncio.create_task(write_audio(last_write_index, bytes_written))
                swriter.out_buf = audio_out_mv[last_write_index: bytes_written]
                await swriter.drain()
                # await asyncio.sleep(0)
                # logger.info(f"{step} unpausing")
                # swriter.out_buf = audio_out_mv[:bytes_written]
                # # swriter.write(audio_out_mv[:bytes_written])
                # before_drain = ticks_us()
                # await swriter.drain()
                # logger.info(f"paused for {ticks_diff(ticks_us(), before_drain) / 1000000}s")
                # could arrange this so we can be preparing new samples while this is draining? separate task?
                # logger.info(f"{step} drained")
                write_begin = ticks_us()
                last_write_index = bytes_written
                # i2s_chunk_size *= 2
            if done:
                break
    # logger.info(f"{samples_written} vs target {target_samples}")
    writing_audio = False
    # logger.info(f"end write {step}")
    # ret = audio_out.write(sampmles)
    # logger.info(f"write returned {ret} for step {step}")
    # logger.info(f"joystick {joystick.position()} {joystick.pressed()}")
async def write_audio(start, end):
    # swriter.out_buf = audio_out_mv[last_write: bytes_written]
    # logger.info(f"write_audio {start}:{end}")
    swriter.out_buf = audio_out_mv[start:end]
# else:
#     swriter.out_buf = silence
    # last_write = bytes_written
    await swriter.drain()
    # logger.info(f"bytes written {start}:{end}")
# keep last write index, detect when it goes lower and assume 0





async def main():
    global current_sample
    asyncio.create_task(midi_receive())
    rotary_position = rotary.value()
    current_sample = samples[rotary_position % len(samples)]
    try:
        while True:
            # does this need to be wrapped in another async task to be worth while..... ?????
            await asyncio.sleep(0.1)
            # if started:
            #     num_read = wav.readinto(wav_samples_mv)
            #     # end of WAV file?
            #     if num_read == 0:
            #         # end-of-file, advance to first byte of Data section
            #         _ = wav.seek(44)
            #     else:
            #         _ = audio_out.write(wav_samples_mv[:num_read])
            #         # pass
            # else:
            #     audio_out.write(zeros)

            # if uart.any() > 0:
            if rotary_position != rotary.value():
                rotary_position = rotary.value()
                current_sample = samples[rotary_position % len(samples)]
                logger.info(f"rotary postiton {rotary_position} {rotary_pressed()}")
                logger.info(f"switched to sample {current_sample.name}")
            # if uart.any():
            #     msg = midi.receive()
            #     if msg is not None:
            #         if isinstance(msg, Start):
            #             midi_clock.start()
            #             started = True
            #             _ = wav.seek(44)
            #         if isinstance(msg, Stop):
            #             midi_clock.stop()
            #             started = False
            #         if isinstance(msg, TimingClock):
            #             step = midi_clock.process_clock()
            #             if step is not None:
            #                 x, y = joystick.position()
            #                 if x > 0.1:
            #                     length = 4 if x > 0.9 else 2 if x > 0.5 else 1
            #                     step = latch.get(step, length)
            #                     if y < -0.5:
            #                         latch.reps = 4
            #                     elif y > 0.5:
            #                         latch.reps = 2
            #                     else:
            #                         latch.reps = None
            #                 else:
            #                     latch.cancel()
            #                 # logger.info(f"getting step {step}"
            #                 chunk_samples = current_sample.get_chunk(step)
            #                 # logger.info(f"playing samples for step {step}")
            #                 rate = midi_clock.bpm / current_sample.bpm
            #                 # logger.info(f"play rate for step {step} is {rate}")
            #                 target_samples = round(current_sample.samples_per_chunk / rate)
            #                 # logger.info(f"start write {step}")
            #                 # TODO this is probably causing us to miss clocks since it takes ~20ms. think about this.
            #                 # at 32nd notes this gate is kinda choppy nonsense. could work at meta level.
            #                 gate.ratio = 1 if x > 0 else 1 + x
            #                 gate.period = 2 if y < -0.5 else 8 if y > 0.5 else 4
            #                 on_steps = gate.ratio * gate.period
            #                 play_step = step % gate.period <= on_steps

            #                 stretch_rate = 0.5
            #                 stretch_block_length = 0.040 # in seconds
            #                 stretch_block_samples = round(SAMPLE_RATE_IN_HZ * stretch_block_length)
            #                 samples_per_stretch_block = round(1 / stretch_rate * stretch_block_samples)

            #                 for stretch_block_offset in range(0, target_samples, stretch_block_samples):
            #                     for i in range(samples_per_stretch_block):
            #                         j = round(stretch_block_offset + i % stretch_block_samples * rate)
            #                         # if i / target_samples < gate:
            #                         if play_step:
            #                             audio_out.write(chunk_samples[j * 4: j * 4 + 4])
            #                         else:
            #                             audio_out.write(silence)
            #                 # logger.info(f"end write {step}")
            #                 # ret = audio_out.write(sampmles)
            #                 # logger.info(f"write returned {ret} for step {step}")
                #                 logger.info(f"joystick {joystick.position()} {joystick.pressed()}")

    except (KeyboardInterrupt, Exception) as e:
        print("caught exception {} {}".format(type(e).__name__, e))

    # cleanup
# wav.close()
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
