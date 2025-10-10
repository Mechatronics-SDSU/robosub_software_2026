from fsm.fsm                                    import FSM_Template
from utils.socket_send                          import set_screen

import os, yaml, time
"""
    discord: @.kech
    github: @rsunderr

    FSM for navigating under and rising up into the octagon
    
"""

class Octagon_FSM(FSM_Template):
    """
    FSM for octagon mode - drives under octagon, surfaces, pauses, descends, drives back to gate, drives to start, surfaces
    """
    def __init__(self, shared_memory_object, run_list):
        """
        Octagon FSM constructor
        """
        # call parent constructor
        super().__init__(shared_memory_object, run_list)
        self.name = "OCTAGON"
        
        #TARGET VALUES-----------------------------------------------------------------------------------------------------------------------
        self.x_buffer = self.y_buffer = self.z_buffer = self.oct_x = self.oct_y = self.oct_z = self.depth = self.pause = 0
        try:
            with open(os.path.expanduser("~/robosub_software_2025/objects.yaml"), 'r') as file: # read from yaml
                data = yaml.safe_load(file)
                course = data['course']
                self.x_buffer = data[course]['octagon']['x_buf']
                self.y_buffer = data[course]['octagon']['y_buf']
                self.z_buffer = data[course]['octagon']['z_buf']
                self.oct_x =    data[course]['octagon']['x']
                self.oct_y =    data[course]['octagon']['y']
                self.oct_z =    data[course]['octagon']['z']
                self.depth =    data[course]['octagon']['depth'] # swimming depth
                self.pause =    data[course]['octagon']['pause'] # pause duration
        except FileNotFoundError:
            print("ERROR: objects.yaml file not found or attempting to read invalid data, using all 0's")
            
    def start(self):
        """
        Start FSM by enabling and starting processes
        """
        super().start()  # call parent start method

        # set initial state
        self.next_state("TO_OCT")

    def next_state(self, next):
        """
        Change to next state
        """
        if not self.active or self.state == next: return # do nothing if not enabled or no state change
        match(next):
            case "INIT": return # initial state
            case "TO_OCT": # drive to octagon
                self.shared_memory_object.target_x.value = self.oct_x
                self.shared_memory_object.target_y.value = self.oct_y
                self.shared_memory_object.target_z.value = self.depth
            case "RISE": # surface in octagon
                self.shared_memory_object.target_z.value = self.oct_z
                self.shared_memory_object.target_yaw.value = -45 # degrees of turn
            case "PAUSE": # pause after surfacing
                time.sleep(self.pause) # wait at surface, turn direction
                self.shared_memory_object.target_yaw.value = 0 # turn back to 0
                self.suspend()
            case _: # do nothing if invalid state
                print(f"{self.name} INVALID NEXT STATE {next}")
                return
        
        self.state = next
        print(f"{self.name}:{self.state}")
    
    def loop(self):
        """
        Loop function, mostly state transitions within conditionals
        """
        if not self.active: return # do nothing if not enabled
        self.display(0, 0, 255) # update display
        #TRANSITIONS-----------------------------------------------------------------------------------------------------------------------
        match(self.state):
            case "INIT" | "PAUSE": return
            case "TO_OCT": # transition: TO_OCT -> RISE
                if self.reached_xy(self.oct_x, self.oct_y):
                    self.next_state("RISE")
            case "RISE": # transition: RISE -> PAUSE
                if self.shared_memory_object.dvl_z.value <= self.z_buffer:
                    self.next_state("PAUSE")
            case _: # do nothing if invalid state
                print(f"{self.name} INVALID STATE {self.state}")
                return