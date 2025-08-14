from socket_send                            import set_screen
from fsm                                    import *
import yaml, os
"""
    discord: @.kech
    github: @rsunderr

    FSM for navigating through gate
    
"""

class Gate_FSM(FSM_Template):
    """
    FSM for gate mode - driving through the gate
    """
    def __init__(self, shared_memory_object, run_list):
        """
        Gate FSM constructor
        """
        # call parent constructor
        super().__init__(shared_memory_object, run_list)
        self.name = "GATE"

        # buffers
        self.x_buffer = 0.5#m
        self.y_buffer = 0.7#m
        self.z_buffer = 1.2#m

        # TARGET VALUES-----------------------------------------------------------------------------------------------------------------------
        self.gate_x, self.gate_y, self.gate_z = (None, None, None)
        with open(os.path.expanduser("~/robosub_software_2025/objects.yaml"), 'r') as file: # read from yaml
            data = yaml.safe_load(file)
            self.gate_x = data['objects']['gate']['x']
            self.gate_y = data['objects']['gate']['y']
            self.gate_z = data['objects']['gate']['z']

    def start(self):
        """
        Start FSM by enabling and starting processes
        """
        super().start()  # call parent start method

        # set initial state
        self.next_state("DRIVE")

    def next_state(self, next):
        """
        Change to next state
        """
        if not self.active or self.state == next: return # do nothing if not enabled or no state change
        # STATES-----------------------------------------------------------------------------------------------------------------------
        match(next):
            case "INIT": return # initial state
            case "DRIVE": # drive toward gate
                self.shared_memory_object.target_x.value = self.gate_x
                self.shared_memory_object.target_y.value = self.gate_y
                self.shared_memory_object.target_z.value = self.gate_z
            case "DONE": # disable but not kill (go to next mode)
                self.active = False
                self.complete = True
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
        self.display(0, 255, 0) # update display

        # TRANSITIONS------------------------------------------------------------------------------------------------------
        match(self.state):
            case "INIT" | "DONE": return
            case "DRIVE": # transition: DRIVE -> DONE
                if self.reached_xyz(self.gate_x, self.gate_y, self.gate_z):
                    self.next_state("DONE")
            case _: # do nothing if invalid state
                print(f"{self.name} INVALID STATE {self.state}")

