from utils.socket_send                              import set_screen
from fsm.fsm                                        import FSM_Template
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

        # TARGET VALUES-----------------------------------------------------------------------------------------------------------------------
        self.x_buffer = self.y_buffer = self.z_buffer = self.gate_x = self.gate_y = self.gate_z = self.drop = 0
        try:
            with open(os.path.expanduser("~/robosub_software_2025/objects.yaml"), 'r') as file: # read from yaml
                data = yaml.safe_load(file)
                course = data['course']
                self.x_buffer = data[course]['gate']['x_buf']
                self.y_buffer = data[course]['gate']['y_buf']
                self.z_buffer = data[course]['gate']['z_buf']
                self.gate_x = data[course]['gate']['x']
                self.gate_y = data[course]['gate']['y']
                self.gate_z = data[course]['gate']['z']
                self.drop  = data[course]['gate']['drop'] # initial drop depth
        except FileNotFoundError:
            print("ERROR: objects.yaml file not found or attempting to read invalid data, using all 0's")

    def start(self):
        """
        Start FSM by enabling and starting processes
        """
        super().start()  # call parent start method

        # set initial state
        self.next_state("TO_GATE")

    def next_state(self, next):
        """
        Change to next state
        """
        if not self.active or self.state == next: return # do nothing if not enabled or no state change
        # STATES-----------------------------------------------------------------------------------------------------------------------
        match(next):
            case "INIT": return # initial state
            case "DIVE":
                self.shared_memory_object.target_z.value = self.drop
            case "TO_GATE": # drive toward gate
                self.shared_memory_object.target_x.value = self.gate_x
                self.shared_memory_object.target_y.value = self.gate_y
                self.shared_memory_object.target_z.value = self.gate_z
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
        
        print(self.state)
        # TRANSITIONS------------------------------------------------------------------------------------------------------
        match(self.state):
            case "INIT" | "DONE": return
            case "DIVE": # transition: DIVE -> TO_GATE
                if self.shared_memory_object.dvl_z.value >= self.drop - self.z_buffer:
                    self.next_state("TO_GATE")
            case "TO_GATE": # transition: TO_GATE -> DONE
                if self.reached_xyz(self.gate_x, self.gate_y, self.gate_z): # if it passes gate past at least 1m or reaches tgt
                    self.next_state("DONE")
            case _: # do nothing if invalid state
                print(f"{self.name} INVALID STATE {self.state}")
