#!/usr/bin/env python3
import subprocess

REMOTE_SAMPLE_DIR = '/sd/samples'
# LOCAL_SAMPLE_DIR = 'tmp/22050'
LOCAL_SAMPLE_DIR = 'Downloads'
MOUNT_CMD = [
    'mpremote',
    'exec',
    'import os, machine',
    'exec',
    "os.mount(machine.SDCard(), '/sd')",
]
LS_CMD = [
    'ls',
    REMOTE_SAMPLE_DIR
]

SED_CMD = [
    "sed",
    "-nr",
    r"s/.* (.+.wav)/\1/p",
]

def list_samples() -> list[str]:
    ps = subprocess.Popen(MOUNT_CMD + LS_CMD, stdout=subprocess.PIPE)
    sed = subprocess.run(SED_CMD, stdin=ps.stdout, capture_output=True, text=True)
    return sed.stdout.splitlines()

def get_sample(filename):
    res = subprocess.run([*MOUNT_CMD, "cp", f":{REMOTE_SAMPLE_DIR}/{filename}", f"{LOCAL_SAMPLE_DIR}/{filename}"])

def put_sample(filename):
    subprocess.run([*MOUNT_CMD, "cp", f"{LOCAL_SAMPLE_DIR}/{filename}", f":{REMOTE_SAMPLE_DIR}/{filename}"])

put_sample('wav_music-16k-16bits-stereo.wav')
# for wav in list_samples():
#     print(wav)
#     put_sample(wav)
