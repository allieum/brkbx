from machine import I2S
from machine import Pin
import asyncio
import utility
from time import ticks_us, ticks_diff
import control
from control import log_joystick
from sequence import StepParams
import native_wav
import fx
import sample
from clock import get_running_clock, internal_clock
from sample import get_current_sample

logger = utility.get_logger(__name__)

# ======= I2S CONFIGURATION =======
SCK_PIN = 'D21'
WS_PIN = 'D20'
SD_PIN = 'D7'
I2S_ID = 1
BUFFER_LENGTH_IN_BYTES = 40000
# ======= I2S CONFIGURATION =======

# ======= AUDIO CONFIGURATION =======
WAV_SAMPLE_SIZE_IN_BITS = 16
FORMAT = I2S.MONO
SAMPLE_RATE_IN_HZ = 44100
# ======= AUDIO CONFIGURATION =======

audio_out = I2S(
    I2S_ID,
    sck=Pin(SCK_PIN),
    ws=Pin(WS_PIN),
    sd=Pin(SD_PIN),
    mck=None,
    mode=I2S.TX,
    bits=WAV_SAMPLE_SIZE_IN_BITS,
    format=FORMAT,
    rate=SAMPLE_RATE_IN_HZ,
    ibuf=BUFFER_LENGTH_IN_BYTES,
)

swriter = asyncio.StreamWriter(audio_out)
audio_out_buffer = bytearray(22124)
audio_out_mv = memoryview(audio_out_buffer)
bytes_written = 0
target_samples = 0
stretch_write = 0
last_input_step = 0
started_preparing_next_step = False
PLAY_WINDOW = 2
async def play_step(step, bpm):
    global started_preparing_next_step, last_input_step, stretch_write
    started_preparing_next_step = False
    do_play_step = sample.voice_on or fx.joystick_mode.has_input()
    if (len(fx.button_latch.lengths) == 0 and not fx.joystick_mode.gate.is_on(step)) or not do_play_step:
        stretch_write = 0
        return

    step_bytes = round(60 / bpm / 8 * SAMPLE_RATE_IN_HZ) * 2
    if fx.stretch_active():
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


planned_step_time = None
async def prepare_step(step, step_time = None) -> None:
    global target_samples, bytes_written, step_start_bytes, planned_step_time
    clock = get_running_clock()
    if clock is None:
        bpm = internal_clock.bpm
    else:
        bpm = clock.bpm
    # logger.info(f"step {step} planned for {step_time}")
    planned_step_time = step_time
    ticks = ticks_us()
    fx.flip.flip_sample(step)
    current_sample = get_current_sample()
    stretch_rate = bpm / current_sample.bpm
    pitch_rate = 1
    params = StepParams(step, pitch_rate, stretch_rate, current_sample.i)
    fx.joystick_mode.update(params)
    # logger.info(f"prepare step {params.step}")
    log_joystick()
    if params.step is None:
        logger.info(f"skipping step {step} ({params.step})")
        return
    chunk_samples = current_sample.get_chunk(params.step)
    # stretch_block_length = 0.015 # in seconds
    stretch_block_length = control.timestretch_grain_knob.value()
    stretch_block_input_samples = round(SAMPLE_RATE_IN_HZ * stretch_block_length)
    pitched_samples = round(current_sample.samples_per_chunk / params.pitch_rate)
    if params.pitch_rate != 1:
        logger.info(f"pitch rate {params.pitch_rate}")
    if stretch_block_input_samples > pitched_samples:
        logger.warning(f"stretch block bigger than sample chunk {stretch_block_input_samples} vs {current_sample.samples_per_chunk}, using smaller")
        logger.info(f"stretch block: {stretch_block_length}")
        stretch_block_input_samples = pitched_samples
    stretch_block_output_samples = round(1 / params.stretch_rate * stretch_block_input_samples)
    # logger.info(f"play rate for step {step} is {rate}")
    effective_rate = params.stretch_rate * params.pitch_rate
    target_samples = round(current_sample.samples_per_chunk / effective_rate)
    write_begin = ticks_us()
    logger.debug(f"preamble for {step} took {ticks_diff(write_begin, ticks) / 1000000}s")

    if params.play_step:
        volume = 0 if control.volume_knob.value() < 0.02 else control.volume_knob.value()
        bytes_written = native_wav.write(audio_out_buffer,
                                         chunk_samples,
                                         stretch_block_input_samples,
                                         stretch_block_output_samples,
                                         target_samples,
                                         pitched_samples,
                                         params.pitch_rate,
                                         volume,
                                         control.filter_knob.value())
        # logger.info(f"volume : {volume}")
        logger.debug(f"finished writing {step} res={bytes_written}, took {ticks_diff(ticks_us(), write_begin) / 1000000}s")

async def write_audio(step, start, end):
    if planned_step_time and (lag := ticks_diff(ticks_us(), planned_step_time) / 1000000) > 0.005:
        logger.warning(f"step {step} (planned for {planned_step_time}) lag is too high ({lag}), skipping step")
        return
    swriter.out_buf = audio_out_mv[start: end]
    logger.debug(f"{step} writing audio from {start} to {end}")
    await swriter.drain()
    audio_len = (end - start) / 2 / SAMPLE_RATE_IN_HZ
    logger.debug(f"{step} finished writing {audio_len}s of audio")
