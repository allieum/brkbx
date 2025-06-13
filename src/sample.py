from typing import Tuple, List
import utility
import math
import os

logger = utility.get_logger(__name__)

def find_wav_data(wav_file) -> Tuple[int, int]:
    """ Parses wav file to locate data chunk where the samples are
    :returns (data_offset, data_length)
    """
    file_buf = bytearray(4)
    wav_file.readinto(file_buf)
    descriptor = file_buf.decode("ascii")

    _ = wav_file.readinto(file_buf)
    chunk_size = int.from_bytes(file_buf, "little")
    logger.info(f"descriptor {descriptor}: {chunk_size}")

    wav_file.seek(12)

    while True:
        wav_file.readinto(file_buf)
        descriptor = file_buf.decode("ascii")
        wav_file.readinto(file_buf)
        chunk_size = int.from_bytes(file_buf, "little")
        logger.info(f"descriptor {descriptor}: {chunk_size}")
        if descriptor == "data":
            data_offset = wav_file.tell()
            data_length = chunk_size
            logger.info(f"wav data offset {data_offset}, length {data_length}")
            return data_offset, data_length
        wav_file.seek(chunk_size, 1)

# NOTE: could read the fmt chunk to validate these, for now just assume
CHANNELS = 1
BYTES_PER_SAMPLE = 2
SAMPLE_RATE = 44100
CHUNKS_PER_BEAT = 8
MAX_CHUNK_SIZE = 44100


class Sample:
    BPM_MIN = 90
    BPM_MAX = 180

    wav_samples = bytearray(MAX_CHUNK_SIZE)
    wav_samples_mv = memoryview(wav_samples)

    def __init__(self, wav_filename: str, i):
        logger.info(wav_filename)
        self.wav_file = open(wav_filename, "rb")
        self.wav_offset, self.wav_size = find_wav_data(self.wav_file)
        self.name = wav_filename
        self.i = i

        nsamples = self.wav_size / CHANNELS / BYTES_PER_SAMPLE
        length = nsamples / SAMPLE_RATE

        total_beats = 4
        while True:
            self.bpm = round(total_beats / length * 60, 2)
            if self.bpm in range(Sample.BPM_MIN, Sample.BPM_MAX + 1):
                logger.info(f"calculated bpm assuming {total_beats} is {self.bpm} for {wav_filename}")
                break
            total_beats *= 2

        # can rounding cause trouble here? ie compounding offset, could do it in get_chunk instead
        self.chunks = CHUNKS_PER_BEAT * total_beats
        self.samples_per_chunk = math.ceil(nsamples / self.chunks)
        self.chunk_size = self.samples_per_chunk * BYTES_PER_SAMPLE * CHANNELS
        logger.info(f"{wav_filename} is {length:.3f}s")


        logger.info(f"{nsamples} total samples, {self.chunk_size} bytes per chunk")
        if self.chunk_size > MAX_CHUNK_SIZE:
            logger.error(f"chunk_size {self.chunk_size} for {self.name} is bigger than allocated array")


    def get_chunk(self, i: int) -> memoryview:
        """ read the ith chunk of wav file into memory and return it """
        self.wav_file.seek(self.wav_offset + i % self.chunks * self.chunk_size)
        # logger.info(f"reading offset {offset}")
        self.wav_file.readinto(self.wav_samples_mv)
        # logger.info(f"samples array {self.wav_samples[:64]}")
        return self.wav_samples_mv


def load_samples(folder: str) -> List[Sample]:
    files = sorted(os.listdir(folder))
    return [Sample(f"{folder}/{wav}", i) for i, wav in enumerate(files) if ".wav" in wav]

samples = []
voice_on = False
current_sample = 0
def init():
    global samples
    samples = load_samples("/sd/samples/y2k")
    # samples = load_samples("/sd/samples/ESSENTIAL DRUM BREAKS")
    logger.info(f"loaded {len(samples)} samples")

def get_samples():
    return samples

def get_current_sample():
    return samples[current_sample % len(samples)]

def set_current_sample(i):
    global current_sample
    current_sample = i
    if len(samples) > 0:
        current_sample %= len(samples)
    logger.info(f"set sample to {i}:{samples[current_sample].name}")
