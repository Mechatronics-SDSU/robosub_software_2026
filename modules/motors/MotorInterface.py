from modules.motors.ObjectTracking          import Object_Tracking
import time

#from MotorWrapper import Can_Wrapper
"""
    discord: @kialli
    github: @kchan5071

    Mission control
    
"""

class MotorInterface:

    def __init__(self, shared_memory_object):

        self.shared_memory_object = shared_memory_object
        self.Object_Tracking = Object_Tracking()
        self.can = MotorWrapper()


    def get_depth(self):
        """
        Get the depth from the shared memory object
        """
        return self.shared_memory_object.depth.value
    

    #should start HFSM
    def run_loop(self):
        while self.shared_memory_object.running.value:   
            start = time.time()


hierarchical_state_machine