from shared_memory                          import SharedMemoryWrapper
from fsm.test_fsm                               import Test_FSM
from utils.socket_send                            import set_screen
from modules.test_module.test_process       import Test_Process
from fsm.gate_fsm                               import Gate_FSM
from fsm.slalom_fsm                             import Slalom_FSM
from fsm.octagon_fsm                            import Octagon_FSM
import time
import os
"""
    discord: @.kech
    github: @rsunderr

    Mission Control for managing modes
    
"""
# create shared memory object
shared_memory_object = SharedMemoryWrapper()
delay = 0.25#s

# create test processes
#test_object = Test_Process(shared_memory_object)

# initialize modes
gate_modules = []
oct_modules = []
slalom_modules = []

gate_mode   = Gate_FSM(shared_memory_object, gate_modules)
oct_mode    = Octagon_FSM(shared_memory_object, oct_modules)
slm_mode    = Slalom_FSM(shared_memory_object, slalom_modules)

# initialize values
shared_memory_object.dvl_x.value = 0
shared_memory_object.dvl_y.value = 0
shared_memory_object.dvl_z.value = 0.5

gate_mode.testing = True
oct_mode.testing = True
slm_mode.testing = True
slm_mode.y_buffer = 100

def main():
    gate_mode.start()
    loop("GATE")

def loop(mode):
    """
    Looping function, mostly mode transitions within conditionals
    """
    if not shared_memory_object.running.value: return
    #time.sleep(delay)

    print(f"MODE = {mode}")
    print(f"GATE: \tactive={gate_mode.active}\tcomplete={gate_mode.complete}")
    print(f"OCT: \tactive={oct_mode.active}\tcomplete={oct_mode.complete}")
    print(f"SLM: \tactive={slm_mode.active}\tcomplete={slm_mode.complete}\n")

    # TRANSITIONS-----------------------------------------------------------------------------------------------------------------------
    match(mode):
        case "GATE": # transition: GATE -> SLM
            gate_mode.loop()
            if gate_mode.complete:
                slm_mode.start()
                mode = "SLM"
        case "SLM": # transition: SLM -> OCT
            slm_mode.loop()
            if slm_mode.complete:
                oct_mode.start()
                mode = "OCT"
        case "OCT": # transition: OCT -> OFF
            stop()
            return
            oct_mode.loop()
            if oct_mode.complete:
                stop() # turn off robot
        case _: # invalid mode
            print(f"INVALID MODE {mode}")


    # increment x
    shared_memory_object.dvl_x.value += 0.54
    loop(mode)
    

def stop():
    """
    Soft kill the robot
    """
    shared_memory_object.running.value = 0 # kill gracefully
    #os.system("pkill -f zed") # kill zed
    #os.system("pkill -f python3") # kill python3

if __name__ == '__main__':
    print("RUN FROM MISSION CONTROL")
    try:
        main()
    except KeyboardInterrupt:
        print("Keyboard interrupt received, stopping mission control.")
        stop()