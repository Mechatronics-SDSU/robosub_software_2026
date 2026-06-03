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
    TO_GRABBER_PICKUP = "TO_GRABBER_PICKUP"
    GRABBER_PICKUP = "GRABBER_PICKUP"
    TO_GRABBER_DROP = "TO_GRABBER_DROP"
    GRABBER_DROP = "GRABBER_DROP"

    def __str__(self) -> str: # make elegant string
        return self.value

class Grabber_FSM(FSM_Template):
    """
    FSM for grabber mode - operating the grabber
    """
    def __init__(self, shared_memory_object, run_list: list):
        """
        Grabber FSM constructor
        """
        # call parent constructor
        super().__init__(shared_memory_object, run_list)
        self.name: str      = "GRABBER"
        self.state: States  = States.INIT  # initial state

        # TARGET VALUES-----------------------------------------------------------------------------------------------------------------------
        self.gate_x = self.gate_y = self.gate_z = self.drop = self.t_drop = 0
        try:
            with open(os.path.expanduser("~/robosub_software_2026/objects.yaml"), 'r') as file: # read from yaml
                data = yaml.safe_load(file)
                course = data['course']
                self.x_buffer = data[course]['grabber']['x_buf']
                self.y_buffer = data[course]['grabber']['y_buf']
                self.z_buffer = data[course]['grabber']['z_buf']
                self.grabber_x1 = data[course]['grabber']['x']
                self.grabber_y1 = data[course]['grabber']['y']
                self.grabber_z1 = data[course]['grabber']['z']
                self.grabber_x2 = data[course]['grabber']['x']
                self.grabber_y2 = data[course]['grabber']['y']
                self.grabber_z2 = data[course]['grabber']['z']

                self.t_grabber = data[course]['grabber']['t_grabber'] # time to run grabber for
        except KeyError:
            print("ERROR: Invalid data format in objects.yaml, using all 0's")

    def start(self) -> None:
        """
        Start FSM by enabling and starting processes
        """
        super().start()  # call parent start method

        # set initial state
        self.next_state(States.TO_GRABBER_PICKUP)

    def next_state(self, next: States) -> None:
        """
        Change to next state
        """
        if not self.active or self.state == next: return # do nothing if not enabled or no state change
        # STATES-----------------------------------------------------------------------------------------------------------------------
        match(next):
            case States.INIT: return # initial state
            case States.TO_GRABBER_PICKUP: # drive toward grabber
                self.shared_memory_object.target_x.value = self.grabber_x1
                self.shared_memory_object.target_y.value = self.grabber_y1
                self.shared_memory_object.target_z.value = self.grabber_z1
            case States.GRABBER_PICKUP: 
                # TODO: run grabber for t_grabber seconds
                pass
            case States.TO_GRABBER_DROP: 
                self.shared_memory_object.target_x.value = self.grabber_x2
                self.shared_memory_object.target_y.value = self.grabber_y2
                self.shared_memory_object.target_z.value = self.grabber_z2
                pass
            case States.GRABBER_DROP: 
                # TODO: run grabber for t_grabber seconds
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
            case States.TO_GRABBER_PICKUP: # transition: DIVE -> TO_GRABBER
                if self.reached_xyz(self.grabber_x1, self.grabber_y1, self.grabber_z1):
                    self.next_state(States.GRABBER_PICKUP)
            case States.GRABBER_PICKUP: # transition: GRABBER_PICKUP -> TO_GRABBER_DROP
                time.sleep(self.t_grabber)
                self.next_state(States.TO_GRABBER_DROP)
            case States.TO_GRABBER_DROP: # transition: TO_GRABBER_DROP -> GRABBER_DROP
                if self.reached_xyz(self.grabber_x2, self.grabber_y2, self.grabber_z2):
                    self.next_state(States.GRABBER_DROP)
            case States.GRABBER_DROP: # transition: GRABBER_DROP -> DONE
                time.sleep(self.t_grabber)
                self.suspend()
            case _: # do nothing if invalid state
                print(f"{self.name} INVALID STATE {self.state}")

