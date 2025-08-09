from fsm                                    import FSM_Template
from socket_send                            import set_screen

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
        self.name = "OCTGN"

        # buffers
        self.x_buffer = 0.3#m
        self.y_buffer = 0.3#m
        self.z_buffer = 0.5#m

        #TARGET VALUES-----------------------------------------------------------------------------------------------------------------------
        self.oct_x, self.oct_y, self.gate_x, self.gate_y, self.gate_z = (None, None, None, None, None)
        self.depth = 1 # swimming depth
        with open(os.path.expanduser("~/robosub_software_2025/objects.yaml"), 'r') as file: # read from yaml
            data = yaml.safe_load(file)
            self.oct_x =    data['objects']['octagon']['x']
            self.oct_y =    data['objects']['octagon']['y']
            self.gate_x =   data['objects']['gate']['x']
            self.gate_y =   data['objects']['gate']['y']
            self.gate_z =   data['objects']['gate']['z']

    def start(self):
        """
        Start FSM by enabling and starting processes
        """
        super().start()  # call parent start method
        print("STARTING OCTAGON MODE")

        # set initial state
        self.next_state("TO_OCT")

    def next_state(self, next):
        """
        Change to next state
        """
        if not self.active or self.state == next: return # do nothing if not enabled or no state change
        match(next):
            case "INIT": # initial state
                pass
            case "TO_OCT": # drive to octagon
                print("TO_OCT")
                self.shared_memory_object.target_x.value = self.oct_x
                self.shared_memory_object.target_y.value = self.oct_y
                self.shared_memory_object.target_z.value = self.depth
            case "RISE_OCT": # surface in octagon
                print("RISE_OCT")
                self.shared_memory_object.target_z.value = 0
            case "DESCEND": # descend after surfacing
                print("DESCEND")
                time.sleep(1) # wait at surface for 1s
                self.shared_memory_object.target_z.value = self.depth
            case "TO_GATE": # return to gate after octagon
                print("TO_GATE")
                self.shared_memory_object.target_x.value = self.gate_x
                self.shared_memory_object.target_y.value = self.gate_y
                self.shared_memory_object.target_z.value = self.gate_z
            case "RETURN": # return to starting position
                print("RETURN")
                self.shared_memory_object.target_x.value = 0
                self.shared_memory_object.target_y.value = 0
                self.shared_memory_object.target_z.value = self.depth
            case "RISE_END": # surface at end of run
                print("RISE_END")
                self.shared_memory_object.target_z.value = 0
            case "DONE": # end of run
                print("DONE")
                self.stop()
                return
            case _: # do nothing if invalid state
                print("OCTAGON: INVALID NEXT STATE", self.state)
                return
        self.state = next
    
    def loop(self):
        """
        Loop function, mostly state transitions within conditionals
        """
        if not self.active: return # do nothing if not enabled
        self.display(0, 0, 255) # update display
        #TRANSITIONS-----------------------------------------------------------------------------------------------------------------------
        match(self.state):
            case "INIT": pass
            case "TO_OCT": # transition: TO_OCT -> RISE_OCT
                if self.reached_xyz(self.oct_x, self.oct_y, self.depth):
                    self.next_state("RISE_OCT")
            case "RISE_OCT": # transition: RISE_OCT -> DESCEND
                if abs(self.shared_memory_object.dvl_z.value - 0) <= self.z_buffer:
                    self.next_state("DESCEND")
            case "DESCEND": # transition: DESCEND -> TO_GATE
                if abs(self.shared_memory_object.dvl_z.value - self.depth) <= self.z_buffer:
                    self.next_state("TO_GATE")
            case "TO_GATE": # transition: TO_GATE -> RETURN
                if self.reached_xyz(0, 0, self.depth):
                    self.next_state("RETURN")
            case "RETURN": # transition: RETURN -> RISE_END
                if self.reached_xyz(self.gate_x, self.gate_y, self.gate_z):
                    self.next_state("RISE_END")
            case "RISE_END": # transition: RISE_END -> DONE
                if abs(self.shared_memory_object.dvl_z.value - 0) <= self.z_buffer:
                    self.next_state("DONE")
            case "DONE": pass
            case _: # do nothing if invalid state
                print("OCTAGON: INVALID LOOP STATE", self.state)
                return