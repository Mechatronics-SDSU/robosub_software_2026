from trax_fxns import Trax
import serial
import struct
import time

"""
    Created by Ryan Sundermeyer
    https://github.com/rsunderr
    rwork@sundermeyer.com
"""

trax = Trax()
trax.connect()

# # kSetAcqParams
# frameID = "kSetAcqParams" # OR =24
# payload = (False, False, 0.0, 0.001)
# trax.send_packet(frameID, payload)
# # kSetAcqParamsDone
# data = trax.recv_packet()
# print(data[1] == 26)

# # kSetDataComponents
# frameID = "kSetDataComponents" # OR =3
# payload = (4, 0x5, 0x18, 0x19, 0x4f)
# trax.send_packet(frameID, payload)

# kStopContinuousMode
# frameID = "kStopContinuousMode" # OR =22
# trax.send_packet(frameID)

# kSetDataComponents
frameID = 1
trax.send_packet(frameID)

frameID = 2  
packet = trax.send_packet(frameID)
data = trax.recv_packet(frameID)
print(data)
print(type(data))

# frameID = 3
# payload = (4, 0x5, 0x18, 0x19, 0x4f) # 4 comps
# trax.send_packet(frameID, payload)

# frameID = 4
# trax.send_packet(frameID)

# fremID = 5
# data = trax.recv_packet(payload)
# trax.send_packet(frameID)


# # kStartContinuousMode
# frameID = "kStartContinuousMode" # OR =21
# trax.send_packet(frameID)

# # try:
# #     while True:
# #         data = trax.recv_packet(payload)
# #         print(data)
# #         print(type(data))
# #     # if data[4] < 90 or data[4] > 270: break # exit if aiming to left
# # except KeyboardInterrupt:
# #     print("Closing...")
# #     pass


# # kStopContinuousMode
# frameID = "kStopContinuousMode" # OR =22
# trax.send_packet(frameID)

trax.close()