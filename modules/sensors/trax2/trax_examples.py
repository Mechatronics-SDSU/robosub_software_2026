from trax_fxns import TRAX
import serial
import struct

"""
    Created by Ryan Sundermeyer
    https://github.com/rsunderr
    rwork@sundermeyer.com
"""

trax = TRAX()
trax.connect()

##### CHECK DEVICE VERSION #####
# kGetModInfo
frameID = "kGetModInfo" # OR =1
trax.send_packet(frameID)

# kGetModInfoResp
data = trax.recv_packet()
typ = TRAX.uint_to_str(data[2])
rev = TRAX.uint_to_str(data[3])
print(str(typ) + " " + str(rev))

##### DATA SNAPSHOT #####
# kSetDataComponents
frameID = "kSetDataComponents" # OR =3
payload = (4, 0x5, 0x18, 0x19, 0x4f)
trax.send_packet(frameID, payload)

# kGetData
frameID = "kGetData" # OR =4
trax.send_packet(frameID)

# kGetDataResp
data = trax.recv_packet(payload)
print(data)

##### POWER OFF TRAX #####
# kPowerDown
frameID = "kPowerDown" # OR =15
trax.send_packet(frameID)
# any message will wake TRAX back up

##### GET SERIAL NUMBER #####
# kSerialNumber
frameID = "kSerialNumber" # OR =52
trax.send_packet(frameID)
# kSerialNumberResp
data = trax.recv_packet()
print(data[2])

##### SET/TEST ACQ PARAMS ##### 
# kSetAcqParams
frameID = "kSetAcqParams" # OR =24
payload = (False, False, 0.0, 0.001)
trax.send_packet(frameID, payload)
# kSetAcqParamsDone
data = trax.recv_packet()
print(data[1] == 26)

# kGetAcqParams
frameID = "kGetAcqParams" # OR =25
trax.send_packet(frameID)

# kGetAcqParamsResp
data = trax.recv_packet()
print(data)


trax.close()