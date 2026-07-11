import serial
# import pyserial
import struct
import numpy
try:
    from USB_Transmit import USB_Transmitter
except:
    from modules.motors.USB_Transmit import USB_Transmitter

"""
    discord: @.kech
    github: @rsunderr
    This script is used to reset the motors using USB Transmitter.
"""


baud_rate = 115200
usb_port = None
srl = None

transmitter = USB_Transmitter()
transmitter.reset_motors()