from utils.socket_send                              import set_screen
from fsm.fsm                                        import FSM_Template
from enum                                           import Enum
import time, yaml, os
"""
    discord: @.kech
    github: @rsunderr

    FSM for navigating to and firing torpedoes
"""
P_DEBUG = False

class States(Enum):
    """
    Enumeration for FSM states
    """
    INIT    = "INIT"
    TO_TORP = "TO_TORP"
    FIRE    = "FIRE"
    
    def __str__(self) -> str: # make elegant string
        return self.value

class Torpedoes_FSM(FSM_Template):
    """
    FSM for gate mode - driving through the gate
    """
    def __init__(self, shared_memory_object, run_list: list):
        """
        Gate FSM constructor
        """
        # call parent constructor
        super().__init__(shared_memory_object, run_list)
        self.run_list       = run_list
        self.usb_object     = self.run_list[0]
        self.name: str      = "TORPEDOES"
        self.state: States  = States.INIT  # initial state

        # TARGET VALUES-----------------------------------------------------------------------------------------------------------------------
        self.torp_x = self.torp_y = self.torp_z = self.torp_yaw = 0
        try:
            with open(os.path.expanduser("~/robosub_software_2026/objects.yaml"), 'r') as file: # read from yaml
                data = yaml.safe_load(file)
                course = data['course']
                self.x_buffer = data[course]['torpedoes']['x_buf']
                self.y_buffer = data[course]['torpedoes']['y_buf']
                self.z_buffer = data[course]['torpedoes']['z_buf']
                self.torp_x = data[course]['torpedoes']['x']
                self.torp_y = data[course]['torpedoes']['y']
                self.torp_z = data[course]['torpedoes']['z']
                self.torp_yaw = data[course]['torpedoes']['yaw']
        except KeyError:
            print("ERROR: Invalid data format in objects.yaml, using all 0's")

    def start(self) -> None:
        """
        Start FSM by enabling and starting processes
        """
        super().start()  # call parent start method

        # set initial state
        self.next_state(States.TO_TORP)

    def next_state(self, next: States) -> None:
        """
        Change to next state
        """
        if not self.active or self.state == next: return # do nothing if not enabled or no state change
        # STATES-----------------------------------------------------------------------------------------------------------------------
        match(next):
            case States.INIT: return # initial state
            case States.TO_TORP: # drive toward gate
                self.shared_memory_object.target_x.value = self.torp_x
                self.shared_memory_object.target_y.value = self.torp_y
                self.shared_memory_object.target_z.value = self.torp_z
            case States.FIRE:
                self.shared_memory_object.target_yaw = self.torp_yaw
                time.sleep(0.5)
                self.usb_object.fire_torpedo(1)
                time.sleep(0.25)
                self.usb_object.fire_torpedo(2)
                time.sleep(0.25)
                self.shared_memory_object.target_yaw = 0
                
            case _: # do nothing if invalid state
                print(f"{self.name} INVALID NEXT STATE {next}")
                return
        self.state = next
        if P_DEBUG:
            print(f"{self.name}:{self.state}")

    def loop(self) -> None:
        """
        Loop function, mostly state transitions within conditionals
        """
        if not self.active: return # do nothing if not enabled
        self.display(0, 255, 0) # update display
        
        if P_DEBUG:
            print(self.state)
        # TRANSITIONS------------------------------------------------------------------------------------------------------
        match(self.state):
            case States.INIT: return
            case States.TO_TORP: # transition: TO_GATE -> DONE
                if self.reached_xyz(self.torp_x, self.torp_y, self.torp_z):
                    self.next_state(States.FIRE)
            case States.FIRE:
                    self.suspend()
            case _: # do nothing if invalid state
                print(f"{self.name} INVALID STATE {self.state}")

