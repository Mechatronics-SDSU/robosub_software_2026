from utils.socket_send                      import set_screen
from fsm.fsm                                import FSM_Template
import yaml, os
"""
    discord: @.kech
    github: @rsunderr

    FSM for navigating through gate
    
"""

class Slalom_FSM(FSM_Template):
    """
    FSM for gate mode - driving through the gate
    """
    def __init__(self, shared_memory_object, run_list):
        """
        Gate FSM constructor
        """
        # call parent constructor
        super().__init__(shared_memory_object, run_list)
        self.name = "SLALOM"

        # TARGET VALUES-----------------------------------------------------------------------------------------------------------------------
        self.x_buffer = self.y_buffer = self.z_buffer = self.x1 = self.y1 = self.x2 = self.y2 = self.x3 = self.y3 = self.depth = (None, None, None, None, None, None, None)
        with open(os.path.expanduser("~/robosub_software_2025/objects.yaml"), 'r') as file: # read from yaml
            data = yaml.safe_load(file)
            course = data['course']
            self.x_buffer = data[course]['slalom']['x_buf']
            self.y_buffer = data[course]['slalom']['y_buf']
            self.z_buffer = data[course]['slalom']['z_buf']
            self.x1 = data[course]['slalom']['x1']
            self.y1 = data[course]['slalom']['y1']
            self.x2 = data[course]['slalom']['x2']
            self.y2 = data[course]['slalom']['y2']
            self.x3 = data[course]['slalom']['x3']
            self.y3 = data[course]['slalom']['y3']
            self.depth = data[course]['slalom']['z']

    def start(self):
        """
        Start FSM by enabling and starting processes
        """
        super().start()  # call parent start method

        # set initial state
        self.next_state("TO_START")

    def next_state(self, next):
        """
        Change to next state
        """
        if not self.active or self.state == next: return # do nothing if not enabled or no state change
        # STATES-----------------------------------------------------------------------------------------------------------------------
        match(next):
            case "INIT": return # initial state
            case "TO_START": # drive to start of slalom
                self.shared_memory_object.target_x.value = self.x1
                self.shared_memory_object.target_y.value = self.y1
                self.shared_memory_object.target_z.value = self.depth
            case "TO_MID": # drive to middle of slalom
                self.shared_memory_object.target_x.value = self.x2
                self.shared_memory_object.target_y.value = self.y2
            case "TO_END": # drive to end of slalom
                self.shared_memory_object.target_x.value = self.x3
                self.shared_memory_object.target_y.value = self.y3
            case "DONE": # disable but not kill (go to next mode)
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
        self.display(0, 255, 0) # update display

        # TRANSITIONS------------------------------------------------------------------------------------------------------
        match(self.state):
            case "INIT" | "DONE": return
            case "TO_START": # transition: TO_START -> TO_MID
                if self.reached_xyz(self.x1, self.y1, self.depth):
                    self.next_state("TO_MID")
            case "TO_MID": # transition: TO_MID -> TO_END
                if self.reached_xyz(self.x2, self.y2, self.depth):
                    self.next_state("TO_END")
            case "TO_END": # transition: TO_END -> DONE
                if self.reached_xyz(self.x3, self.y3, self.depth):
                    self.next_state("DONE")
            case _: # do nothing if invalid state
                print(f"{self.name} INVALID STATE {self.state}")
