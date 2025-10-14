from fsm.fsm                                        import FSM_Template
from utils.socket_send                              import set_screen
from enum                                           import Enum
import os, yaml, time
"""
    discord: @.kech
    github: @rsunderr

    FSM for returning through gate after octagon
    
"""
class States(Enum):
    """
    Enumeration for FSM states
    """
    INIT    = "INIT"
    DESCEND = "DESCEND"
    MP1     = "MP1"
    MP2     = "MP2"
    TO_GATE = "TO_GATE"
    HOME    = "HOME"
    RISE_END= "RISE_END"
    
    def __str__(self) -> str: # make elegant string
        return self.value
    
class Return_FSM(FSM_Template):
    """
    FSM for return mode - drives back to gate, drives to start, surfaces
    """
    def __init__(self, shared_memory_object, run_list):
        """
        Return FSM constructor
        """
        # call parent constructor
        super().__init__(shared_memory_object, run_list)
        self.name = "RETURN"
        self.state = States.INIT  # initial state

        #TARGET VALUES-----------------------------------------------------------------------------------------------------------------------
        self.gate_x = self.gate_y = self.x1 = self.y1 = self.x2 = self.y2 = self.drop = self.depth = 0
        try:
            with open(os.path.expanduser("~/robosub_software_2025/objects.yaml"), 'r') as file: # read from yaml
                data = yaml.safe_load(file)
                course = data['course']
                self.x_buffer = data[course]['return']['x_buf']
                self.y_buffer = data[course]['return']['y_buf']
                self.z_buffer = data[course]['return']['z_buf']
                self.drop   =   data[course]['return']['drop'] # drop depth to avoid octagon
                self.t_drop =   data[course]['return']['t_drop'] # initial drop duration
                self.depth  =   data[course]['return']['depth'] # swimming depth
                self.gate_x =   data[course]['gate']['x']
                self.gate_y =   data[course]['gate']['y']
                self.x1     =   data[course]['return']['x1']
                self.y1     =   data[course]['return']['y1']
                self.x2     =   data[course]['return']['x2']
                self.y2     =   data[course]['return']['y2']
        except KeyError:
            print("ERROR: Invalid data format in objects.yaml, using all 0's")

    def start(self) -> None:
        """
        Start FSM by enabling and starting processes
        """
        super().start()  # call parent start method

        # set initial state
        self.next_state(States.DESCEND)

    def next_state(self, next: States) -> None:
        """
        Change to next state
        """
        if not self.active or self.state == next: return # do nothing if not enabled or no state change
        match(next):
            case States.INIT: return # initial state
            case States.DESCEND: # initial descend in octagon to avoid smacking oct during gate shot
                self.shared_memory_object.target_z.value = self.drop
            case States.MP1: # move to midpoint 1 before gate
                self.shared_memory_object.target_z.value = self.depth
                self.shared_memory_object.target_x.value = self.x1
                self.shared_memory_object.target_y.value = self.y1
            case States.MP2: # move to midpoint 2 before gate
                self.shared_memory_object.target_x.value = self.x2
                self.shared_memory_object.target_y.value = self.y2
            case States.TO_GATE: # return to gate after octagon
                self.shared_memory_object.target_x.value = self.gate_x
                self.shared_memory_object.target_y.value = self.gate_y
            case States.HOME: # return to starting position
                self.shared_memory_object.target_x.value = 0
                self.shared_memory_object.target_y.value = 0
            case States.RISE_END: # surface at end of run
                self.shared_memory_object.target_z.value = 0
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
        self.display(0, 100, 100) # update display
        #TRANSITIONS-----------------------------------------------------------------------------------------------------------------------
        match(self.state):
            case States.INIT: return
            case States.DESCEND: # transition: DESCEND -> MP1
                if self.shared_memory_object.dvl_z.value >= self.drop - self.z_buffer / 2: # minimal buffer
                    self.next_state(States.MP1)
            case States.MP1: # transition MP1 -> MP2
                if self.reached_xy(self.x1, self.y1):
                    self.next_state(States.MP2)
            case States.MP2: # transition MP2 -> TO_GATE
                if self.reached_xy(self.x2, self.y2):
                    self.next_state(States.TO_GATE)
            case States.TO_GATE: # transition: TO_GATE -> HOME
                if self.reached_xy(self.gate_x, self.gate_y):
                    self.next_state(States.HOME)
            case States.HOME: # transition: HOME -> RISE_END
                if self.reached_xy(0, 0):
                    self.next_state(States.RISE_END)
            case States.RISE_END: # transition: RISE_END -> DONE
                if self.shared_memory_object.dvl_z.value <= self.z_buffer:
                    self.suspend()
            case _: # do nothing if invalid state
                print(f"{self.name} INVALID STATE {self.state}")
                return