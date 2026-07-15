from modules.logger.logger import Logger

import serial
import struct
import subprocess

"""
    discord: @will.craychee,    @.kech
    github:                     @rsunderr

    Handles the start button input from the central microcontroller
    the button colors are as follows:
    red: power flush
    green: ready to launch
    blue: debug mode (tbd)
"""
    
class StartButtonDriver:
    """
    StartButtonDriver: Connects to and receives data from microcontroller over USB
    """
    def __init__(self, port="/dev/ttyACM0", baud_rate=921600):
        """
        Start button contstructor: Attempts to connect to the specified serial port
        """
        self.srl: serial.Serial = serial.Serial()
        self.port = port
        self.baud_rate = baud_rate
        self.Logger = Logger()
        try:
            # Open ttyACM0 at 921600 baud
            self.srl = serial.Serial(self.port, self.baud_rate, timeout=1)
            self.Logger.info(f"Connected on {self.port}")
            self.Logger.debug(f"Listening on {self.port} at {self.baud_rate} baud...")
            
        except serial.SerialException as e:
            self.Logger.error(f"Failed to connect on {self.port}: {e}")
            pass

    def disconnect(self):
        """
        Disconnects from the serial port if connected.
        """
        if self.srl is not None:
            self.srl.close()
            self.Logger.info("Serial connection closed.")
            
    def loop(self):
        """
        Main loop to read and parse incoming serial data
        """
        byte: bytes = b''
        packet: bytes = b''
        
        while True:
            # Look for the header byte 0xAA
            try: 
                byte = self.srl.read(1)
                
                if byte[0] == 0xAA:
                    # Read the next 10 bytes (rest of the packet)
                    packet = self.srl.read(10)
                
                if len(packet) != 10:
                    continue  # incomplete packet, skip

                # parse fields
                greenPressed = packet[0]
                bluePressed  = packet[1]
                extKillState = packet[2]
                intKillState = packet[3]
                depth_bytes  = packet[4:8]

                # Unpack little-endian float
                depth = struct.unpack('<f', depth_bytes)[0]

                # Optional: check packet terminator
                if packet[8:] != b'\r\n':
                    continue  # bad packet, skip
                
                if (int(greenPressed) == 1):  # if green button pressed, run launch script
                    subprocess.run(["python3", "launch.py"])

                # Print neatly
                self.Logger.debug(f"Green: {greenPressed}, Blue: {bluePressed}, ExtKill: {extKillState}, IntKill: {intKillState}, Depth: {depth:.6f} m")
                
            except serial.SerialException:
                self.Logger.warning("Failed to read from serial port.")
                continue

if __name__ == "__main__":
    driver = StartButtonDriver("/dev/ttyACM0", 921600)
    driver.loop()