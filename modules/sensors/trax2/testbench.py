from trax_fxns import TRAX

"""
    Created by Ryan Sundermeyer
    https://github.com/rsunderr
    rwork@sundermeyer.com
"""
"""
try:
    subprocess.run(["sudo", "chmod", "777", "/dev/ttyUSB1"], check=True)
except:
    pass
"""

trax = TRAX()
trax.connect()

# kStopContinuousMode
#frameID = "kStopContinuousMode"
#trax.send_packet(frameID)

frameID = "kSetDataComponents"
payload = (6, 0x15, 0x16, 0x17, 0x5, 0x18, 0x19) # 6 comp's: ax ay az yaw pitch roll
trax.send_packet(frameID, payload)

# kGetData
frameID = "kGetData"
trax.send_packet(frameID)

# kGetDataResp
data = trax.recv_packet(payload)
print(data)

trax.close()