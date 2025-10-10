import subprocess, time

# import FSMs
from shared_memory                          import SharedMemoryWrapper
from fsm.gate_fsm                           import Gate_FSM
from fsm.octagon_fsm                        import Octagon_FSM
from fsm.slalom_fsm                         import Slalom_FSM
from fsm.return_fsm                         import Return_FSM
from fsm.fsm                                import FSM_Template

#import modules
from modules.pid.pid_interface              import PIDInterface
from modules.sensors.a50_dvl.dvl_interface  import DVL_Interface
from modules.vision.vision_main             import VisionDetection
from modules.motors.kill_motors             import kill_motors
from utils.socket_send                      import set_screen


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
DELAY = 0 #s

# initialize objects
pid_object = PIDInterface(shared_memory_object)
dvl_object = DVL_Interface(shared_memory_object)
vis_object = VisionDetection(shared_memory_object)

# initialize modes
gate_modules = [pid_object, dvl_object]
gate_mode   = Gate_FSM(shared_memory_object, gate_modules)
slalom_mode = Slalom_FSM(shared_memory_object, [])
oct_mode    = Octagon_FSM(shared_memory_object, [])
return_mode = Return_FSM(shared_memory_object, [])

mode_list = [gate_mode, slalom_mode, oct_mode, return_mode] # order of modes

def main():
    """
    Main function - intializes mode and starts loop
    """
    # make linked list of modes
    make_list(mode_list)
    
    # start initial mode
    mode = mode_list[0] # mode pointer
    mode.start()
    # loop
    run_loop(mode)

def run_loop(mode: FSM_Template) -> None:
    """
    Looping function, handles mode transitions
    """
    while shared_memory_object.running.value:
        time.sleep(DELAY) # loop delay
        
        if mode is not None:
            mode.loop() # run current mode loop
            if mode.complete:
                mode = mode.next()   # transition to next mode
        else: # exit loop if no mode
            stop()
            break

def stop():
    """
    Soft kill the robot
    """
    shared_memory_object.running.value = 0 # kill gracefully
    time.sleep(0.5)
    kill_motors()

def make_list(modes: list[FSM_Template]) -> None:
    """
    Make a linked list of modes from a list of modes
    """
    for i in range(len(modes)-1):
        modes[i].next_mode = modes[i+1]
        
    modes[len(modes)-1].next_mode = None # end chain


if __name__ == '__main__':
    print("RUN FROM LAUNCH")
    try:
        main()
    except KeyboardInterrupt:
        print("keyboard interrupt detected, stopping program")
        shared_memory_object.running.value = 0
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        
        