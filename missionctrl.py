from shared_memory                          import SharedMemoryWrapper
from gate_fsm                               import Gate_FSM
from octagon_fsm                            import Octagon_FSM
import time
import os
"""
    discord: @.kech
    github: @rsunderr

    Mission Control for managing modes
    
"""
class MissionControl:
    """
    Mission Control - Manages enabling/disabling and transitions for modes (FSMs)
    """
    def __init__(self):
        """
        Mission Control constructor
        """
        # create shared memory object
        self.shared_memory_object = SharedMemoryWrapper()

        # initialize modes
        self.gate_mode  = Gate_FSM(self.shared_memory_object)
        self.oct_mode   = Octagon_FSM(self.shared_memory_object)

        self.gate_mode.start() # start gate mode
    
        self.loop() # loop

        # join processes
        #self.gate_mode.join()
        #self.oct_mode.join()

    def loop(self):
        """
        Looping function, mostly mode transitions within conditionals
        """
        while self.shared_memory_object.running.value:
            time.sleep(0.001)

            self.gate_mode.loop()
            self.oct_mode.loop()

            # TRANSITIONS-----------------------------------------------------------------------------------------------------------------------
            if self.gate_mode.state == "NEXT": # transition: gate mode -> octagon mode
                #self.gate_mode.stop()
                self.oct_mode.start()
            if self.oct_mode.state == "DONE": # transition: octagon mode -> off
                self.stop() # turn off robot
    
    def stop(self):
        """
        Fully kill the robot
        """
        self.shared_memory_object.running.value = 0 # kill gracefully
        os.system("pkill -f zed") # kill zed
        os.system("pkill -f python3") # kill python3