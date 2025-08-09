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
        
        # create test processes
        test_object = Test_Process(self.shared_memory_object)

        # initialize modes
        test_list = [test_object]
        self.test_mode1  = Test_FSM(self.shared_memory_object, test_list)
        self.test_mode2 = Test_FSM(self.shared_memory_object, test_list)

        self.test_mode1.start() # start test1
    
        self.loop() # loop

        # join processes
        #self.test_mode1.join()
        #self.test_mode2.join()

    def loop(self):
        """
        Looping function, mostly mode transitions within conditionals
        """
        while self.shared_memory_object.running.value:
            time.sleep(0.5)

            self.shared_memory_object.dvl_x.value = float(input("dvl_x = "))
            self.shared_memory_object.dvl_y.value = float(input("dvl_y = "))
            self.shared_memory_object.dvl_z.value = float(input("dvl_z = "))

            self.test_mode1.loop()

            # TRANSITIONS-----------------------------------------------------------------------------------------------------------------------
            if self.test_mode1.state == "NEXT": # transition: gate mode -> octagon mode
                self.test_mode2.start()
            if self.test_mode2.state == "DONE": # transition: octagon mode -> off
                self.stop() # turn off robot
    
    def stop(self):
        """
        Soft kill the robot
        """
        self.shared_memory_object.running.value = 0 # kill gracefully
        #os.system("pkill -f zed") # kill zed
        #os.system("pkill -f python3") # kill python3