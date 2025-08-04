from multiprocessing                        import Process, Value
from shared_memory                          import SharedMemoryWrapper
from modules.motors.MotorInterface          import MotorInterface
from modules.pid.pid_interface              import PIDInterface
from modules.sensors.a50_dvl.dvl_interface  import DVL_Interface
from modules.vision.vision_main             import VideoRunner
from utils.kill_button_interface            import Kill_Button_Interface
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
        self.test_mode = Test_FSM()
        self.test_mode.start()

        self.loop()

        self.test_mode.join()

    def loop(self):
        while self.shared_memory_object.running.value:
            time.sleep(0.001)
            print(self.state)
            self.test_mode.loop()

