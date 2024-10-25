#!/usr/bin/env python3
import subprocess

LIST_WAV_CMD = [
    'mpremote',
    'exec',
    'import os, machine',
    'exec',
    "os.mount(machine.SDCard(), '/sd')",
    'ls',
    '/sd/samples',
]

SED_CMD = [
    "sed",
    "-nr",
    r"s/.* (\w+.wav)/\1/p",
]

ps = subprocess.Popen(LIST_WAV_CMD, stdout=subprocess.PIPE)
sed = subprocess.run(SED_CMD, stdin=ps.stdout, capture_output=True, text=True)

# print(sed.stdout)
# print(sed.stderr)

for wav_file in sed.stdout.splitlines():
    # copy files from device, push them to device
    print(wav_file)
