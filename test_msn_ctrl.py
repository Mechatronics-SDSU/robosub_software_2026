from multiprocessing                        import Process, Value
from shared_memory                          import SharedMemoryWrapper
from gate_fsm                               import Gate_FSM
from octagon_fsm                            import Octagon_FSM
from slalom_fsm                             import Slalom_FSM
from return_fsm                             import Return_FSM
import subprocess
import time
import os

#import modules
#from modules.pid.pid_interface              import PIDInterface
#from modules.sensors.a50_dvl.dvl_interface  import DVL_Interface
#from modules.vision.vision_main             import VisionDetection
from socket_send                            import set_screen
from coinflip_fsm                           import CoinFlip_FSM

"""
    discord: @.kech
    github: @rsunderr

    Mission Control for managing modes
    
"""
# create shared memory object
shared_memory_object = SharedMemoryWrapper()
delay = 0.25#s

# initialize objects
#pid_object = PIDInterface(shared_memory_object)
#dvl_object = DVL_Interface(shared_memory_object)
#vis_object = VisionDetection(shared_memory_object)

# initialize objects
#pid_object = PIDInterface(shared_memory_object)
#dvl_object = DVL_Interface(shared_memory_object)
#vis_object = VisionDetection(shared_memory_object)

# initialize modes
cf_modules = []#[pid_object, dvl_object]
gate_modules = []#[pid_object, dvl_object]
slalom_modules = []
oct_modules = []
rtrn_modules = []

cf_mode     = CoinFlip_FSM(shared_memory_object, cf_modules)
gate_mode   = Gate_FSM(shared_memory_object, gate_modules)
slalom_mode    = Slalom_FSM(shared_memory_object, slalom_modules)
oct_mode    = Octagon_FSM(shared_memory_object, oct_modules)
return_mode = Return_FSM(shared_memory_object, rtrn_modules)

# initialize values
shared_memory_object.dvl_x.value = 0
shared_memory_object.dvl_y.value = 0
shared_memory_object.dvl_z.value = 1

gate_mode.testing = True
oct_mode.testing = True
slalom_mode.testing = True
return_mode.testing = True
# ignore buffers
gate_mode.z_buffer = 100
slalom_mode.y_buffer = 100
oct_mode.z_buffer = 100

def main():
    gate_mode.start()
    loop("GATE")

def loop(mode):
    """
    Looping function, mostly mode transitions within conditionals
    """
    if not shared_memory_object.running.value: return
    time.sleep(delay)
    shared_memory_object.dvl_x.value += 0.5

    # TRANSITIONS-----------------------------------------------------------------------------------------------------------------------
    match(mode):
        case "GATE": 
            gate_mode.loop()
            if gate_mode.complete: # transition: GATE -> SLM
                slalom_mode.start()
                mode = "SLM"
        case "SLM": 
            slalom_mode.loop()
            if slalom_mode.complete: # transition: SLM -> OCT
                oct_mode.start()
                mode = "OCT"
        case "OCT":
            oct_mode.loop()
            if oct_mode.complete: # transition: OCT -> OFF
                return_mode.start()
                mode = "RETURN"
        case "RETURN":
            return_mode.loop()
            if return_mode.complete: # transition: RETURN -> OFF
                stop()
                return
        case _: # invalid mode
            print(f"INVALID MODE {mode}")


    loop(mode)
    

def stop():
    """
    Soft kill the robot
    """
    shared_memory_object.running.value = 0 # kill gracefully

if __name__ == '__main__':
    print("RUN FROM MISSION CONTROL")
    try:
        main()
    except KeyboardInterrupt:
        print("Keyboard interrupt received, stopping mission control.")
        stop()