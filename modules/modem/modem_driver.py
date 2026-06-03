import logging
import os
from time import monotonic, sleep

import serial

"""
M16 modem driver for modem communication.
"""

class M16:
    """Driver for the WaterLinked M16 modem."""

    CHANNELS = range(1, 13)
    LEVELS = range(1, 5)

    def __init__(self, port: str, baudrate: int = 9600, channel: int = 1, level: int = 1) -> None:
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(filename)s:%(lineno)d=%(levelname)s:%(message)s",
        )

        if not os.path.exists(port):
            raise ValueError(f"Port {port} does not exist")

        self.ser = serial.Serial(port, baudrate)
        self.channel = channel
        self.level = level

        self.set_channel(channel)
        self.set_level(level)
        self.reset_diagnostic_mode()

    def send_data(self, data: str) -> int | None:
        """Send ASCII command text to the modem."""
        return self.ser.write(data.encode("ascii"))

    def send_bytes(self, data: bytes) -> int | None:
        """Send raw bytes to the modem."""
        return self.ser.write(data)

    def set_channel(self, channel: int) -> bool:
        """Set modem communication channel from 1 to 12."""
        if channel not in self.CHANNELS:
            self.logger.warning("Channel %s is invalid. Use 1 through 12.", channel)
            return False

        channel_text = {10: "a", 11: "b", 12: "c"}.get(channel, str(channel))

        self.send_data("c")
        sleep(1)
        self.send_data("c")
        self.send_data(channel_text)
        sleep(1)

        self.channel = channel
        return True

    def set_level(self, level: int) -> bool:
        """Set modem power level from 1 to 4."""
        if level not in self.LEVELS:
            self.logger.warning("Level %s is invalid. Use 1 through 4.", level)
            return False

        self.send_data("l")
        sleep(1)
        self.send_data("l")
        self.send_data(str(level))
        sleep(1)

        self.level = level
        return True

    def reset_diagnostic_mode(self) -> None:
        """Put the modem into transparent mode."""
        self.send_data("t")
        sleep(1)
        self.send_data("t")
        sleep(1)

    def send_two_bytes(self, data: bytes) -> int | None:
        """Send exactly two raw bytes."""
        if len(data) != 2:
            raise ValueError("data must be exactly 2 bytes")

        bytes_written = self.send_bytes(data)
        sleep(1)
        return bytes_written

    def read_two_bytes(self, timeout: float = 10.0) -> bytes | None:
        """Read exactly two bytes from the modem, or return None on timeout."""
        buffer = bytearray()
        start = monotonic()

        while monotonic() - start < timeout:
            waiting = self.ser.in_waiting
            if waiting:
                buffer.extend(self.ser.read(waiting))

                if len(buffer) >= 2:
                    return bytes(buffer[-2:])

            sleep(0.05)

        return None

    def close(self) -> None:
        """Close the serial connection."""
        self.ser.close()
