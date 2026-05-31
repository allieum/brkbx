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
import argparse
import hashlib
import os
import subprocess
import sys

DEFAULT_REMOTE_SAMPLE_DIR = "/flash/samples"

MOUNT_CMD = [
    "mpremote",
    "exec",
    "import os, machine",
    "exec",
    "os.mount(machine.SDCard(), '/sd')",
]

def run_mpremote(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run([*MOUNT_CMD, *args], check=False, capture_output=True, text=True)
    if check and result.returncode != 0:
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        if result.stdout:
            print(result.stdout, file=sys.stderr)
        result.check_returncode()
    return result


def _device_str(value: str) -> str:
    return repr(value)


def _wav_names_from_stdout(stdout: str) -> set[str]:
    return {
        line.strip()
        for line in stdout.splitlines()
        if line.strip().endswith(".wav") and not line.strip().startswith(".upload_")
    }


def ensure_remote_dir(remote_dir: str) -> None:
    parts = remote_dir.strip("/").split("/")
    lines = ["import os"]
    for i in range(len(parts)):
        path = "/" + "/".join(parts[: i + 1])
        lines.append(f"try:\n    os.mkdir({_device_str(path)})\nexcept OSError:\n    pass")
    run_mpremote("exec", "\n".join(lines))


def list_remote(remote_dir: str) -> set[str]:
    script = (
        "import os\n"
        f"remote = {_device_str(remote_dir)}\n"
        "try:\n"
        "    names = [n for n in os.listdir(remote) if n.endswith('.wav') and not n.startswith('.upload_')]\n"
        "except OSError:\n"
        "    names = []\n"
        "print('\\n'.join(names))"
    )
    result = run_mpremote("exec", script)
    return _wav_names_from_stdout(result.stdout)


def list_local(local_dir: str) -> set[str]:
    return {
        name
        for name in os.listdir(local_dir)
        if name.endswith(".wav") and os.path.isfile(os.path.join(local_dir, name))
    }


def delete_sample(remote_dir: str, filename: str) -> None:
    path = f"{remote_dir}/{filename}"
    script = (
        "import os\n"
        f"path = {_device_str(path)}\n"
        "try:\n"
        "    os.remove(path)\n"
        "except OSError:\n"
        "    pass\n"
    )
    run_mpremote("exec", script)


def _upload_temp_name(filename: str) -> str:
    digest = hashlib.sha256(filename.encode()).hexdigest()[:12]
    return f".upload_{digest}.wav"


def put_sample(local_dir: str, remote_dir: str, filename: str) -> None:
    local_path = os.path.join(local_dir, filename)
    remote_path = f"{remote_dir}/{filename}"
    temp_name = _upload_temp_name(filename)
    temp_remote = f"{remote_dir}/{temp_name}"

    # mpremote cp embeds the remote path in single-quoted Python on the device;
    # apostrophes in the destination path break unless we upload via a safe name.
    if "'" in filename:
        run_mpremote("cp", local_path, f":{temp_remote}")
        script = (
            "import os\n"
            f"os.rename({_device_str(temp_remote)}, {_device_str(remote_path)})\n"
        )
        run_mpremote("exec", script)
    else:
        run_mpremote("cp", local_path, f":{remote_path}")


def sync(local_dir: str, remote_dir: str, *, dry_run: bool = False) -> None:
    if not os.path.isdir(local_dir):
        sys.exit(f"local directory does not exist: {local_dir}")

    local = list_local(local_dir)
    remote = list_remote(remote_dir)

    to_delete = sorted(remote - local)
    to_put = sorted(local - remote)

    if dry_run:
        for filename in to_delete:
            print(f"would delete {filename}")
        for filename in to_put:
            print(f"would put {filename}")
        print(f"{len(to_delete)} to delete, {len(to_put)} to put")
        return

    if to_put:
        ensure_remote_dir(remote_dir)

    for filename in to_delete:
        print(f"delete {filename}")
        delete_sample(remote_dir, filename)

    for filename in to_put:
        print(f"put {filename}")
        put_sample(local_dir, remote_dir, filename)

    if to_delete or to_put:
        print(f"synced {len(local)} local samples ({len(to_delete)} deleted, {len(to_put)} uploaded)")
    else:
        print(f"synced {len(local)} local samples (already up to date)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync .wav samples from a local directory to the device (rsync --delete style).",
    )
    parser.add_argument(
        "--local",
        "-l",
        default=os.environ.get("LOCAL_BREAK_SAMPLE_DIRECTORY"),
        help="local directory of .wav files (default: $LOCAL_BREAK_SAMPLE_DIRECTORY)",
    )
    parser.add_argument(
        "--remote",
        "-r",
        default=os.environ.get("REMOTE_SAMPLE_DIR", DEFAULT_REMOTE_SAMPLE_DIR),
        help="remote directory on device (default: $REMOTE_SAMPLE_DIR or %(default)s)",
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="print planned changes without touching the device",
    )
    args = parser.parse_args()
    if not args.local:
        sys.exit(
            "local directory not set; pass --local or set LOCAL_BREAK_SAMPLE_DIRECTORY in .env"
        )
    sync(args.local, args.remote, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
