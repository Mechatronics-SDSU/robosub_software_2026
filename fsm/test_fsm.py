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

        # buffers
        self.x_buffer = 0#m
        self.y_buffer = 0#m
        self.z_buffer = 0#m

        # TARGET VALUES-----------------------------------------------------------------------------------------------------------------------
        self.gate_x, self.gate_y, self.gate_z = (None, None, None)
        with open(os.path.expanduser("~/robosub_software_2025/objects.yaml"), 'r') as file: # read from yaml
            data = yaml.safe_load(file)
            course = data['course']
            self.gate_x = data[course]['gate']['x']
            self.gate_y = data[course]['gate']['y']
            self.gate_z = data[course]['gate']['z']

    def start(self):
        """
        Start FSM
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
            case "DRIVE":
                self.shared_memory_object.target_x.value = self.gate_x
                self.shared_memory_object.target_y.value = self.gate_y
                self.shared_memory_object.target_z.value = self.gate_z
            case "NEXT": 
                self.shared_memory_object.target_x.value = 5
                self.shared_memory_object.target_y.value = 0
                self.shared_memory_object.target_z.value = 0
            case "DONE": # fully disable and kill
                #self.display(255, 0, 0)
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
            case "DRIVE": # transition: DRIVE -> NEXT
                if self.reached_xyz(self.gate_x, self.gate_y, self.gate_z):
                    self.next_state("NEXT")
            case "NEXT": # transition: NEXT -> DONE
                if self.reached_xyz(5, 0, 0):
                    self.next_state("DONE")
            case _: # do nothing if invalid state
                print(f"{self.name} INVALID STATE {self.state}")
    
    def display(self, r, g, b):
        """
        Sends color and text to display
        """
        print(f"RGB = ({r}, {g}, {b})")
        print(f"{self.name}:{self.state}")
        tgt_txt = f"DVL: \t\t x = {round(self.shared_memory_object.dvl_x.value,2)}\t y = {round(self.shared_memory_object.dvl_y.value,2)}\t z = {round(self.shared_memory_object.dvl_z.value,2)}"
        dvl_txt = f"TGT: \t\t x = {round(self.shared_memory_object.target_x.value,2)}\t y = {round(self.shared_memory_object.target_y.value,2)}\t z = {round(self.shared_memory_object.target_z.value,2)}"
        print(tgt_txt + "\n" + dvl_txt)
