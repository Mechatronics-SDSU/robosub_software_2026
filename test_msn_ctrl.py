from multiprocessing                        import Process, Value
from shared_memory                          import SharedMemoryWrapper
from fsm.test_fsm                           import Test_FSM
from utils.socket_send                      import set_screen
from modules.test_module.test_process       import Test_Process
from fsm.gate_fsm                               import Gate_FSM
from fsm.slalom_fsm                             import Slalom_FSM
from fsm.octagon_fsm                            import Octagon_FSM
from fsm.return_fsm                             import Return_FSM
import time
import os
import random;


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

# create test processes
#test_object = Test_Process(shared_memory_object)

# initialize modes
return_mode = Return_FSM(shared_memory_object, [])

# initialize values

try:
    delay = int(input("Enter time delay in seconds:")) #s
    shared_memory_object.dvl_x.value = int(input("Enter starting x value: "))
    shared_memory_object.dvl_y.value = int(input("Enter starting y value: "))
    shared_memory_object.dvl_z.value = int(input("Enter starting z value: "))
    mult = int(input("Enter step multiplier: "))
except ValueError:
    print("Invalid input, using default values")
    delay = 2
    shared_memory_object.dvl_x.value = 0
    shared_memory_object.dvl_y.value = 0
    shared_memory_object.dvl_z.value = 0
    mult = 1

def main():
    return_mode.start()
    return_mode.state = "MP1"
    return_mode.x1 = 0
    return_mode.y1 = 0
    return_mode.x2 = 1
    return_mode.y2 = 0
    loop("RETURN")

def loop(mode):
    """
    Looping function, mostly mode transitions within conditionals
    """
    while shared_memory_object.running.value:
        time.sleep(delay)

        return_mode.loop()

        # increment x,y,z by rand value with multiplier
        if mult >= 1:
            shared_memory_object.dvl_x.value += mult * random.uniform(-0.1, 1)
            shared_memory_object.dvl_y.value += mult * random.uniform(-0.1, 1)
            shared_memory_object.dvl_z.value += mult * random.uniform(-0.1, 1)
        else:
        # if mult < 1, mult = 1
            shared_memory_object.dvl_x.value += random.uniform(-0.1, 1)    
            shared_memory_object.dvl_y.value += random.uniform(-0.1, 1)    
            shared_memory_object.dvl_z.value += random.uniform(-0.1, 1)


        print(return_mode, return_mode.state)
        print("\nx:"+ str(shared_memory_object.dvl_x.value))
        print("y:" + str(shared_memory_object.dvl_y.value)) 
        print("z:" + str(shared_memory_object.dvl_z.value) + "\n")


def stop():
    """
    Soft kill the robot
    """
    shared_memory_object.running.value = 0 # kill gracefully

if __name__ == '__main__':
    print("RUN FROM MISSION CONTROL")
    try:
        main()
    except KeyboardInterrupt:
        print("Keyboard interrupt received, stopping mission control.")
        stop()