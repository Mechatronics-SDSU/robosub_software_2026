import os
import serial
import struct
import json
import logging
from time import time, sleep
from typing import Optional, Dict, Any

class M16:
    """
    Library for controlling the M16 modem.
    Provides methods for configuring the modem, sending commands,
    reading diagnostic packets, and decoding them.
    
    The modem maintains internal state for:
      - channel (1-12)
      - power level (1-4)
      - mode (diagnostic or transparent)
    """
    # Valid channels (1 through 12) and levels (1 through 4)
    CHANNELS = [1, 2, 3, 4, 5 ,6, 7, 8, 9, 10, 11, 12]
    LEVELS = [1, 2, 3, 4]
    PACKET_LENGTH = 18

    def __init__(self, port: str, baudrate: int = 9600, channel: int = 1, level: int = 4, diagnostic: bool = False, 
                 timeout: float = 0.5) -> None:
        """
        Initialize the modem connection. If channel, level or diagnostic mode is not spesified they are set to default
        default = channel = 1, Level = 4, diagnostic mode = False
        If an optional parameter is left as None, the modem will retain its current configuration.
        
        Parameters:
            port (str): Serial port (e.g. "COM3" on Windows or "/dev/ttyUSB0" on Linux).
            baudrate (int): Baud rate (default 9600).
            timeout (float): Timeout for serial reads (default 0.5).
            channel (int): Channel to set (valid values 1 to 12), (default 1).
            level (int): Power level to set (valid values 1 to 4), (default 4).
            diagnostic (bool): If True, set the modem to diagnostic mode; if False, set transparent mode, (default 1).
        """
        # Logging
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(filename)s:%(lineno)d=%(levelname)s:%(message)s')

        # Check if the port exists
        if not os.path.exists(port):
            raise ValueError(f"Port {port} does not exist")
        self.ser = serial.Serial(port, baudrate, timeout=timeout)

        # Initialize internal state with defaults.
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
        """
        Send ASCII data to the modem.
        
        Parameters:
            data (str): The data to be sent.

        Returns: 
            int: Number of characters written.
        """
        return self.ser.write(data.encode('ascii'))

    def send_bytes(self, data: bytes) -> int | None:
        """
        Send bytes to the modem.
        
        Parameters:
            data (str): The data to be sent.

        Returns: 
            int: Number of characters written.
        """
        return self.ser.write(data)


    def set_channel(self, channel: int) -> bool:
        """
        Set the modem's communication channel.
        
        Parameters:
            channel (int): The channel number (1 to 12).
        """
        if channel not in self.CHANNELS:
            self.logger.warning(f"Channel: {channel} is not a valid channel, needs to be between 1-12 ")
            return False
        self.send_data('c')
        sleep(1)
        self.send_data('c')
        # For channels 10-12, convert to letters: 10 -> 'a', 11 -> 'b', 12 -> 'c'
        if channel in (10, 11, 12):
            ch_str = {10: 'a', 11: 'b', 12: 'c'}[channel]
        else:
            ch_str = str(channel)
        self.send_data(ch_str)
        self.channel = channel  # Update internal state
        sleep(1)
        return True

    def set_level(self, level: int) -> bool:
        """
        Set the modem's power level.
        
        Parameters:
            level (int): The power level (1 to 4).
        """
        if level not in self.LEVELS:
            self.logger.warning(f"Level: {level} is not a valid level, needs to be between 1-4 ")
            return False
        self.send_data('l')
        sleep(1)
        self.send_data('l')
        self.send_data(str(level))
        self.level = level  # Update internal state
        sleep(1)
        return True

    def set_diagnostic_mode(self) -> None:
        """
        Set the modem in diagnostic mode.
        """
        self.send_data('d')
        sleep(1)
        self.send_data('d')
        self.diagnostic = True  # Update internal state
        sleep(1)

    def reset_diagnostic_mode(self) -> None:
        """
        Reset the modem from diagnostic mode (enter transparent mode).
        """
        self.send_data('t')
        sleep(1)
        self.send_data('t')
        self.diagnostic = False  # Update internal state
        sleep(1)

    def toggle_mode(self) -> None:
        """
        Toggle between diagnostic and transparent modes.
        """
        self.send_data('m')
        sleep(1)
        self.send_data('m')
        # Toggle internal state if already set; if not, we cannot infer reliably.
        if self.diagnostic is not None:
            self.diagnostic = not self.diagnostic
        sleep(1)

    def get_report(self) -> None:
        """
        Request a diagnostic report from the modem.
        """
        self.send_data('r')
        sleep(1)
        self.send_data('r')
        sleep(1)

    def request_report(self, filename: Optional[str] = None, overall_timeout: float = 5.0) -> Dict[str, Any] | None:
        """
        Request a diagnostic report, decode it, update member varaibles from the report,
        and optionally save the report as a JSON file.
        
        This function sends the report request command and then listens for a valid packet
        until overall_timeout seconds have elapsed.
        
        Parameters:
            filename (str, optional): If provided, the report is saved to this file.
            overall_timeout (float): Maximum time (in seconds) to wait for a valid report.
        
        Returns:
            Dict[str, Any]: The decoded report if successful; otherwise, None.
        """
        # Send the report request.
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

        # Update internal state from the report.
        self.update_state_from_report(report)

        # Optionally save the report as JSON.
        if filename is not None:
            with open(filename, "w") as f:
                json.dump(report, f, indent=4, default=self._default_converter)
            self.logger.info(f"Report saved to {filename}")

        return report
    

    def update_state_from_report(self, report: Dict[str, Any]) -> None:
        """
        Update internal state modem configuration

        Parameters:
            report (Dict[str, Any]): Decoded report from the modem containing configuration info. 
        """
        self.channel = report.get("CHANNEL", self.channel)
        self.level = 4 - report.get("LEVEL", self.level)
        self.diagnostic = bool(report.get("DIAGNOSTIC_MODE", 0))
        self.logger.debug(f"State updated: channel={self.channel}, level={self.level}, diagnostic={self.diagnostic}")


    def send_two_bytes(self, data: str | bytes) -> (int | None):
        """
        Send two bytes of data to the modem.
        
        Parameters:
            data (str): A string (at least two characters) representing the data.

        Returns:
            int: Number of characters written-
        """
        if len(data) != 2:
            return 0
        else: 
            bytes = self.send_bytes(data)
            sleep(1)
            return bytes

    def send_msg(self, msg: str, timeout_per_chunk: float = 5.0) -> (int | None):
        """
        Send a longer message (more than 2 bytes) in 2-byte chunks.
        If in diagnostic mode, after sending each chunk, wait for a diagnostic report 
        that indicates the transmission is complete (TX_COMPLETE == 1).
        If in transparent mode, simply wait 2 seconds between chunks.
        
        Parameters:
            msg (str): The message to be sent.
            timeout_per_chunk (float): Maximum time (in seconds) to wait for TX_COMPLETE
                                       after sending each 2-byte chunk (diagnostic mode only).
        
        Returns:

        """
        sum_sent_char = 0
        # Break the message into 2-byte chunks.
        if len(msg) % 2 != 0:
            msg = msg + " "

        for i in range(0, len(msg), 2):
            chunk = msg[i:i+2]
            sent_char = self.send_two_bytes(chunk)
            self.logger.info(f"Sent chunk: '{chunk}'")
            if sent_char is not None:
                sum_sent_char += sent_char
            
            if self.diagnostic:
                # Wait for a report with TX_COMPLETE set to 1.
                start_time = time()
                while time() - start_time < timeout_per_chunk:
                    packet = self.read_packet()
                    if packet is not None:
                        report = self.decode_packet(packet)
                        if report is not None:
                            if report.get("TX_COMPLETE", 0) == 1:
                                self.logger.info(f"Transmission complete for chunk: '{chunk}'")
                                break
                    sleep(0.1)
            else:
                # In transparent mode, simply wait the transmission duration.
                sleep(2)
        return sent_char

    def read_packet(self) -> Optional[bytes]:
        """
        Read data from the serial port and search for a valid diagnostic packet.
        A valid packet starts with '$' (0x24) and ends with '\\n' (0x0A) and is exactly 18 bytes long.
        
        Returns:
            Optional[bytes]: The valid packet if found, otherwise the buffer if it is not empty.
        """
        buffer = b""
        start_time = time()
        timeout_duration = 2  # seconds to wait for a valid packet

        while time() - start_time < timeout_duration:
            if self.ser.in_waiting:
                data = self.ser.read(self.ser.in_waiting)
                buffer += data
                self.logger.debug(f"Buffer length: {len(buffer)}, buffer: {str(buffer)}")

            if b'$' in buffer and b'\n' in buffer:
                start_index = buffer.rfind(b'$')
                end_index = buffer.rfind(b'\n', start_index)
                packet = buffer[start_index:end_index + 1]
                if len(packet) == self.PACKET_LENGTH:
                    self.logger.debug(f"Returning packet: {str(packet)}")
                    return packet
                elif len(packet) > self.PACKET_LENGTH:
                    self.logger.debug(f"Returning packet: {str(packet)}")
                    return packet[:self.PACKET_LENGTH]
            sleep(0.1)

        if len(buffer) == 0:
            self.logger.debug(f"Returning None")
            return None
        else:
            self.logger.debug(f"Returning buffer: {str(buffer)}")
            return buffer

    def decode_packet(self, packet: bytes) -> Optional[Dict[str, Any]]:
        """
        Decode a diagnostic packet received from the modem.
        
        The packet should be 18 bytes long, starting with '$' (0x24) and ending with '\\n' (0x0A).
        The bytes between contain the data in the following format:
            - Byte 0: '$'
            - Bytes 1-16: Data fields (see modem documentation)
            - Byte 17: '\\n'
        
        Returns:
            Optional[Dict[str, Any]]: A dictionary of decoded values if the packet is valid,
            otherwise None.
        """
        try:
            packet_str = packet.decode('ISO-8859-1')
        except UnicodeDecodeError:
            return None

        if len(packet_str) != self.PACKET_LENGTH or packet_str[0] != '$' or packet_str[-1] != '\n':
            return None

        data_bytes = packet_str[1:17].encode('ISO-8859-1')
        try:
            decoded = struct.unpack("<HBBBHBBBBBHBB", data_bytes)
        except struct.error:
            return None

        decoded_dict = {
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
        return decoded_dict

    def _default_converter(self, object: Any) -> Optional[str]:
        """
        Convert bytes object to bytestring.
        """
        if isinstance(object, bytes):
            return object.hex()
        raise TypeError(f"Object of type {type(object)} is not JSON serializable")

    def close(self) -> None:
        """
        Close the serial connection.
        """
        self.ser.close()

# Example usage:
if __name__ == "__main__":
    # Initialize modem on COM4 with diagnostic mode disabled.
    m = M16("COM4", diagnostic=False)
    # m.send_msg("Hello, this is a longer message.")
    # m.request_report("report.json")
    m.set_channel(1)