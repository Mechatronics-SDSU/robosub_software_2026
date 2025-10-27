import subprocess, time

# import FSMs
from shared_memory                          import SharedMemoryWrapper
from fsm.gate_fsm                           import Gate_FSM
from fsm.octagon_fsm                        import Octagon_FSM
from fsm.slalom_fsm                         import Slalom_FSM
from fsm.return_fsm                         import Return_FSM

from modules.sensors.trax2.trax_interface import Trax_Interface
"""
    discord: @.kech
    github: @rsunderr
    
    Meant for testing launch logic and FSMs
    
"""

# create shared memory object
shared_memory_object = SharedMemoryWrapper()
DELAY = 0.2 # if you want to stay on one mode longer, increase delay to a high number

#trax_object = Trax_Interface(shared_memory_object)

gate_mode   = Gate_FSM(shared_memory_object, []) #[trax_object])
slalom_mode = Slalom_FSM(shared_memory_object, [])
oct_mode    = Octagon_FSM(shared_memory_object, [])
return_mode = Return_FSM(shared_memory_object, [])

mode_list = [gate_mode, slalom_mode, oct_mode, return_mode] # order of modes

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
    main_loop(mode)

def main_loop(mode):
    """
    Looping function, handles mode transitions
    """
    while shared_memory_object.running.value:
        time.sleep(DELAY) # loop delay
        # tester code ------------------------------------------
        if mode != return_mode:
            shared_memory_object.dvl_x.value += 0.1
        else:
            shared_memory_object.dvl_x.value -= 0.1
        # ----------------------------------------------------------
        
        if mode is not None:
            mode.loop() # run current mode loop
            display(mode)
            if mode.complete:
                mode = mode.next()   # transition to next mode
        else: # exit loop if no mode
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
    """
    Display function for testing
    """
    if mode is not None: print(f"MODE: {mode.name}:{mode.state}")
    print("x: %.1f -> %.1f" % (shared_memory_object.dvl_x.value, shared_memory_object.target_x.value))
    print("y: %.1f -> %.1f" % (shared_memory_object.dvl_y.value, shared_memory_object.target_y.value))
    print("z: %.1f -> %.1f" % (shared_memory_object.dvl_z.value, shared_memory_object.target_z.value))
    print("\n")

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
        
        