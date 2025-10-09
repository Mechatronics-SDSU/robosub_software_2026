from multiprocessing                        import Process, Value
from shared_memory                          import SharedMemoryWrapper
from fsm.test_fsm                           import Test_FSM
from utils.socket_send                      import set_screen
from modules.test_module.test_process       import Test_Process
from fsm.gate_fsm                               import Gate_FSM
from fsm.slalom_fsm                             import Slalom_FSM
from fsm.octagon_fsm                            import Octagon_FSM
from fsm.return_fsm                             import Return_FSM
import time, os, random, yaml, subprocess


#import modules
#from modules.pid.pid_interface              import PIDInterface
#from modules.sensors.a50_dvl.dvl_interface  import DVL_Interface
#from modules.vision.vision_main             import VisionDetection
#from socket_send                            import set_screen
#from coinflip_fsm                           import CoinFlip_FSM

"""
    discord: @.kech
    github: @rsunderr

    Mission Control for managing modes
    
"""
# create shared memory object
shared_memory_object = SharedMemoryWrapper()

# initialize modes
slalom_mode = Slalom_FSM(shared_memory_object, [])
oct_mode    = Octagon_FSM(shared_memory_object, [])
return_mode = Return_FSM(shared_memory_object, [])
gate_mode   = Gate_FSM(shared_memory_object, [])


mode_list = [gate_mode, slalom_mode, oct_mode, return_mode]

def main():
    """
    Main function
    """
    # make linked list of modes
    make_list(mode_list)

    # start initial mode
    mode = mode_list[0] # mode pointer
    mode.start()
    # loop
    loop(mode)

def loop(mode):
    while shared_memory_object.running.value:
        with open(os.path.expanduser("~/robosub_software_2025/objects.yaml"), 'r') as file:
            data = yaml.safe_load(file)
            course = data['course']
            test_delay = data[course]['delay']
            test_mult  = data[course]['mult']

        time.sleep(test_delay)

        # update shared memory values
        if mode != return_mode:
            shared_memory_object.dvl_x.value += test_mult * random.uniform(-0.1, 1)
            shared_memory_object.dvl_y.value += test_mult * random.uniform(-0.1, 1)
            shared_memory_object.dvl_z.value += test_mult * random.uniform(-0.1, 1)
        else:
            shared_memory_object.dvl_x.value -= test_mult * random.uniform(-0.1, 1)
            shared_memory_object.dvl_y.value -= test_mult * random.uniform(-0.1, 1)
            shared_memory_object.dvl_z.value -= test_mult * random.uniform(-0.1, 1)

        if mode is not None:
            mode.loop()
            display(mode)
            if mode.complete:
                mode = mode.next()
        else:
            stop()
            break

def make_list(modes):
    """
    Make a linked list of modes from a list of modes
    """
    for i in range(len(modes)-1):
        modes[i].next_mode = modes[i+1]
        
    modes[len(modes)-1].next_mode = None # end chain

def display(mode):
    new_entry = {
        'mode': mode.name if mode else "None",
        'state': mode.state if mode else "None",
        'dvl_x': shared_memory_object.dvl_x.value,
        'dvl_y': shared_memory_object.dvl_y.value,
        'dvl_z': shared_memory_object.dvl_z.value,
        'timestamp': time.time()
    }
    # Load existing log or create new
    try:
        with open("log.yaml", "r") as file:
            logs = yaml.safe_load(file) or []
    except FileNotFoundError:
        logs = []

    # Add the new entry
    logs.append(new_entry)

    # Save back to file
    with open("log.yaml", "w") as file:
        yaml.dump(logs, file)


def stop():
    """
    Soft kill the robot
    """
    shared_memory_object.running.value = 0 # kill gracefully

if __name__ == '__main__':
    print("RUN FROM LAUNCH")
    try:
        main()
    except KeyboardInterrupt:
        print("keyboard interrupt detected, stopping program")
        shared_memory_object.running.value = 0
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        
        