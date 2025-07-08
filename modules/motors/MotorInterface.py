from modules.motors.hierarchical_state_machine   import HierarchicalStateMachine
import time

#from MotorWrapper import Can_Wrapper
"""
    discord: @kialli
    github: @kchan5071

    This module is responsible for interfacing the shared memory object with the hierarchical state machine.
    
"""

class MotorInterface:

    def __init__(self, shared_memory_object):
        self.shared_memory_object = shared_memory_object
        self.heirarchical_state_machine = HierarchicalStateMachine()


    def get_depth(self):
        """
        Get the depth from the shared memory object
        """
        return self.shared_memory_object.depth.value

    #should start HFSM
    def run_loop(self):
        print("Hierarchical State Machine initialized.")
        # Example usage

        print("Current States:")
        print(self.heirarchical_state_machine.states)

        # Example of running the state machine
        current_state = "Gate"  
        while True:
            next_state = self.heirarchical_state_machine.get_next_state(current_state, "on_complete")
            if next_state:
                print(f"Transitioning from {current_state} to {next_state}")
                current_state = next_state
            else:
                print(f"No transition found for state {current_state}")
            
            # Simulate some processing time
            time.sleep(1)





        while self.shared_memory_object.running.value:   
            pass