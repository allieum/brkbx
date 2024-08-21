from typing import Tuple
import utility

logger = utility.get_logger(__name__)

def find_wav_data(wav_file) -> Tuple[int, int]:
    """
    :returns (data_offset, data_length)
    """
    file_buf = bytearray(4)
    wav_file.readinto(file_buf)
    descriptor = file_buf.decode("ascii")

    nread = wav_file.readinto(file_buf)
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
CHANNELS = 2
BYTES_PER_SAMPLE = 2
SAMPLE_RATE = 44100

class Sample:
    def __init__(self, wav_filename: str):
        self.wav_file = open(f"/sd/{wav_filename}", "rb")
        self.wav_offset, self.wav_size = find_wav_data(self.wav_file)

        nsamples = self.wav_size / CHANNELS / BYTES_PER_SAMPLE
        length = nsamples / SAMPLE_RATE
        logger.info(f"{wav_filename} is {length:.3f}s")
