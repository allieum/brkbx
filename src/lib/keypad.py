from machine import Pin
from time import sleep

__version__ = '1.0.3'
__author__ = 'Teeraphat Kullanankanjana'

class KeypadException(Exception):
    """
    Exception class for keypad-related errors.
    """
    pass

class Keypad:
    def __init__(self, row_pins, column_pins):
        """
        Initialize the keypad object.

        Args:
            row_pins (list): List of row pins.
            column_pins (list): List of column pins.
            keys (list): 2D list representing the key layout.

        Raises:
            KeypadException: If pins or keys are not properly defined.
        """
        if not all(isinstance(pin, Pin) for pin in row_pins):
            raise KeypadException("Row pins must be instances of Pin.")
        
        if not all(isinstance(pin, Pin) for pin in column_pins):
            raise KeypadException("Column pins must be instances of Pin.")
        
        # if not isinstance(keys, list) or not all(isinstance(row, list) for row in keys):
        #     raise KeypadException("Keys must be a 2D list.")
        nkeys = len(row_pins) * len(column_pins)
        self.row_pins = row_pins
        self.column_pins = column_pins
        self.down_cb = [lambda: ()] * nkeys
        self.up_cb = [lambda: ()] * nkeys

        self.key_state = [0] * nkeys
        # for pin in self.row_pins:
        #     pin.init(Pin.IN, Pin.PULL_DOWN)
        # for pin in self.column_pins:
        #     pin.init(Pin.IN, Pin.PULL_DOWN)

        for pin in self.column_pins:
            pin.init(Pin.OUT)
            pin.value(0)

    def on(self, key: int, down = None, up = None):
        if up:
            self.up_cb[key] = up
        if down:
            self.down_cb[key] = down

    def any_pressed(self, keys):
        for k in keys:
            if self.key_state[k] is 1:
                return True
        return False

    def read_keypad(self):
        """
        Read the keypad and return the pressed key.

        Returns:
            str or None: Pressed key or None if no key is pressed.

        Raises:
            KeypadException: If pins or keys are not properly defined.
        """
        i = 0
        for col_pin in self.column_pins:
            col_pin.value(1)
            row_values = [p.value() for p in self.row_pins]
            for val in row_values:
                prev = self.key_state[i]
                if val != prev:
                    self.key_state[i] = val
                    self.down_cb[i]() if val is 1 else self.up_cb[i]()
                    if val is 1:
                        print(f"pressed key {i}")
                    else:
                        print(f"released key {i}")
                i += 1
            col_pin.value(0)
