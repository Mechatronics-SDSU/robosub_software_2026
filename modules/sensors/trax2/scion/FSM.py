from fsm                                    import FSM_Template
from socket_send                            import set_screen
import yaml, os, time
"""
    discord: @.kech
    github: @rsunderr

    FSM for testing purposes
    
"""

class IMU_FSM(FSM_Template):
    """
    IMU testing FSM
    """
    def __init__(self, shared_memory_object, run_list):
        """
        Test FSM constructor
        """
        # call parent constructor
        super().__init__(shared_memory_object, run_list)
        self.name = "TEST"

        # buffers
        self.x_buffer = 0.3#m
        self.y_buffer = 0.3#m
        self.z_buffer = 0.5#m

        # xyz
        self.imu_x = 0
        self.imu_y = 0
        self.imu_z = 0

        self.vel_x = 0
        self.vel_y = 0
        self.vel_z = 0

        self.t_prev = time.time()
        self.t = self.t_prev

        # TARGET VALUES-----------------------------------------------------------------------------------------------------------------------
        self.gate_x, self.gate_y, self.gate_z = (1000, 1000, 0.5)
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
            case "INIT": # initial state
                return
            case "DRIVE": 
                print("DRIVE")
                self.shared_memory_object.target_x.value = self.gate_x
                self.shared_memory_object.target_y.value = self.gate_y
                self.shared_memory_object.target_z.value = self.gate_z
            case "DONE": # fully disable and kill
                self.display(255, 0, 0)
                print("DONE")
                self.active = False
                self.stop()
            case _: # do nothing if invalid state
                print("IMU: INVALID NEXT STATE", self.state)
                return
        self.state = next

    def loop(self):
        """
        Loop function, mostly state transitions within conditionals
        """
        if not self.active: return # do nothing if not enabled

        # IMU ------------------------------------------------------------------------------------------------------
        self.t = time.time()
        #time.sleep(t%0.05) # make sure it only runs this every 0.05s
        if self.t - self.t_prev == 0.05: # if 0.05s has passed:
            # update velocity
            self.vel_x += self.shared_memory_object.imu_lin_acc.value[0]
            self.vel_y += self.shared_memory_object.imu_lin_acc.value[1]
            self.vel_z += self.shared_memory_object.imu_lin_acc.value[2]
            # update position
            self.imu_x += self.vel_x
            self.imu_y += self.vel_y
            self.imu_z += self.vel_z

            self.shared_memory_object.imu_x.value = self.imu_x
            self.shared_memory_object.imu_y.value = self.imu_y
            self.shared_memory_object.imu_z.value = self.imu_z
            # update previous t
            self.t_prev = self.t



        # update display
        self.display(255,0,0)

        # TRANSITIONS------------------------------------------------------------------------------------------------------
        match(self.state):
            case "INIT": pass
            case "DRIVE": # transition: DRIVE -> NEXT
                if abs(self.imu_x - self.gate_x) <= self.x_buffer and abs(self.imu_y - self.gate_y) <= self.y_buffer and abs(self.imu_z - self.gate_z) <= self.z_buffer:
                    self.next_state("DONE")
            case "DONE": pass
            case _: # do nothing if invalid state
                print("GATE: INVALID LOOP STATE", self.state)
