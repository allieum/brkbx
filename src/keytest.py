from machine import Pin
import control

Pin("D1", Pin.IN, Pin.PULL_DOWN)
Pin("D2", Pin.IN, Pin.PULL_DOWN)
Pin("D3", Pin.IN, Pin.PULL_DOWN)
Pin("D4", Pin.IN, Pin.PULL_DOWN)

led = Pin("D12", Pin.OUT)
led.value(1)
while True:
    # print(test.value())
    control.keypad.read_keypad()
