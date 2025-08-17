from fsm                                    import FSM_Template
from socket_send                            import set_screen
from modules.motors.ScionMotorWrapper import MotorWrapper
import time
import yaml
import os
"""
    discord: @.kech
    github: @rsunderr

    FSM for testing purposes
    
"""

DISPLAY = False

class ForwardSpinFSM(FSM_Template):
    """
    FSM testing sandbox
    """
    def __init__(self, shared_memory_object, run_list, vis_start):
        """
        Test FSM constructor
        """
        # call parent constructor
        super().__init__(shared_memory_object, run_list, vis_start)
        self.name = "FDSP"

        # buffers
        self.x_buffer = 10#m
        self.y_buffer = 10#m
        self.z_buffer = 0.5#m
        self.yaw_buffer = 0#m

        self.forward_start_time = 0
        self.spin_start_time = 0
        self.motor_wrapper = MotorWrapper(shared_memory_object)

        # TARGET VALUES-----------------------------------------------------------------------------------------------------------------------
        self.gate_x, self.gate_y, self.gate_z = (None, None, None)
        with open(os.path.expanduser("~/robosub_software_2025/objects.yaml"), 'r') as file: # read from yaml
            data = yaml.safe_load(file)
            self.forward_time = data['objects']['fdsm']['forward_time']
            self.spin_time = data['objects']['fdsm']['spin_time']
            self.initial_depth = data['objects']['fdsm']['initial_depth']
            self.depth = data['objects']['fdsm']['depth']

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
            case "INIT": # initial state
                return
            case "DRIVE": 
                print("FOR: DRIVE")
                self.forward_start_time = time.time()
                self.shared_memory_object.target_z.value = self.initial_depth
                self.shared_memory_object.target_x.value = 10
            case "SPIN": 
                print("FOR: SPIN")
                self.spin_start_time = time.time()
                self.shared_memory_object.target_z.value = self.depth
                self.shared_memory_object.target_yaw.value = 180
                self.shared_memory_object.target_x.value = 0
            case "DONE": # fully disable and kill
                self.shared_memory_object.target_x.value = 0
                print("FOR: DONE")
                self.active = False
                self.stop()
            case _: # do nothing if invalid state
                print("FDSP: INVALID NEXT STATE:", self.state)
                self.motor_wrapper.stop()
                return
        self.state = next

    def loop(self):
        """
        Loop function, mostly state transitions within conditionals
        """
        if not self.active: return # do nothing if not enabled

        # TRANSITIONS------------------------------------------------------------------------------------------------------
        match(self.state):
            case "INIT":
                return
            case "DRIVE": # transition: DRIVE -> NEXT
                if time.time() - self.forward_start_time > self.forward_time:
                    self.state = "SPIN"
            case "SPIN":
                if time.time() - self.spin_start_time > self.spin_start_time:
                    self.next_state("DONE")
            case "DONE": pass
            case _: # do nothing if invalid state
                print("FDSP: INVALID LOOP STATE:", self.state)
