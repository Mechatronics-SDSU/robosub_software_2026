from shared_memory                          import SharedMemoryWrapper
from gate_fsm                               import Gate_FSM
from octagon_fsm                            import Octagon_FSM
import time
"""
    discord: @.kech
    github: @rsunderr

    Mission Control for managing modes
    
"""
# manages modes of operation for the submarine
class MissionControl:
    def __init__(self):
        # create shared memory object
        self.shared_memory_object = SharedMemoryWrapper()

        # initialize modes
        self.gate_mode  = Gate_FSM(self.shared_memory_object)
        self.oct_mode   = Octagon_FSM(self.shared_memory_object)

        self.gate_mode.start() # start gate mode
    
        self.loop() # loop

        # join processes
        self.gate_mode.join()
        self.oct_mode.join()

    # looping function
    def loop(self):
        while self.shared_memory_object.running.value:
            time.sleep(0.001)

            self.gate_mode.loop()
            self.oct_mode.loop()

            # transition: gate mode -> octagon mode
            if self.gate_mode.state == "DONE": 
                self.oct_mode.start()
                print("GATE MODE FINISHED")
            # transition: octagon mode -> off
            if self.oct_mode.state == "DONE": 
                self.shared_memory_object.running.value = 0 # end loop
                print("OCTAGON MODE FINISHED")

