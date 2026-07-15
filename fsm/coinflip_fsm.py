from fsm.fsm                                    import FSM_Template
from modules.sensors.trax2.trax_fxns            import TRAX
from enum                                       import Enum
import yaml, os, subprocess
"""
    discord: @.kech
    github: @rsunderr

    FSM for coin flip
    
"""
class States(Enum):
    """
    Enumeration for FSM states
    """
    INIT    = "INIT"
    TURN    = "TURN"
    
    def __str__(self) -> str: # make elegant string
        return self.value

class CoinFlip_FSM(FSM_Template): # FIXME not finished
    """
    FSM for coin flip mode - aiming toward gate after being turned by diver
    """
    def __init__(self, shared_memory_object, run_list: list):
        """
        Coin Flip FSM constructor
        """
        # call parent constructor
        super().__init__(shared_memory_object, run_list)
        self.name: str      = "COIN_FLIP"
        self.state: States  = States.INIT  # initial state

        # TARGET VALUES-----------------------------------------------------------------------------------------------------------------------
        self.pool_yaw = self.yaw_buffer = self.depth = 0
        self.trax_yaw = 90 # default has a chance of being correct
        with open(os.path.expanduser("~/robosub_software_2026/objects.yaml"), 'r') as file: # read from yaml
            data = yaml.safe_load(file)
            # FIXME add coin flip section to yaml
            #self.yaw_buffer = data['objects']['coin_flip']['yaw_buff']
            #self.pool_yaw = data['objects']['coin_flip']['pool_yaw']
            # FIXME does PID code work with trax degree convention?

    def start(self) -> None:
        """
        Start FSM by enabling and starting processes
        """
        super().start()  # call parent start method

        # set initial state
        self.next_state(States.TURN)

    def next_state(self, next: States) -> None:
        """
        Change to next state
        """
        if not self.active or self.state == next: return # do nothing if not enabled or no state change
        # STATES-----------------------------------------------------------------------------------------------------------------------
        match(next):
            case States.INIT: return # initial state
            case States.TURN: # drop to correct depth and turn towards gate
                self.shared_memory_object.target_yaw.value = self.pool_yaw
                #self.shared_memory_object.target_z.value = self.depth
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
        self.display(150, 0, 150) # update display

        # TRANSITIONS------------------------------------------------------------------------------------------------------
        match(self.state):
            case States.INIT: return
            case States.TURN: # transition: TURN -> DONE
                if self.pool_yaw + self.yaw_buffer >= 360:
                    if abs(self.shared_memory_object.trax_yaw.value - self.pool_yaw + 360) <= self.yaw_buffer:
                        self.rezero_trax_yaw() # rezero trax yaw
                        self.suspend()
                elif abs(self.shared_memory_object.trax_yaw.value - self.pool_yaw) <= self.yaw_buffer:
                    self.rezero_trax_yaw() # rezero trax yaw
                    self.suspend()
            case _: # do nothing if invalid state
                print(f"{self.name} INVALID STATE {self.state}")
    
    def rezero_trax_yaw(self) -> None: # FIXME
        """
        Rezero trax yaw to make current heading 0 degrees
        """
        pass

