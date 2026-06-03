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
    TO_DROPPER = "TO_DROPPER"
    RUN_DROPPER = "RUN_DROPPER"

    def __str__(self) -> str: # make elegant string
        return self.value

class Dropper_FSM(FSM_Template):
    """
    FSM for dropper mode - operating the dropper
    """
    def __init__(self, shared_memory_object, run_list: list):
        """
        Dropper FSM constructor
        """
        # call parent constructor
        super().__init__(shared_memory_object, run_list)
        self.name: str      = "DROPPER"
        self.state: States  = States.INIT  # initial state

        # TARGET VALUES-----------------------------------------------------------------------------------------------------------------------
        self.gate_x = self.gate_y = self.gate_z = self.drop = self.t_drop = 0
        try:
            with open(os.path.expanduser("~/robosub_software_2026/objects.yaml"), 'r') as file: # read from yaml
                data = yaml.safe_load(file)
                course = data['course']
                self.x_buffer = data[course]['dropper']['x_buf']
                self.y_buffer = data[course]['dropper']['y_buf']
                self.z_buffer = data[course]['dropper']['z_buf']
                self.dropper_x1 = data[course]['dropper']['x']
                self.dropper_y1 = data[course]['dropper']['y']
                self.dropper_z1 = data[course]['dropper']['z']

                self.t_dropper = data[course]['dropper']['t_dropper'] # time to run dropper for
        except KeyError:
            print("ERROR: Invalid data format in objects.yaml, using all 0's")

    def start(self) -> None:
        """
        Start FSM by enabling and starting processes
        """
        super().start()  # call parent start method

        # set initial state
        self.next_state(States.TO_DROPPER)

    def next_state(self, next: States) -> None:
        """
        Change to next state
        """
        if not self.active or self.state == next: return # do nothing if not enabled or no state change
        # STATES-----------------------------------------------------------------------------------------------------------------------
        match(next):
            case States.INIT: return # initial state
            case States.TO_DROPPER: # drive toward dropper
                self.shared_memory_object.target_x.value = self.dropper_x1
                self.shared_memory_object.target_y.value = self.dropper_y1
                self.shared_memory_object.target_z.value = self.dropper_z1
            case States.RUN_DROPPER: #POP_A_SQUAT
                # TODO: run dropper for t_dropper seconds
                pass
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
            case States.TO_DROPPER: # transition: DIVE -> TO_DROPPER
                if self.reached_xyz(self.dropper_x1, self.dropper_y1, self.dropper_z1):
                    self.next_state(States.RUN_DROPPER)
            case States.RUN_DROPPER: # transition: RUN_DROPPER -> DONE
                time.sleep(self.t_dropper)
                self.suspend()
            case _: # do nothing if invalid state
                print(f"{self.name} INVALID STATE {self.state}")

