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
