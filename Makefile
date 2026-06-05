xrun: deploy-native
	cd src && mpr xrun -f main.py

mountsd:
	mpr run mountsd.py

list-samples:
	mpremote exec "import os, machine" exec "os.mount(machine.SDCard(), '/sd')" ls /sd/samples | sed -nr "s/.* (\w+.wav)/\1/p"

copy-samples:
	mpr run copy_samples.py

.PHONY: sync-samples
sync-samples: convert-to-mono
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
	' && mpr run src/main.py

.PHONY: convert-to-mono
convert-to-mono:
	@./scripts/convert_to_mono.sh

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
