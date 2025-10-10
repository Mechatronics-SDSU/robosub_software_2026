from fsm.fsm                                    import FSM_Template
from utils.socket_send                          import set_screen
import yaml
import os
"""
    discord: @.kech
    github: @rsunderr

    FSM for testing purposes
    
"""

class Test_FSM(FSM_Template):
    """
    FSM testing sandbox
    """
    def __init__(self, shared_memory_object, run_list):
        """
        Test FSM constructor
        """
        # call parent constructor
        super().__init__(shared_memory_object, run_list)
        self.name = "TEST"
        self.testing = True # print instead of display

        # TARGET VALUES-----------------------------------------------------------------------------------------------------------------------
        self.x_buffer = self.y_buffer = self.z_buffer = self.x1 = self.y1 = self.x2 = self.y2 = self.x3 = self.y3 = (None, None, None, None, None, None)
        with open(os.path.expanduser("~/robosub_software_2025/objects.yaml"), 'r') as file: # read from yaml
            data = yaml.safe_load(file)
            course = data['course']
            self.x_buffer = data[course]['return']['x_buf']
            self.y_buffer = data[course]['return']['y_buf']
            self.z_buffer = data[course]['return']['z_buf']
            self.x1 = data[course]['return']['x1']
            self.y1 = data[course]['return']['y1']
            self.x2 = data[course]['return']['x2']
            self.y2 = data[course]['return']['y2']
            self.x3 = data[course]['return']['x3']
            self.y3 = data[course]['return']['y3']
            self.depth = data[course]['return']['depth']

    def start(self):
        """
        Start FSM
        """
        super().start()  # call parent start method

        # set initial state
        self.next_state("WP1")

    def next_state(self, next):
        """
        Change to next state
        """
        if not self.active or self.state == next: return # do nothing if not enabled or no state change
        # STATES-----------------------------------------------------------------------------------------------------------------------
        match(next):
            case "INIT": return # initial state
            case "WP1":
                self.shared_memory_object.target_x.value = self.x1
                self.shared_memory_object.target_y.value = self.y1
                self.shared_memory_object.target_z.value = self.depth
            case "WP2":
                self.shared_memory_object.target_x.value = self.x2
                self.shared_memory_object.target_y.value = self.y2
                self.shared_memory_object.target_z.value = self.depth
            case "WP3":
                self.shared_memory_object.target_x.value = self.x3
                self.shared_memory_object.target_y.value = self.y3
                self.shared_memory_object.target_z.value = self.depth
            case "DONE": # fully disable and kill
                self.display(255, 0, 0)
                self.stop()
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
        self.display(255,0,0) # update display

        # TRANSITIONS------------------------------------------------------------------------------------------------------
        match(self.state):
            case "INIT" | "DONE": return
            case "WP1":
                if self.reached_xy(self.x1, self.y1): self.next_state("WP2")
            case "WP2":
                if self.reached_xy(self.x2, self.y2): self.next_state("WP3")
            case "WP3":
                if self.reached_xy(self.x3, self.y3): self.next_state("DONE")
            case _: # do nothing if invalid state
                print(f"{self.name} INVALID STATE {self.state}")