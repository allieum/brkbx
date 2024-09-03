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
from adafruit_midi import MIDI
from adafruit_midi.timing_clock import TimingClock
from adafruit_midi.start import Start
from adafruit_midi.stop import Stop

import os
from machine import I2C
from machine import I2S
from machine import Pin
from machine import SDCard
from machine import UART
from sgtl5000 import CODEC

from clock import MidiClock
from control import joystick, rotary, rotary_pressed
from fx import Gate, Latch
from sample import Sample, load_samples
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
FORMAT = I2S.STEREO
SAMPLE_RATE_IN_HZ = 44100
# ======= AUDIO CONFIGURATION =======

# MIDI config
RX_PIN = 28
TX_PIN = 29

# https://docs.micropython.org/en/latest/mimxrt/pinout.html#mimxrt-uart-pinout
# UART7 is pins 28, 29
uart = UART(7)
uart.init(31250, timeout=1, timeout_char=1)

# TODO: can't handle multibyte messages, increasing buffer size delays receipt of TimingClock so keep it fixed for now
midi = MIDI(midi_in=uart, midi_out=uart, in_buf_size=1)

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
wav = open("/sd/{}".format(WAV_FILE), "rb")
# TODO: 44 is not safe assumption, could parse file, see https://stackoverflow.com/questions/19991405/how-can-i-detect-whether-a-wav-file-has-a-44-or-46-byte-header
_ = wav.seek(44)  # advance to first byte of Data section in WAV file

# allocate sample array
# memoryview used to reduce heap allocation
wav_samples = bytearray(1000)
wav_samples_mv = memoryview(wav_samples)

# continuously read audio samples from the WAV file
# and write them to an I2S DAC
logger.info("==========  START PLAYBACK ==========")
started = False

silence = bytearray(0 for _ in range(4))
# def i2s_irq(i2s):
#     logger.warning("irq triggered")
# audio_out.irq(i2s_irq)
# audio_out.write(zeros)
midi_clock = MidiClock()

# WAV file strategy:
# 1) calculate offsets into file for each beat
# 2) trigger those on the proper midi step
# 3) figure out time stretching or w/e
gate = Gate()
latch = Latch()
rotary_position = rotary.value()
current_sample = samples[rotary_position % len(samples)]
try:
    while True:
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
        if uart.any():
            msg = midi.receive()
            if msg is not None:
                if isinstance(msg, Start):
                    midi_clock.start()
                    started = True
                    _ = wav.seek(44)
                if isinstance(msg, Stop):
                    midi_clock.stop()
                    started = False
                if isinstance(msg, TimingClock):
                    step = midi_clock.process_clock()
                    if step is not None:
                        x, y = joystick.position()
                        if x > 0.5:
                            step = latch.get(step)
                            if y < -0.5:
                                latch.reps = 4
                            elif y > 0.5:
                                latch.reps = 2
                            else:
                                latch.reps = None
                        else:
                            latch.cancel()
                        # logger.info(f"getting step {step}"
                        chunk_samples = current_sample.get_chunk(step)
                        # logger.info(f"playing samples for step {step}")
                        rate = midi_clock.bpm / current_sample.bpm
                        # logger.info(f"play rate for step {step} is {rate}")
                        target_samples = round(current_sample.samples_per_chunk / rate)
                        # logger.info(f"start write {step}")
                        # TODO this is probably causing us to miss clocks since it takes ~20ms. think about this.
                        # at 32nd notes this gate is kinda choppy nonsense. could work at meta level.
                        gate.ratio = 1 if x > 0 else 1 + x
                        gate.period = 2 if y < -0.5 else 8 if y > 0.5 else 4
                        on_steps = gate.ratio * gate.period
                        play_step = step % gate.period <= on_steps


                        for i in range(target_samples):
                            j = round(i * rate)
                            # if i / target_samples < gate:
                            if play_step:
                                audio_out.write(chunk_samples[j * 4: j * 4 + 4])
                            else:
                                audio_out.write(silence)
                        # logger.info(f"end write {step}")
                        # ret = audio_out.write(sampmles)
                        # logger.info(f"write returned {ret} for step {step}")
                        logger.info(f"joystick {joystick.position()} {joystick.pressed()}")

except (KeyboardInterrupt, Exception) as e:
    print("caught exception {} {}".format(type(e).__name__, e))

# cleanup
wav.close()
os.umount("/sd")
sd.deinit()
audio_out.deinit()
print("Done")
