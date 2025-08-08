from multiprocessing                        import Process, Value
from shared_memory                          import SharedMemoryWrapper
from shared_memory                          import SharedMemoryWrapper
from gate_fsm                               import Gate_FSM
from octagon_fsm                            import Octagon_FSM
import subprocess
import time
import os

"""
    discord: @kialli, @.kech
    github: @kchan5071, @rsunderr
    
    Runs mission control code and starts the sub
    
"""
device_path = '/dev/ttyACM0'
# create shared memory object
shared_memory_object = SharedMemoryWrapper()
# initialize modes
gate_mode  = Gate_FSM(shared_memory_object)
oct_mode   = Octagon_FSM(shared_memory_object)

def main():
    """
    Main function
    """
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
        time.sleep(0.001)

        gate_mode.loop()
        oct_mode.loop()

        # TRANSITIONS-----------------------------------------------------------------------------------------------------------------------
        if gate_mode.state == "NEXT": # transition: gate mode -> octagon mode
            #gate_mode.stop()
            oct_mode.start()
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
        
