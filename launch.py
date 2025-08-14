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
from modules.pid.pid_interface              import PIDInterface
from modules.sensors.a50_dvl.dvl_interface  import DVL_Interface
from modules.vision.vision_main             import VisionDetection
from socket_send                            import set_screen
from coinflip_fsm                           import CoinFlip_FSM

"""
    discord: @.kech, @kialli
    github: @rsunderr, @kchan5071
    
    Runs mission control code and starts the sub
    
"""
# permissions fix
device_path = '/dev/ttyACM0'
subprocess.run(["sudo", "chmod", "777", device_path], check=True)
print(f"Permissions changed for {device_path}")

# create shared memory object
shared_memory_object = SharedMemoryWrapper()
delay = 0.001#s

# initialize objects
pid_object = PIDInterface(shared_memory_object)
dvl_object = DVL_Interface(shared_memory_object)
vis_object = VisionDetection(shared_memory_object)

# initialize modes
cf_modules = [pid_object, dvl_object]
gate_modules = [pid_object, dvl_object]
slalom_modules = []
oct_modules = []
rtrn_modules = []

cf_mode     = CoinFlip_FSM(shared_memory_object, cf_modules)
gate_mode   = Gate_FSM(shared_memory_object, gate_modules)
slalom_mode    = Slalom_FSM(shared_memory_object, slalom_modules)
oct_mode    = Octagon_FSM(shared_memory_object, oct_modules)
return_mode = Return_FSM(shared_memory_object, rtrn_modules)

def main():
    """
    Main function
    """
    # start gate mode and loop
    gate_mode.start()
    loop(gate_mode)

def loop(mode):
    """
    Looping function, mostly mode transitions within conditionals
    """
    if not shared_memory_object.running.value: return
    #time.sleep(delay)

    # TRANSITIONS-----------------------------------------------------------------------------------------------------------------------
    match(mode.name):
        case gate_mode.name: # gate mode
            gate_mode.loop()
            if mode.complete: next_mode(slalom_mode) # transition: gate -> slalom
        case slalom_mode.name: # slalome mode
            slalom_mode.loop()
            if mode.complete: next_mode(oct_mode) # transition: slalom -> octagon
        case oct_mode.name: # octagon mode
            oct_mode.loop()
            if mode.complete: next_mode(return_mode) # transition: octagon -> return
        case return_mode.name: # return mode
            return_mode.loop()
            if return_mode.complete: stop() # transition: return -> off
        case _: # invalid mode
            print(f"INVALID MODE {mode}")

def next_mode(next_mode):
    """
    Start next mode
    """
    next_mode.start() # start next mode
    loop(next_mode.name) # loop

def stop():
    """
    Soft kill the robot
    """
    shared_memory_object.running.value = 0 # kill gracefully

if __name__ == '__main__':
    print("RUN FROM LAUNCH")
    try:
        main()
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        
