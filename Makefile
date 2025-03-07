xrun:
	cd src && mpr xrun -f main.py

mountsd:
	mpr run mountsd.py

list-samples:
	mpremote exec "import os, machine" exec "os.mount(machine.SDCard(), '/sd')" ls /sd/samples | sed -nr "s/.* (\w+.wav)/\1/p"

build-native:
	cd native/native_wav && make

deploy-native: build-native
	mpr put native/native_wav/native_wav.mpy lib

deploy-micropython-firmware:
	teensy_loader_cli --mcu=imxrt1062 -v -w TEENSY41-20241129-v1.24.1.hex

setup-teensy:
	mpr touch /flash/SKIPSD && mpr mkdir lib && mpr mkdir lib/adafruit_midi && mpr put src/lib/typing.mpy lib && mpr put native/native_wav/native_wav.mpy lib
