from utils.socket_send                              import set_screen
from fsm.fsm                                        import FSM_Template
from enum                                           import Enum
import time, yaml, os
"""
    discord: @.kech
    github: @rsunderr

    FSM for navigating around target for prequalification
"""
class States(Enum):
    """
    Enumeration for FSM states
    """
    INIT        = "INIT"
    DIVE        = "DIVE"
    TO_TGT      = "TO_TGT"
    TGT_RIGHT   = "TGT_RIGHT"
    TGT_BACK    = "TGT_BACK"
    TGT_LEFT    = "TGT_LEFT"
    TGT_FRONT   = "TGT_FRONT"
    RETURN      = "RETURN"    
    
    def __str__(self) -> str: # make elegant string
        return self.value

class Prequal_FSM(FSM_Template):
    """
    FSM for prequal mode - driving around a target
    """
    def __init__(self, shared_memory_object, run_list: list):
        """
        Prequal FSM constructor
        """
        # call parent constructor
        super().__init__(shared_memory_object, run_list)
        self.name: str      = "PREQUAL"
        self.state: States  = States.INIT  # initial state

        # TARGET VALUES-----------------------------------------------------------------------------------------------------------------------
        self.tgt_x = self.tgt_y = self.depth = self.drop = self.t_drop = self.gap = 0
        try:
            with open(os.path.expanduser("~/robosub_software_2026/objects.yaml"), 'r') as file: # read from yaml
                data = yaml.safe_load(file)
                course = data['course']
                self.x_buffer = data[course]['tgt']['x_buf']
                self.y_buffer = data[course]['tgt']['y_buf']
                self.z_buffer = data[course]['tgt']['z_buf']
                self.tgt_x = data[course]['tgt']['x']
                self.tgt_y = data[course]['tgt']['y']
                self.depty = data[course]['tgt']['depth']
                self.gap = data[course]['tgt']['gap']
                self.drop  = data[course]['tgt']['drop'] # initial drop depth
                self.t_drop = data[course]['tgt']['t_drop'] # initial drop duration
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
            case States.TO_TGT: # drive toward target
                self.shared_memory_object.target_x.value = self.tgt_x - self.gap
                self.shared_memory_object.target_y.value = self.tgt_y
                self.shared_memory_object.target_z.value = self.depth
            case States.TGT_RIGHT: # drive to right of target
                self.shared_memory_object.target_x.value = self.tgt_x
                self.shared_memory_object.target_y.value = self.tgt_y - self.gap
            case States.TGT_BACK: # drive to back of target
                self.shared_memory_object.target_x.value = self.tgt_x + self.gap
                self.shared_memory_object.target_y.value = self.tgt_y
            case States.TGT_LEFT: # drive to left of target
                self.shared_memory_object.target_x.value = self.tgt_x
                self.shared_memory_object.target_y.value = self.tgt_y + self.gap
            case States.TGT_FRONT: # drive to front of target
                self.shared_memory_object.target_x.value = self.tgt_x - self.gap
                self.shared_memory_object.target_y.value = self.tgt_y
            case States.RETURN: # return to start
                self.shared_memory_object.target_x.value = 0
                self.shared_memory_object.target_y.value = 0
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
            case States.DIVE: # transition: DIVE -> TO_TGT
                self.next_state(States.TO_TGT)
            case States.TO_TGT: # transition: TO_TGT -> TO_RIGHT
                if self.reached_xyz(self.tgt_x - self.gap, self.tgt_y, self.depth):
                    self.next_state(States.TGT_RIGHT)
            case States.TGT_RIGHT: # transition: TGT_RIGHT -> TGT_BACK
                if self.reached_xy(self.tgt_x, self.tgt_y - self.gap):
                    self.next_state(States.TGT_BACK)
            case States.TGT_BACK: # transition: TGT_BACK -> TGT_LEFT
                if self.reached_xy(self.tgt_x + self.gap, self.tgt_y):
                    self.next_state(States.TGT_LEFT)
            case States.TGT_LEFT: # transition: TGT_LEFT -> TGT_FRONT
                if self.reached_xy(self.tgt_x, self.tgt_y + self.gap):
                    self.next_state(States.TGT_FRONT)
            case States.TGT_FRONT: # transition: TGT_FRONT -> RETURN
                if self.reached_xy(self.tgt_x - self.gap, self.tgt_y):
                    self.next_state(States.RETURN)
            case States.RETURN: # transition: RETURN -> off (floats to surface)
                if self.reached_xy(0, 0):
                    self.suspend()
            case _: # do nothing if invalid state
                print(f"{self.name} INVALID STATE {self.state}")

