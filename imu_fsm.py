from fsm                                    import FSM_Template
from socket_send                            import set_screen
import yaml, os, time
"""
    discord: @.kech
    github: @rsunderr

    FSM for testing purposes
    
"""

DISPLAY_ACTIVE = False

class IMU_FSM(FSM_Template):
    """
    IMU testing FSM
    """
    def __init__(self, shared_memory_object, run_list, vis_start):
        """
        Test FSM constructor
        """
        # call parent constructor
        super().__init__(shared_memory_object, run_list, vis_start)
        self.name = "TEST"

        # buffers
        self.z_buffer = 0.2#m

        self.yaw_buffer = .1

        # TARGET VALUES-----------------------------------------------------------------------------------------------------------------------
        self.gate_x, self.gate_y, self.gate_z = (1000, 1000, 0.5)
        with open(os.path.expanduser("~/robosub_software_2025/objects.yaml"), 'r') as file: # read from yaml
            data = yaml.safe_load(file)
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
            case "DRIVE": 
                print("IMU: DRIVE")
                self.shared_memory_object.target_x.value = 0
                self.shared_memory_object.target_y.value = 0
                self.shared_memory_object.target_z.value = 1
            case "DONE": # fully disable and kill
                if DISPLAY_ACTIVE:
                    self.display(255, 0, 0)
                print("IMU: DONE")
                self.active = False
                self.complete = True
                self.stop()
            case _: # do nothing if invalid state
                print("IMU: INVALID NEXT STATE:", self.state)
                return
        self.state = next

    def loop(self):
        """
        Loop function, mostly state transitions within conditionals
        """
        if not self.active: return # do nothing if not enabled


        # update display
        if DISPLAY_ACTIVE:
            self.display(255,0,0)

        # TRANSITIONS------------------------------------------------------------------------------------------------------
        match(self.state):
            case "INIT": 
                return
            case "DRIVE": # transition: DRIVE -> NEXT
                # print(self.shared_memory_object.depth.value)
                if abs(self.shared_memory_object.depth.value - self.gate_z) <= self.z_buffer and abs(self.shared_memory_object.imu_yaw.value - self.shared_memory_object.target_yaw.value) <= self.yaw_buffer:
                    self.next_state("DONE")
            case "DONE": pass
            case _: # do nothing if invalid state
                print("GATE: INVALID LOOP STATE", self.state)

