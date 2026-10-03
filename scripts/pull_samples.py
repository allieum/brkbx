#!/usr/bin/env python3
# runs on computer. uses mpremote to copy samples from the device to a local directory
import argparse
import os
import subprocess
import sys

DEFAULT_REMOTE_SAMPLE_DIR = "/flash/samples"
DEFAULT_LOCAL_DIR = "samples"


def run_mpremote(*args: str) -> subprocess.CompletedProcess:
    result = subprocess.run(["mpremote", *args], check=False, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr or result.stdout, file=sys.stderr)
        result.check_returncode()
    return result


def list_remote(remote_dir: str) -> list[str]:
    script = (
        "import os\n"
        f"print('\\n'.join(os.listdir({remote_dir!r})))"
    )
    result = run_mpremote("exec", script)
    return sorted(line.strip() for line in result.stdout.splitlines() if line.strip().endswith(".wav"))


def pull(remote_dir: str, local_dir: str) -> None:
    os.makedirs(local_dir, exist_ok=True)
    names = list_remote(remote_dir)
    for name in names:
        print(f"pull {name}")
        run_mpremote("cp", f":{remote_dir}/{name}", os.path.join(local_dir, name))
    print(f"pulled {len(names)} samples from {remote_dir} to {local_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Copy .wav samples from the device to a local directory.")
    parser.add_argument("--remote", "-r", default=DEFAULT_REMOTE_SAMPLE_DIR,
                        help="remote directory on device (default: %(default)s)")
    parser.add_argument("--local", "-l", default=DEFAULT_LOCAL_DIR,
                        help="local destination directory (default: %(default)s)")
    args = parser.parse_args()
    pull(args.remote, args.local)


if __name__ == "__main__":
    main()
