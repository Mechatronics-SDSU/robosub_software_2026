from fsm                                    import *
from socket_send                            import set_screen

import os, yaml, time
"""
    discord: @.kech
    github: @rsunderr

    FSM for returning through gate after octagon
    
"""

class Return_FSM(FSM_Template):
    """
    FSM for return mode - drives back to gate, drives to start, surfaces
    """
    def __init__(self, shared_memory_object, run_list):
        """
        Return FSM constructor
        """
        # call parent constructor
        super().__init__(shared_memory_object, run_list)
        self.name = "RETURN"

        # buffers
        self.x_buffer = 0.3#m
        self.y_buffer = 0.3#m
        self.z_buffer = 0.75#m

        #TARGET VALUES-----------------------------------------------------------------------------------------------------------------------
        self.gate_x, self.gate_y, self.gate_z, self.depth = (None, None, None, None)
        with open(os.path.expanduser("~/robosub_software_2025/objects.yaml"), 'r') as file: # read from yaml
            data = yaml.safe_load(file)
            self.depth =   data['objects']['octagon']['depth'] # swimming depth
            self.gate_x =   data['objects']['gate']['x']
            self.gate_y =   data['objects']['gate']['y']
            self.gate_z =   data['objects']['gate']['z']

    def start(self):
        """
        Start FSM by enabling and starting processes
        """
        super().start()  # call parent start method

        # set initial state
        self.next_state("DESCEND")

    def next_state(self, next):
        """
        Change to next state
        """
        if not self.active or self.state == next: return # do nothing if not enabled or no state change
        match(next):
            case "INIT": return # initial state
            case "DESCEND": # descend in octagon
                self.shared_memory_object.target_z.value = self.depth
            case "TO_GATE": # return to gate after octagon
                self.shared_memory_object.target_x.value = self.gate_x
                self.shared_memory_object.target_y.value = self.gate_y
                self.shared_memory_object.target_z.value = self.gate_z
            case "RETURN": # return to starting position
                self.shared_memory_object.target_x.value = 0
                self.shared_memory_object.target_y.value = 0
                self.shared_memory_object.target_z.value = self.depth
            case "RISE_END": # surface at end of run
                self.shared_memory_object.target_z.value = 0
            case "DONE": # end of run
                self.stop()
                return
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
        self.display(0, 100, 100) # update display
        #TRANSITIONS-----------------------------------------------------------------------------------------------------------------------
        match(self.state):
            case "INIT" | "DONE": return
            case "DESCEND": # transition: DESCEND -> TO_GATE
                if abs(self.shared_memory_object.dvl_z.value - self.depth) <= self.z_buffer:
                    self.next_state("TO_GATE")
            case "TO_GATE": # transition: TO_GATE -> RETURN
                if self.reached_xyz(self.gate_x, self.gate_y, self.gate_z):
                    self.next_state("RETURN")
            case "RETURN": # transition: RETURN -> RISE_END
                if self.reached_xyz(0, 0, self.depth):
                    self.next_state("RISE_END")
            case "RISE_END": # transition: RISE_END -> DONE
                if abs(self.shared_memory_object.dvl_z.value - 0) <= self.z_buffer:
                    self.next_state("DONE")
            case _: # do nothing if invalid state
                print(f"{self.name} INVALID STATE {self.state}")
                return