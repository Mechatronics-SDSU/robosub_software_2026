"""
M16 modem driver from the Waterlinked Website for two-byte transparent-mode handshakes.
"""

from modules.logger.logger import Logger 
from time import sleep, monotonic

import serial


class M16:
    CHANNELS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    LEVELS = [1, 2, 3, 4]

    def __init__(
        self,
        port: str,
        baudrate: int = 9600,
        channel: int = 1,
        level: int = 1,
        diagnostic: bool = False,
        timeout: float = 0.1,
        configure: bool = True,
    ):
        self.logger = Logger()
        self.port = port
        self.baudrate = baudrate
        self.channel = channel
        self.level = level
        self.diagnostic = diagnostic

        self.ser = serial.Serial(port, baudrate=baudrate, timeout=timeout)
        sleep(0.5)
        self.clear_buffers()

        if configure:
            self.logger.info(
                f"Configuring M16: port={port} baudrate={baudrate} channel={channel} level={level} diagnostic={diagnostic}",
            )
            self.set_channel(channel)
            self.set_level(level)
            if diagnostic:
                self.set_diagnostic_mode()
            else:
                self.reset_diagnostic_mode()

            self.clear_buffers()
            self.logger.info(f"M16 setup complete on {port}")

    def clear_buffers(self):
        """Clear stale serial bytes before starting a send/listen phase."""
        try:
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
        except serial.SerialException:
            pass

    def send_data(self, data: str) -> int | None:
        """Send ASCII command/config data."""
        written = self.ser.write(data.encode("ascii"))
        self.ser.flush()
        return written

    def send_bytes(self, data: bytes) -> int | None:
        """Send raw transparent-mode bytes."""
        written = self.ser.write(data)
        self.ser.flush()
        return written

    def set_channel(self, channel: int) -> bool:
        if channel not in self.CHANNELS:
            self.logger.warning(f"Invalid M16 channel {channel}. Use 1 through 12.")
            return False

        channel_char = {10: "a", 11: "b", 12: "c"}.get(channel, str(channel))

        self.send_data("c")
        sleep(1)
        self.send_data("c")
        self.send_data(channel_char)
        sleep(1)

        self.channel = channel
        return True

    def set_level(self, level: int) -> bool:
        if level not in self.LEVELS:
            self.logger.warning(f"Invalid M16 power level {level}. Use 1 through 4.")
            return False

        self.send_data("l")
        sleep(1)
        self.send_data("l")
        self.send_data(str(level))
        sleep(1)

        self.level = level
        return True

    def set_diagnostic_mode(self):
        self.send_data("d")
        sleep(1)
        self.send_data("d")
        sleep(1)
        self.diagnostic = True

    def reset_diagnostic_mode(self):
        """Enter transparent mode."""
        self.send_data("t")
        sleep(1)
        self.send_data("t")
        sleep(1)
        self.diagnostic = False

    def send_two_bytes(self, data: bytes) -> int | None:
        """Send exactly two raw bytes in transparent mode."""
        if not isinstance(data, bytes):
            raise TypeError("send_two_bytes expects bytes")
        if len(data) != 2:
            self.logger.warning(f"send_two_bytes expected 2 bytes, got {len(data)}")
            return 0

        written = self.send_bytes(data)

        # The official driver waits after transparent-mode chunks. Keep that behavior.
        sleep(2)
        return written

    def read_two_bytes(self, timeout: float = 30.0):
        """
        Wait until exactly two bytes are received, or return None on timeout.
        This avoids returning short reads like b'' or one stale byte.
        """
        buffer = b""
        start = monotonic()

        while monotonic() - start < timeout:
            waiting = self.ser.in_waiting
            if waiting > 0:
                needed = 2 - len(buffer)
                buffer += self.ser.read(min(waiting, needed))

                if len(buffer) == 2:
                    return buffer

                if len(buffer) > 2:
                    self.logger.warning(f"Received more than 2 bytes, using first 2: {buffer!r}")
                    return buffer[:2]

            sleep(0.05)

        self.logger.warning(f"Timed out waiting for 2 bytes. Partial buffer: {buffer!r}")
        return None

    def close(self):
        self.ser.close()
