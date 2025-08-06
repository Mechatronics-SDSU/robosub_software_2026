import struct
import logging
import serial
from serial.tools import list_ports

class PING:
    def __init__(self):
        self.ser = None
        self.baud = 115200

    def connect(self):
        ping360 = ""
        ports = list_ports.comports()
        self.ser = serial.Serial()
        for port in ports:
            if port.serial_number == ping360: # connect to a ping360
                try:
                    self.ser = serial.Serial(port.device, self.baud, timeout=1)
                    print("PING360 CONNECTED: ", port.device)
                    return
                except:
                    self.lg.critical("PING360 FOUND, UNABLE TO CONNECT")
                    return
                
    def close(self):
        self.ser.close()