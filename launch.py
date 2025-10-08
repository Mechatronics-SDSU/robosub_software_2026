import subprocess, time

# import FSMs
from shared_memory                          import SharedMemoryWrapper
from fsm.gate_fsm                           import Gate_FSM
from fsm.octagon_fsm                        import Octagon_FSM
from fsm.slalom_fsm                         import Slalom_FSM
from fsm.return_fsm                         import Return_FSM

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
delay = 0 #s

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

mode = None # mode pointer

# linked list of modes
gate_mode.next_mode = slalom_mode
slalom_mode.next_mode = oct_mode
oct_mode.next_mode = return_mode
return_mode.next_mode = None # ends chain

def main():
    """
    Main function
    """
    # start initial mode
    global mode
    mode = gate_mode
    mode.start()
    # loop
    loop()

def loop():
    """
    Looping function, handles mode transitions
    """
    global mode
    while shared_memory_object.running.value:
        time.sleep(delay) # loop delay
        
        if mode is not None:
            mode.loop() # run current mode loop
            if mode.complete:
                mode = mode.next()   # transition to next mode
        else:
            break # exit loop if no mode

def stop():
    """
    Soft kill the robot
    """
    shared_memory_object.running.value = 0 # kill gracefully
    time.sleep(0.5)
    kill_motors()


if __name__ == '__main__':
    print("RUN FROM LAUNCH")
    try:
        main()
    except KeyboardInterrupt:
        print("keyboard interrupt detected, stopping program")
        shared_memory_object.running.value = 0
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        
        