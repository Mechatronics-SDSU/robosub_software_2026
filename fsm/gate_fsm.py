from utils.socket_send                              import set_screen
from fsm.fsm                                        import FSM_Template
from enum                                           import Enum
import time, yaml, os
"""
    discord: @.kech
    github: @rsunderr

    FSM for navigating through gate
"""
class States(Enum):
    """
    Enumeration for FSM states
    """
    INIT    = "INIT"
    DIVE    = "DIVE"
    TO_GATE = "TO_GATE"
    
    def __str__(self) -> str: # make elegant string
        return self.value

class Gate_FSM(FSM_Template):
    """
    FSM for gate mode - driving through the gate
    """
    def __init__(self, shared_memory_object, run_list: list):
        """
        Gate FSM constructor
        """
        # call parent constructor
        super().__init__(shared_memory_object, run_list)
        self.name = "GATE"
        self.state = States.INIT  # initial state

        # TARGET VALUES-----------------------------------------------------------------------------------------------------------------------
        self.gate_x = self.gate_y = self.gate_z = self.drop = self.t_drop = 0
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
                self.t_drop = data[course]['gate']['t_drop'] # initial drop duration
        except KeyError:
            print("ERROR: Invalid data format in objects.yaml, using all 0's")

    def start(self) -> None:
        """
        Start FSM by enabling and starting processes
        """
        super().start()  # call parent start method

        # set initial state
        self.next_state(States.DIVE)

    def next_state(self, next: States) -> None:
        """
        Change to next state
        """
        if not self.active or self.state == next: return # do nothing if not enabled or no state change
        # STATES-----------------------------------------------------------------------------------------------------------------------
        match(next):
            case States.INIT: return # initial state
            case States.DIVE:
                self.shared_memory_object.target_z.value = self.drop
                time.sleep(self.t_drop) # wait before switching to next state (to ramp up motors more gradually)
            case States.TO_GATE: # drive toward gate
                self.shared_memory_object.target_x.value = self.gate_x
                self.shared_memory_object.target_y.value = self.gate_y
                self.shared_memory_object.target_z.value = self.gate_z
            case _: # do nothing if invalid state
                print(f"{self.name} INVALID NEXT STATE {next}")
                return
        self.state = next
        print(f"{self.name}:{self.state}")

    def loop(self) -> None:
        """
        Loop function, mostly state transitions within conditionals
        """
        if not self.active: return # do nothing if not enabled
        self.display(0, 255, 0) # update display
        
        print(self.state)
        # TRANSITIONS------------------------------------------------------------------------------------------------------
        match(self.state):
            case States.INIT: return
            case States.DIVE: # transition: DIVE -> TO_GATE
                if self.shared_memory_object.dvl_z.value >= self.drop - self.z_buffer:
                    self.next_state(States.TO_GATE)
            case States.TO_GATE: # transition: TO_GATE -> DONE
                if self.reached_xyz(self.gate_x, self.gate_y, self.gate_z): # if it passes gate past at least 1m or reaches tgt
                    self.suspend()
            case _: # do nothing if invalid state
                print(f"{self.name} INVALID STATE {self.state}")

