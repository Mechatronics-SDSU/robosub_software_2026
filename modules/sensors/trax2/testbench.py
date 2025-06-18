from trax_fxns import TRAX
import serial
import struct
import time

"""
    Created by Ryan Sundermeyer
    https://github.com/rsunderr
    mechatronics@sundermeyer.com
"""

trax = TRAX()
trax.connect()

# your code here

trax.close()