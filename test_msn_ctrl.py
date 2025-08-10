from shared_memory                          import SharedMemoryWrapper
from test_fsm                               import Test_FSM
from socket_send                            import set_screen
from modules.test_module.test_process       import Test_Process
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
test_object = Test_Process(shared_memory_object)
# initialize modes
test_list = []#[test_object]
test_mode1  = Test_FSM(shared_memory_object, test_list)
test_mode2 = Test_FSM(shared_memory_object, test_list)
test_mode1.name = "TEST1"
test_mode2.name = "TEST2"

test_mode1.start() # start test1

# join processes
#test_mode1.join()
#test_mode2.join()

def loop(mode):
    """
    Looping function, mostly mode transitions within conditionals
    """
    if not shared_memory_object.running.value: return
    time.sleep(delay)

    # SIMULATING DVL XYZ--------------------------------------------------------------------------------------------------------------
    #shared_memory_object.dvl_x.value = float(input("dvl_x = "))
    #shared_memory_object.dvl_y.value = float(input("dvl_y = "))
    #shared_memory_object.dvl_z.value = float(input("dvl_z = "))
    shared_memory_object.dvl_x.value += 0.25 # increment dvl x each loop

    test_mode1.loop()
    test_mode2.loop()

    # TRANSITIONS-----------------------------------------------------------------------------------------------------------------------
    match(mode):
        case "TEST1":
            if test_mode1.complete:
                shared_memory_object.dvl_x.value = 0 # back to start
                test_mode2.start()
                mode = "TEST2"
        case "TEST2":
            if test_mode2.complete:
                stop() # turn off robot

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
        loop("TEST1") # start loop
    except KeyboardInterrupt:
        print("Keyboard interrupt received, stopping mission control.")
        stop()