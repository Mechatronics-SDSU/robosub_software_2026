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

# kStopContinuousMode
frameID = "kStopContinuousMode"
trax.send_packet(frameID)

# kSetAcqParams
frameID = "kSetAcqParams" # OR =24
payload = (False, False, 0.0, 0.05)
trax.send_packet(frameID, payload)

# kSetAcqParamsDone
#data = trax.recv_packet()
#print(data)
#print(data[1] == 26)

# kSetDataComponents
frameID = "kSetDataComponents"
payload = (6, 0x15, 0x16, 0x17, 0x5, 0x18, 0x19) # 6 comp's: ax ay az yaw pitch roll
trax.send_packet(frameID, payload)

# kStartContinuousMode
frameID = "kStartContinuousMode" # OR =21
trax.send_packet(frameID)

try:
    while True:
        data = trax.recv_packet(payload)
        print(data)

        #if data[4] < 90 or data[4] > 270: break # exit if aiming to left
except KeyboardInterrupt:
    # kStopContinuousMode (PLEASE REMEMBER TO STOP - CONTINUOUS RUNS ON STARTUP)
    frameID = "kStopContinuousMode" # OR =22
    trax.send_packet(frameID)

    trax.close()