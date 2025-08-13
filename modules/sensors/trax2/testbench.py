from trax_fxns import TRAX
import serial
import struct
import time

"""
    Created by Ryan Sundermeyer
    https://github.com/rsunderr
    rwork@sundermeyer.com
"""

trax = TRAX()
trax.connect()

# kSetDataComponents
frameID = "kSetDataComponents"
payload = (1, 0x5)
trax.send_packet(frameID, payload)

# kGetData
frameID = "kGetData"
trax.send_packet(frameID)

# kGetDataResp
data = trax.recv_packet(payload)
if len(data) == 6:
    print(f"\n{data[4]} degrees")

trax.close()