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
    date_store = ""

    def __init__(self, port: str, baudrate: int = 9600, channel: int = 1, level: int = 1, diagnostic: bool = False, 
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

    def reset_diagnostic_mode(self) -> None:
        """
        Reset the modem from diagnostic mode (enter transparent mode).
        """
        self.send_data('t')
        sleep(1)
        self.send_data('t')
        self.diagnostic = False  # Update internal state
        sleep(1)


    def send_data(self, data: str) -> int | None:
        """
        Send ASCII data to the modem.
        
        Parameters:
            data (str): The data to be sent.

        Returns: 
            int: Number of characters written.
        """
        return self.ser.write(data.encode('ascii'))

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

    def send_two_bytes(self, data: str) -> (int | None):
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
            bytes = self.send_data(data)
            sleep(1)
            print (data)
            return bytes

    def send_msg(self, msg: str) -> (int | None):
        """
        Send a longer message (more than 2 bytes) in 2-byte chunks.
        If in transparent mode, simply wait 2 seconds between chunks.
        
        Parameters:
            msg (str): The message to be sent.

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
            # Checks if message chunk was sent successfully
            if sent_char is not None:
                # Counts the number of characters sent successfully.
                sum_sent_char += sent_char
            # In transparent mode, simply wait the transmission duration.
            sleep(2)
        return sent_char

    def read_packet(self) -> Optional[bytes]:
        """
        Read data from the serial port.
        
        Returns:
            bytes: The buffer if it is not empty.
        """
        # Stores incoming data in buffer until a valid packet is found or timeout occurs.
        buffer = b""
        start_time = time()
        timeout_duration = 2  # seconds to wait for a valid packet

        while time() - start_time < timeout_duration:
            if self.ser.in_waiting:
                data = self.ser.read(self.ser.in_waiting)
                buffer += data
                self.logger.debug(f"Buffer length: {len(buffer)}, buffer: {str(buffer)}")
        if len(buffer) == 0:
            self.logger.debug(f"Returning None")
            return None
        elif b'$' in buffer:
            buffer = buffer.split(b"$")[0]  # Get data before the '$' character
            self.date_store = self.date_store + buffer.decode('ascii')
            self.logger.info(f"Complete message received: {str(self.date_store)}")
            self.date_store = ""
            return buffer
        else:
            self.logger.debug(f"Returning buffer: {str(buffer)}")
            self.date_store = self.date_store + buffer.decode('ascii')
            return buffer

    

    def close(self) -> None:
        """
        Close the serial connection.
        """
        self.ser.close()