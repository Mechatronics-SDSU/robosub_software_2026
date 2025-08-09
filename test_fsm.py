from fsm                                    import FSM_Template
from socket_send                            import set_screen
import yaml
import os
"""
    discord: @.kech
    github: @rsunderr

    FSM for navigating through gate
    
"""

class Test_FSM(FSM_Template):
    """
    FSM testing sandbox
    """
    def __init__(self, shared_memory_object, run_list):
        """
        Test FSM constructor
        """
        # call parent constructor
        super().__init__(shared_memory_object, run_list)

        # initial state (INIT, DRIVE, NEXT/DONE)
        self.state = "INIT"

        # buffers
        self.x_buffer = 0.3#m
        self.y_buffer = 0.3#m
        self.z_buffer = 0.5#m

        # TARGET VALUES-----------------------------------------------------------------------------------------------------------------------
        self.gate_x, self.gate_y, self.gate_z = (None, None, None)
        with open(os.path.expanduser("~/robosub_software_2025/objects.yaml"), 'r') as file: # read from yaml
            data = yaml.safe_load(file)
            self.gate_x = data['objects']['gate']['x']
            self.gate_y = data['objects']['gate']['y']
            self.gate_z = data['objects']['gate']['z']

    def start(self):
        """
        Start FSM
        """
        super().start()  # call parent start method

        # set initial state
        self.next_state("DRIVE")

    def next_state(self, next):
        """
        Change to next state
        """
        if not self.active or self.state == next: return # do nothing if not enabled or no state change
        # STATES-----------------------------------------------------------------------------------------------------------------------
        match(next):
            case "INIT": pass # initial state
            case "DRIVE": # drive toward gate
                print("DRIVE")
                self.shared_memory_object.target_x.value = self.gate_x
                self.shared_memory_object.target_y.value = self.gate_y
                self.shared_memory_object.target_z.value = self.gate_z
            case "NEXT": # disable but not kill (go to next mode)
                print("NEXT")
                self.active = False
                return
            case "DONE": # fully disable and kill
                print("DONE")
                self.stop()
                return
            case _: # do nothing if invalid state
                print("GATE: INVALID NEXT STATE", self.state)
                return
        self.state = next

    def loop(self):
        """
        Loop function, mostly state transitions within conditionals
        """
        if not self.active: return # do nothing if not enabled
        # display
        set_screen(
            (0, 255, 0),
            f"GATE:{self.state}",
            f"Target: | DVL: x={self.shared_memory_object.dvl_x.value}, y={self.shared_memory_object.dvl_y.value}, z={self.shared_memory_object.dvl_z.value}, gatex={self.gate_x}, gatey={self.gate_y}, gatez={self.gate_z}"
        )

        # TRANSITIONS------------------------------------------------------------------------------------------------------
        match(self.state):
            case "INIT": pass
            case "DRIVE": # transition: DRIVE -> NEXT
                if self.reached_xyz(self.gate_x, self.gate_y, self.gate_z):
                    self.next_state("NEXT")
            case "NEXT": pass
            case "DONE": pass
            case _: # do nothing if invalid state
                print("GATE: INVALID LOOP STATE", self.state)
                return
    
    def reached_xyz(self, x, y, z):
        """
        Returns true if near a location (requires x,y,z buffer and dvl to work)
        """
        if abs(self.shared_memory_object.dvl_x.value - x) <= self.x_buffer and abs(self.shared_memory_object.dvl_y.value - y) <= self.y_buffer and abs(self.shared_memory_object.dvl_z.value - z) <= self.z_buffer:
            return True
        # else
        return False
