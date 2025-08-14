from multiprocessing                        import Process, Value
from shared_memory                          import SharedMemoryWrapper
from gate_fsm                               import Gate_FSM
from octagon_fsm                            import Octagon_FSM
from slalom_fsm                             import Slalom_FSM
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
gate_modules = [pid_object, dvl_object]
oct_modules = []
slalom_modules = []
cf_modules = [pid_object, dvl_object]

gate_mode   = Gate_FSM(shared_memory_object, gate_modules)
oct_mode    = Octagon_FSM(shared_memory_object, oct_modules)
slm_mode    = Slalom_FSM(shared_memory_object, slalom_modules)
cf_mode     = CoinFlip_FSM(shared_memory_object, cf_modules)

def main():
    """
    Main function
    """
    #gate_mode.start() # start gate mode
    gate_mode.start()
    loop("GATE")

    # join processes
    #gate_mode.join()
    #oct_mode.join()

def loop(mode):
    """
    Looping function, mostly mode transitions within conditionals
    """
    if not shared_memory_object.running.value: return
    #time.sleep(delay)

    # TRANSITIONS-----------------------------------------------------------------------------------------------------------------------
    match(mode):
        case "GATE": 
            gate_mode.loop()
            if gate_mode.complete: # transition: GATE -> SLM
                slm_mode.start()
                mode = "SLM"
        case "SLM": 
            slm_mode.loop()
            if slm_mode.complete: # transition: SLM -> OCT
                oct_mode.start()
                mode = "OCT"
        case "OCT":
            stop() # FIXME
            return # FIXME
            oct_mode.loop()
            if oct_mode.complete: # transition: OCT -> OFF
                stop() # turn off robot
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
    print("RUN FROM LAUNCH")
    try:
        main()
        loop("GATE")
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        
