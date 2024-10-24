# SPDX-FileCopyrightText: 2019 Kevin J. Walters for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
`adafruit_midi.note_on`
================================================================================

Note On Change MIDI message.


* Author(s): Kevin J. Walters

Implementation Notes
--------------------

"""

from .midi_message import MIDIMessage

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_MIDI.git"


class SPP(MIDIMessage):
    """ song position pointer  """

    _message_slots = ["position"]

    _STATUS = 0xF2
    _STATUSMASK = 0xFF
    LENGTH = 3

    def __init__(self, position, *, channel=None):
        super().__init__(channel=channel)
        self.position = position

    def __bytes__(self):
        return bytes(
            [
                self._STATUS | (self.channel & self.CHANNELMASK),
                self.position & 0x7F,
                (self.position >> 7) & 0x7F,
            ]
        )

    @classmethod
    def from_bytes(cls, msg_bytes):
        return cls(
            msg_bytes[2] << 7 | msg_bytes[1], channel=msg_bytes[0] & cls.CHANNELMASK
        )



SPP.register_message_type()
