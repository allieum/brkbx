import asyncio
import os
from machine import Pin
from machine import SDCard
from time import ticks_us, ticks_diff

import audio
from audio import play_step, prepare_step, audio_out
from clock import internal_clock, midi_clock, get_running_clock
from control import rotary1
import control
import ui
from midi import midi_receive, LOOKAHEAD_SEC
import sample
from sample import get_samples
from settings import RotarySetting, RotarySettings
import utility

# ===== mysteriously, keypad module only works when these are defined here =========
Pin("D1", Pin.IN, Pin.PULL_DOWN)
Pin("D2", Pin.IN, Pin.PULL_DOWN)
Pin("D3", Pin.IN, Pin.PULL_DOWN)
Pin("D4", Pin.IN, Pin.PULL_DOWN)

logger = utility.get_logger(__name__, "DEBUG")

sd = SDCard(1)  # Teensy 4.1: sck=45, mosi=43, miso=42, cs=44
os.mount(sd, "/sd")

sample.init()
ui.init()

async def run_internal_clock():
    while True:
        # todo only do this frequently if clock is running
        await asyncio.sleep_ms(1 if internal_clock.play_mode else 5)
        step = internal_clock.process_clock(ticks_us())
        if step is None:
            continue
        await play_step(step, internal_clock.bpm)

started = False
midi_clock.bpm_changed = lambda _: asyncio.create_task(prepare_step(0)) if not midi_clock.play_mode else ()
rotary_settings = RotarySettings(rotary1)


async def main():
    logger.info(f"entered main() len samples {len(get_samples())}")
    audio.started_preparing_next_step = False
    asyncio.create_task(midi_receive())
    asyncio.create_task(run_internal_clock())
    sample.current_sample = rotary1.value() % len(get_samples())
    until_step = None
    control.rotary2.button.down_cb = internal_clock.toggle

    logger.info(f"preparing first step")
    await prepare_step(0)
    logger.info(f"prepared first step")
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
                    sample.current_sample = new_val % len(samples)
                    logger.info(f"switched to sample {sample.get_current_sample().name}")
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
