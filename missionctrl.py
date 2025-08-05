from multiprocessing                        import Process, Value
from shared_memory                          import SharedMemoryWrapper
from test_fsm                               import Test_FSM
from spin_fsm                               import Spin_FSM
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
        self.test_mode = Test_FSM(self.shared_memory_object)
        self.spin_mode = Spin_FSM(self.shared_memory_object)

        self.test_mode.start()

        self.loop()

        self.test_mode.join()
        self.spin_mode.join()

    def loop(self):
        while True:#self.shared_memory_object.running.value:
            time.sleep(0.001)

            self.test_mode.loop()
            self.spin_mode.loop()

            # transition test mode -> spin mode
            if self.test_mode.state == "DONE":
                self.spin_mode.start()
            # transition spin mode -> off
            if self.spin_mode.state == "DONE":
                return

