from multiprocessing                        import Process, Value
from shared_memory                          import SharedMemoryWrapper
from gate_fsm                               import Gate_FSM
from octagon_fsm                            import Octagon_FSM
import subprocess
import time
import os

#import modules
from modules.pid.pid_interface              import PIDInterface
from modules.sensors.a50_dvl.dvl_interface  import DVL_Interface
from modules.vision.vision_main             import VisionDetection
from socket_send                            import set_screen

"""
    discord: @kialli, @.kech
    github: @kchan5071, @rsunderr
    
    Runs mission control code and starts the sub
    
"""
device_path = '/dev/ttyACM0'
# create shared memory object
shared_memory_object = SharedMemoryWrapper()
mode = None
delay = 0.001

# initialize objects
pid_object = PIDInterface(shared_memory_object)
dvl_object = DVL_Interface(shared_memory_object)
vis_object = VisionDetection(shared_memory_object)


# initialize modes
gate_modules = [pid_object, dvl_object]
oct_modules = []
gate_mode  = Gate_FSM(shared_memory_object, gate_modules)
oct_mode   = Octagon_FSM(shared_memory_object, oct_modules)

def main():
    """
    Main function
    """
    mode = "GATE"
    gate_mode.start() # start gate mode
    loop() # loop

    # join processes
    #gate_mode.join()
    #oct_mode.join()

def loop():
    """
    Looping function, mostly mode transitions within conditionals
    """
    while shared_memory_object.running.value:
        time.sleep(delay)

        gate_mode.loop()
        oct_mode.loop()

        match(mode):
            case "GATE":
                if gate_mode.completed:
                    gate_mode.active = False
                    oct_mode.start()

        # TRANSITIONS-----------------------------------------------------------------------------------------------------------------------
        if gate_mode.state == "NEXT": # transition: gate mode -> octagon mode
            gate_mode.active = False # disable gate mode
            oct_mode.start() # start octagon mode
        if oct_mode.state == "DONE": # transition: octagon mode -> off
            stop() # turn off robot

def stop():
    """
    Soft kill the robot
    """
    shared_memory_object.running.value = 0 # kill gracefully

if __name__ == '__main__':
    print("RUN FROM LAUNCH")
    try:
        subprocess.run(["sudo", "chmod", "777", device_path], check=True)
        print(f"Permissions changed for {device_path}")
        main()
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        
