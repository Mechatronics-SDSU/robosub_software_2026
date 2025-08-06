from multiprocessing                        import Process, Value
from shared_memory                          import SharedMemoryWrapper
from test_fsm                               import Test_FSM
from spin_fsm                               import Spin_FSM
from gate_fsm                               import Gate_FSM
from octagon_fsm                            import Octagon_FSM
import time
"""
    discord: @.kech
    github: @rsunderr

    Mission Control
    
"""

class MissionControl:
    def __init__(self):
        # create shared memory
        self.shared_memory_object = SharedMemoryWrapper()
        self.gate_mode  = Gate_FSM()
        self.oct_mode   = Octagon_FSM()

        self.gate_mode.start()
    
        self.loop()

        self.gate_mode.join()
        self.oct_mode.join()

    def loop(self):
        while self.shared_memory_object.running.value:
            time.sleep(0.001)

            self.gate_mode.loop()

            # transition gate mode -> spin mode
            if self.gate_mode.state == "DONE":
                self.oct_mode.start()
            # transition octagon mode -> off
            if self.oct_mode.state == "DONE":
                return

