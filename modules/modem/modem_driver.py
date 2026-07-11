"""
M16 modem driver, ported from the Waterlinked reference implementation.
Provides methods for configuring the modem, sending/receiving transparent-mode
messages, and requesting/decoding diagnostic reports.
"""

import os
import struct
import json
from time import time, sleep
from typing import Optional, Dict, Any

from modules.logger.logger import Logger
import serial


class M16:
    """
    Library for controlling the M16 modem.

    The modem maintains internal state for:
      - channel (1-12)
      - power level (1-4)
      - mode (diagnostic or transparent)
    """

    CHANNELS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    LEVELS = [1, 2, 3, 4]
    PACKET_LENGTH = 18

    def __init__(
        self,
        port: str,
        baudrate: int = 9600,
        channel: int = 1,
        level: int = 4,
        diagnostic: bool = False,
        timeout: float = 0.5,
    ) -> None:
        """
        Initialize the modem connection and configure channel/level/mode.

        Parameters:
            port (str): Serial port (e.g. "COM3" on Windows or "/dev/ttyUSB0" on Linux).
            baudrate (int): Baud rate (default 9600).
            timeout (float): Timeout for serial reads (default 0.5).
            channel (int): Channel to set (valid values 1 to 12), (default 1).
            level (int): Power level to set (valid values 1 to 4), (default 4).
            diagnostic (bool): If True, set the modem to diagnostic mode; if False, set transparent mode.
        """
        self.logger = Logger()

        if not os.path.exists(port):
            raise ValueError(f"Port {port} does not exist")
        self.ser = serial.Serial(port, baudrate, timeout=timeout)

        self.port = port
        self.baudrate = baudrate
        self.channel = channel
        self.level = level
        self.diagnostic = diagnostic

        self.logger.info(f"Connecting to modem with: channel: {channel}, level: {level}, diagnostic: {diagnostic}")

        self.set_channel(channel)
        self.logger.info(f"Setting channel: {channel}")

        self.set_level(level)
        self.logger.info(f"Setting level: {level}")

        if diagnostic:
            self.set_diagnostic_mode()
        else:
            self.reset_diagnostic_mode()
        self.logger.info(f"Setting diagnostic mode: {diagnostic}")

    def send_data(self, data: str) -> int | None:
        """Send ASCII data to the modem."""
        return self.ser.write(data.encode("ascii"))

    def clear_buffers(self) -> None:
        """
        Actively drain and discard any bytes currently sitting in the serial
        input buffer. The modem can emit a stray status byte after keying up
        to transmit; if that lingers in the buffer it misaligns the next
        2-byte frame read. reset_input_buffer() alone isn't enough since it
        only discards what the driver has already pulled off the wire, not
        bytes still in-flight at the OS level.
        """
        try:
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()

            leftover = b""
            while self.ser.in_waiting > 0:
                leftover += self.ser.read(self.ser.in_waiting)
                sleep(0.05)

            if leftover:
                self.logger.debug(f"Discarded stale bytes before clearing: {leftover!r}")
        except serial.SerialException:
            pass

    def set_channel(self, channel: int) -> bool:
        """Set the modem's communication channel (1 to 12)."""
        if channel not in self.CHANNELS:
            self.logger.warning(f"Channel: {channel} is not a valid channel, needs to be between 1-12")
            return False

        self.send_data("c")
        sleep(1)
        self.send_data("c")
        # For channels 10-12, convert to letters: 10 -> 'a', 11 -> 'b', 12 -> 'c'
        ch_str = {10: "a", 11: "b", 12: "c"}.get(channel, str(channel))
        self.send_data(ch_str)
        self.channel = channel
        sleep(1)
        return True

    def set_level(self, level: int) -> bool:
        """Set the modem's power level (1 to 4)."""
        if level not in self.LEVELS:
            self.logger.warning(f"Level: {level} is not a valid level, needs to be between 1-4")
            return False

        self.send_data("l")
        sleep(1)
        self.send_data("l")
        self.send_data(str(level))
        self.level = level
        sleep(1)
        return True

    def set_diagnostic_mode(self) -> None:
        """Set the modem into diagnostic mode."""
        self.send_data("d")
        sleep(1)
        self.send_data("d")
        self.diagnostic = True
        sleep(1)

    def reset_diagnostic_mode(self) -> None:
        """Reset the modem from diagnostic mode (enter transparent mode)."""
        self.send_data("t")
        sleep(1)
        self.send_data("t")
        self.diagnostic = False
        sleep(1)

    def toggle_mode(self) -> None:
        """Toggle between diagnostic and transparent modes."""
        self.send_data("m")
        sleep(1)
        self.send_data("m")
        if self.diagnostic is not None:
            self.diagnostic = not self.diagnostic
        sleep(1)

    def get_report(self) -> None:
        """Request a diagnostic report from the modem."""
        self.send_data("r")
        sleep(1)
        self.send_data("r")
        sleep(1)

    def request_report(self, filename: Optional[str] = None, overall_timeout: float = 5.0) -> Optional[Dict[str, Any]]:
        """
        Request a diagnostic report, decode it, update member variables from the
        report, and optionally save the report as a JSON file.
        """
        self.get_report()
        packet = self.read_packet()
        self.logger.debug(f"Found a packet of length: {len(str(packet))} -> {str(packet)}")

        if packet is None:
            self.logger.info("No valid packet received.")
            return None

        report = self.decode_packet(packet)
        self.logger.debug(f"Decoded packet: \n{report}")
        if report is None:
            self.logger.info("Failed to decode the packet.")
            return None

        self.update_state_from_report(report)

        if filename is not None:
            with open(filename, "w") as f:
                json.dump(report, f, indent=4, default=self._default_converter)
            self.logger.info(f"Report saved to {filename}")

        return report

    def update_state_from_report(self, report: Dict[str, Any]) -> None:
        """Update internal modem state (channel/level/diagnostic) from a decoded report."""
        self.channel = report.get("CHANNEL", self.channel)
        self.level = 4 - report.get("LEVEL", self.level)
        self.diagnostic = bool(report.get("DIAGNOSTIC_MODE", 0))
        self.logger.debug(f"State updated: channel={self.channel}, level={self.level}, diagnostic={self.diagnostic}")

    def send_two_bytes(self, data: str) -> int | None:
        """Send exactly two characters of data to the modem."""
        if len(data) != 2:
            return 0

        written = self.send_data(data)
        sleep(1)
        return written

    def send_raw_bytes(self, data: bytes) -> int | None:
        """
        Send raw bytes in transparent mode, bypassing ASCII encoding. Used
        for binary-packed frames (see modem_comms.py's frame protocol)
        whose byte values can fall outside the ASCII range.
        """
        if not data:
            self.logger.warning("send_raw_bytes called with empty data")
            return 0

        written = self.ser.write(data)
        self.ser.flush()
        sleep(1)
        return written

    def send_msg(self, msg: str, timeout_per_chunk: float = 5.0) -> int | None:
        """
        Send a longer message in 2-character chunks. In diagnostic mode, waits
        for a TX_COMPLETE report after each chunk; in transparent mode, simply
        waits 2 seconds between chunks.
        """
        sum_sent_char = 0
        if len(msg) % 2 != 0:
            msg = msg + " "

        for i in range(0, len(msg), 2):
            chunk = msg[i : i + 2]
            sent_char = self.send_two_bytes(chunk)
            self.logger.info(f"Sent chunk: '{chunk}'")
            if sent_char is not None:
                sum_sent_char += sent_char

            if self.diagnostic:
                start_time = time()
                while time() - start_time < timeout_per_chunk:
                    packet = self.read_packet()
                    if packet is not None:
                        report = self.decode_packet(packet)
                        if report is not None and report.get("TX_COMPLETE", 0) == 1:
                            self.logger.info(f"Transmission complete for chunk: '{chunk}'")
                            break
                    sleep(0.1)
            else:
                sleep(2)

        return sum_sent_char

    def read_packet(self) -> Optional[bytes]:
        """
        Read data from the serial port and search for a valid diagnostic packet.
        A valid packet starts with '$' (0x24) and ends with '\\n' (0x0A) and is
        exactly PACKET_LENGTH bytes long. If no such packet is found within the
        read window, returns whatever raw bytes were collected instead (or None
        if nothing arrived) -- this is how transparent-mode message bytes get
        through, since they don't follow the diagnostic packet framing.
        """
        buffer = b""
        start_time = time()
        timeout_duration = 2  # seconds to wait for a valid packet

        while time() - start_time < timeout_duration:
            if self.ser.in_waiting:
                data = self.ser.read(self.ser.in_waiting)
                buffer += data
                self.logger.debug(f"Buffer length: {len(buffer)}, buffer: {str(buffer)}")

            if b"$" in buffer and b"\n" in buffer:
                start_index = buffer.rfind(b"$")
                end_index = buffer.rfind(b"\n", start_index)
                packet = buffer[start_index : end_index + 1]
                if len(packet) == self.PACKET_LENGTH:
                    self.logger.debug(f"Returning packet: {str(packet)}")
                    return packet
                elif len(packet) > self.PACKET_LENGTH:
                    self.logger.debug(f"Returning packet: {str(packet)}")
                    return packet[: self.PACKET_LENGTH]
            sleep(0.1)

        if len(buffer) == 0:
            self.logger.debug("Returning None")
            return None
        else:
            self.logger.debug(f"Returning buffer: {str(buffer)}")
            return buffer

    def decode_packet(self, packet: bytes) -> Optional[Dict[str, Any]]:
        """
        Decode an 18-byte diagnostic packet received from the modem.
        Returns None if the packet doesn't match the expected framing/length.
        """
        try:
            packet_str = packet.decode("ISO-8859-1")
        except UnicodeDecodeError:
            return None

        if len(packet_str) != self.PACKET_LENGTH or packet_str[0] != "$" or packet_str[-1] != "\n":
            return None

        data_bytes = packet_str[1:17].encode("ISO-8859-1")
        try:
            decoded = struct.unpack("<HBBBHBBBBBHBB", data_bytes)
        except struct.error:
            return None

        return {
            "TR_BLOCK": decoded[0].to_bytes(2, "little"),
            "BER": decoded[1],
            "SIGNAL_POWER": decoded[2],
            "NOISE_POWER": decoded[3],
            "PACKET_VALID": decoded[4],
            "PACKET_INVALID": decoded[5],
            "GIT_REV": decoded[6].to_bytes(1, "little"),
            "TIME": (decoded[9] << 16) | (decoded[8] << 8) | decoded[7],
            "CHIP_ID": decoded[10],
            "HW_REV": decoded[11] & 0b00000011,
            "CHANNEL": (decoded[11] & 0b00111100) >> 2,
            "TB_VALID": (decoded[11] & 0b01000000) >> 6,
            "TX_COMPLETE": (decoded[11] & 0b10000000) >> 7,
            "DIAGNOSTIC_MODE": decoded[12] & 0b00000001,
            "LEVEL": (decoded[12] & 0b00001100) >> 2,
        }

    def _default_converter(self, obj: Any) -> Optional[str]:
        """Convert a bytes object to a hex string for JSON serialization."""
        if isinstance(obj, bytes):
            return obj.hex()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    def close(self) -> None:
        """Close the serial connection."""
        self.ser.close()
