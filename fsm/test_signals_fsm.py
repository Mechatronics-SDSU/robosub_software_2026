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
    INIT        = "INIT"
    DROPPER     = "DROPPER"
    TORPEDOES   = "TORPEDOES"
    CLAW        = "CLAW"
    
    
    def __str__(self) -> str: # make elegant string
        return self.value

class TestSignals_FSM(FSM_Template):
    """
    FSM for testing signals - driving through the gate
    """
    def __init__(self, shared_memory_object, run_list: list):
        """
        Test Signals FSM constructor
        """
        # call parent constructor
        super().__init__(shared_memory_object, run_list)
        self.run_list       = run_list
        self.name: str      = "TEST_SIGNALS"
        self.state: States  = States.INIT  # initial state

        # TARGET VALUES-----------------------------------------------------------------------------------------------------------------------
        self.gate_x = self.gate_y = self.gate_z = self.drop = self.t_drop = 0
        try:
            with open(os.path.expanduser("~/robosub_software_2026/objects.yaml"), 'r') as file: # read from yaml
                data = yaml.safe_load(file)
                course = data['course']
                self.x_buffer = data[course]['gate']['x_buf']
                self.y_buffer = data[course]['gate']['y_buf']
                self.z_buffer = data[course]['gate']['z_buf']
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
        self.next_state(States.DROPPER)

    def next_state(self, next: States) -> None:
        """
        Change to next state
        """
        if not self.active or self.state == next: return # do nothing if not enabled or no state change
        # STATES-----------------------------------------------------------------------------------------------------------------------
        match(next):
            case States.INIT: return # initial state
            case States.DROPPER: # spin dropper
                self.shared_memory_object.target_z.value = self.drop
                time.sleep(self.t_drop) # wait before switching to next state (to ramp up motors more gradually)
                self.run_list[0].spin_dropper(0.5) # spin dropper for specified duration
                time.sleep(2) # wait before switching to next state (to ramp up motors more gradually)

            case States.TORPEDOES: # drive toward gate
                self.run_list[0].fire_torpedo(1) # fire torpedo 1
                time.sleep(1) # wait before firing next torpedo
                self.run_list[0].fire_torpedo(2) # fire torpedo 2
                time.sleep(2) # wait before switching to next state

            case States.CLAW: # transition to claw state
                #self.run_list[0].lower_claw() # lower claw
                #self.run_list[0].grab_claw() # grab claw
                #self.run_list[0].raise_claw() # raise claw
                time.sleep(2) # wait before switching to next state
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
            case States.DROPPER: # transition: DROPPER -> TORPEDOES
                self.next_state(States.TORPEDOES)
            case States.TORPEDOES: # transition: TORPEDOES -> CLAW
                self.stop()
                #self.next_state(States.CLAW)
            case States.CLAW: # transition: CLAW -> DONE
                self.suspend()
            case _: # do nothing if invalid state
                print(f"{self.name} INVALID STATE {self.state}")

