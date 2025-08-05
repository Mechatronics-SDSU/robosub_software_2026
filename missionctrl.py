from multiprocessing                        import Process, Value
from shared_memory                          import SharedMemoryWrapper
from test_fsm                               import Test_FSM
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
        self.test_mode.start()

        self.loop()

        self.test_mode.join()

    def loop(self):
        while True:#self.shared_memory_object.running.value:
            time.sleep(0.001)
            print(self.state)
            self.test_mode.loop()

