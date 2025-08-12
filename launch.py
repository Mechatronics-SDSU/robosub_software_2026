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
try:
    from modules.gps.gps_interface              import GPSInterface
except Exception as e:
    print("no gps module: ", e)
from socket_send                            import set_screen

"""
    discord: @kialli, @.kech
    github: @kchan5071, @rsunderr
    
    Runs mission control code and starts the sub
    
"""
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
try:
    gps_object = GPSInterface(shared_memory_object)
except Exception as e:
    print("no gps interface: ", e)


# initialize modes
gate_modules = [pid_object, dvl_object]
oct_modules = []
slalom_modules = []

gate_mode   = Gate_FSM(shared_memory_object, gate_modules)
oct_mode    = Octagon_FSM(shared_memory_object, oct_modules)
slm_mode    = Slalom_FSM(shared_memory_object, slalom_modules)

def main():
    """
    Main function
    """
    mode = "GATE"
    gate_mode.start() # start gate mode
    loop(mode) # loop

    # join processes
    #gate_mode.join()
    #oct_mode.join()

def loop(mode):
    """
    Looping function, mostly mode transitions within conditionals
    """
    if not shared_memory_object.running.value: return
    #time.sleep(delay)

    gate_mode.loop()
    oct_mode.loop()
    # TRANSITIONS-----------------------------------------------------------------------------------------------------------------------
    match(mode):
        case "GATE": # transition: GATE -> OCTGN
            if gate_mode.complete:
                oct_mode.start()
                mode = "OCTGN"
        case "OCTGN": # transition: OCTGN -> OFF
            if oct_mode.complete:
                stop() # turn off robot
    loop(mode)

def stop():
    """
    Soft kill the robot
    """
    shared_memory_object.running.value = 0 # kill gracefully

if __name__ == '__main__':
    print("RUN FROM LAUNCH")
    try:
        # os.system(os.path.expanduser("python3 ~/robosub_software_2025/display_manager/stop_services.py"))
        # time.sleep(1)
        # os.system(os.path.expanduser("python3 ~/robosub_software_2025/display_manager/start_services.py"))
        main()
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        
