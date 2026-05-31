xrun: deploy-native
	cd src && mpr xrun -f main.py

mountsd:
	mpr run mountsd.py

list-samples:
	mpremote exec "import os, machine" exec "os.mount(machine.SDCard(), '/sd')" ls /sd/samples | sed -nr "s/.* (\w+.wav)/\1/p"

copy-samples:
	mpr run copy_samples.py

.PHONY: sync-samples
sync-samples:
	@bash -euo pipefail -c '\
		set -a; [ -f .env ] && source .env; set +a; \
		if [ -z "$$LOCAL_BREAK_SAMPLE_DIRECTORY" ]; then \
			echo "LOCAL_BREAK_SAMPLE_DIRECTORY is not set; add it to .env (see .env.example)" >&2; \
			exit 1; \
		fi; \
		if [ ! -d "$$LOCAL_BREAK_SAMPLE_DIRECTORY" ]; then \
			echo "directory does not exist: $$LOCAL_BREAK_SAMPLE_DIRECTORY" >&2; \
			exit 1; \
		fi; \
		exec python scripts/manage_samples.py -l "$$LOCAL_BREAK_SAMPLE_DIRECTORY" \
	'

.PHONY: convert-to-mono
convert-to-mono:
	@bash -euo pipefail -c '\
		set -a; [ -f .env ] && source .env; set +a; \
		dir="$$LOCAL_BREAK_SAMPLE_DIRECTORY"; \
		if [ -z "$$dir" ]; then \
			echo "LOCAL_BREAK_SAMPLE_DIRECTORY is not set; add it to .env (see .env.example)" >&2; \
			exit 1; \
		fi; \
		if [ ! -d "$$dir" ]; then \
			echo "directory does not exist: $$dir" >&2; \
			exit 1; \
		fi; \
		command -v ffmpeg >/dev/null || { echo "ffmpeg not found in PATH" >&2; exit 1; }; \
		command -v ffprobe >/dev/null || { echo "ffprobe not found in PATH" >&2; exit 1; }; \
		converted=0; skipped=0; \
		while IFS= read -r -d "" f; do \
			ch=$$(ffprobe -v error -select_streams a:0 -show_entries stream=channels -of csv=p=0 "$$f"); \
			if [ "$$ch" -le 1 ] 2>/dev/null; then \
				echo "skip (already mono): $$(basename "$$f")"; \
				skipped=$$((skipped + 1)); \
				continue; \
			fi; \
			out="$$dir/$$(basename "$${f%.*}").wav"; \
			echo "converting $$ch ch -> mono: $$(basename "$$f")"; \
			ffmpeg_args=(-hide_banner -loglevel error -y -i "$$f" \
				-af "pan=mono|c0=0.5*c0+0.5*c1" -ac 1 -ar 44100 -acodec pcm_s16le); \
			if [ "$$f" = "$$out" ]; then \
				tmp=$$(mktemp "$$dir/.convert-to-mono.XXXXXX.wav"); \
				ffmpeg "$${ffmpeg_args[@]}" "$$tmp"; \
				mv "$$tmp" "$$out"; \
			else \
				ffmpeg "$${ffmpeg_args[@]}" "$$out"; \
				rm -f "$$f"; \
			fi; \
			converted=$$((converted + 1)); \
		done < <(find "$$dir" -maxdepth 1 -type f \( \
			-iname "*.wav" -o -iname "*.mp3" -o -iname "*.aiff" -o \
			-iname "*.aif" -o -iname "*.flac" -o -iname "*.m4a" -o \
			-iname "*.aac" -o -iname "*.ogg" \
		\) -print0); \
		echo "done ($$converted converted, $$skipped already mono)"; \
	'

build-native:
	cd native/native_wav && make

deploy-native: build-native
	mpr put native/native_wav/native_wav.mpy lib

deploy-micropython-firmware:
	teensy_loader_cli --mcu=TEENSY41 -v -w TEENSY41-20241129-v1.24.1.hex

deploy-custom-micropython-firmware:
	teensy_loader_cli --mcu=imxrt1062 -v -w firmware.hex

#setup-teensy:
#	mpr touch /flash/SKIPSD && mpr mkdir lib && mpr mkdir lib/adafruit_midi && \
#	mpr put src/lib/typing.mpy lib && mpr put native/native_wav/native_wav.mpy lib && mpr put src/main.py /flash/ && \
#	mpr mip install usb-device-midi
setup-teensy:
	# mpr touch /flash/SKIPSD && mpr mkdir lib && mpr mkdir lib/adafruit_midi && \
	mpr put src/lib/typing.mpy lib && mpr put native/native_wav/native_wav.mpy lib && mpr put src/main.py /flash/ && \
	mpr mip install usb-device-midi
