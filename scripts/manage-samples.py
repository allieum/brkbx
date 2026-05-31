#!/usr/bin/env python3
# runs on computer. uses mpremote to copy samples from computer to sd card
# want:
# - reads from directory on computer
# - deletes any breakbox samples not on computer
# - writes any samples that are not on breakbox
# - sync operation, similar to rsync with delete
# - we want local and remote directory be command line flags
# - have remote default to hard coded directory
# - important part is that we can pass LOCAL_SAMPLE_DIR in 
import subprocess

# REMOTE_SAMPLE_DIR = '/sd/samples'
REMOTE_SAMPLE_DIR = '/flash/samples/160'
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
