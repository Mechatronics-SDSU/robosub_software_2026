from multiprocessing                        import Process, Value
from shared_memory                          import SharedMemoryWrapper
from fsm.gate_fsm                               import Gate_FSM
from fsm.octagon_fsm                            import Octagon_FSM
from fsm.slalom_fsm                             import Slalom_FSM
from fsm.return_fsm                             import Return_FSM
import subprocess
import time
import os

#import modules
from modules.pid.pid_interface              import PIDInterface
from modules.sensors.a50_dvl.dvl_interface  import DVL_Interface
from modules.vision.vision_main             import VisionDetection
from utils.socket_send                            import set_screen
from fsm.coinflip_fsm                           import CoinFlip_FSM

#kill module
from modules.motors.kill_motors             import kill_motors

"""
    discord: @.kech, @kialli
    github: @rsunderr, @kchan5071
    discord: @.kech, @kialli
    github: @rsunderr, @kchan5071
    
    Runs mission control code and starts the sub
    
"""
# permissions fix
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
cf_modules = []#[pid_object, dvl_object]
gate_modules = [pid_object, dvl_object]
slalom_modules = []
oct_modules = []
rtrn_modules = []

cf_mode     = CoinFlip_FSM(shared_memory_object, cf_modules)
gate_mode   = Gate_FSM(shared_memory_object, gate_modules)
slalom_mode = Slalom_FSM(shared_memory_object, slalom_modules)
oct_mode    = Octagon_FSM(shared_memory_object, oct_modules)
return_mode = Return_FSM(shared_memory_object, rtrn_modules)

def main():
    """
    Main function
    """
    slalom_mode.z_buffer = 100
    gate_mode.z_buffer = 100 # FIXME
    oct_mode.z_buffer = 100
    return_mode.z_buffer = 100
    mode = "GATE"

    gate_mode.start()

    loop(mode)

def loop(mode):
    """
    Looping function, mostly mode transitions within conditionals
    """
    while shared_memory_object.running.value:
        #time.sleep(delay)
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

def stop():
    """
    Soft kill the robot
    """
    shared_memory_object.running.value = 0 # kill gracefully
    time.sleep(0.1)
    kill_motors()


if __name__ == '__main__':
    print("RUN FROM LAUNCH")
    try:
        main()
    except KeyboardInterrupt:
        print("keyboard interrupt detected, stopping program")
        shared_memory_object.running.value = 0
    except KeyboardInterrupt:
        print("keyboard interrupt detected, stopping program")
        shared_memory_object.running.value = 0
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        
        