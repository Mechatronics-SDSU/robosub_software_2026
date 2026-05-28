from trax_fxns import TRAX
from trax_interface import trax_interface

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

trax = trax_interface()
trax.setup()



# kStopContinuousMode
#frameID = "kStopContinuousMode"
#trax.send_packet(frameID)

#frameID = "kSetDataComponents"
#payload = (3, 0x4A, 0x4B, 0x4C) # 6 comp's: ax ay az yaw pitch roll
#trax.send_packet(frameID, payload)

# kGetData
#frameID = "kGetData"
#trax.send_packet(frameID)

# kGetDataResp
#data = trax.recv_packet(payload)
#print(data)


#frameID = "kGetFunctionalMode"
#trax.send_packet(frameID)


trax.close()