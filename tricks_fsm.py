from fsm                                    import FSM_Template
from socket_send                            import set_screen
import yaml, os, time
from modules.vision.vision_main             import VisionDetection
from modules.motors.MotorWrapper            import MotorWrapper

"""
    discord: @.kech
    github: @rsunderr

    FSM for gate tricks
    
"""

DISPLAY_ACTIVE = False

class Tricks_FSM(FSM_Template):
    """
    Gate tricks FSM
    """
    def __init__(self, shared_memory_object, run_list, vis_start):
        """
        Tricks FSM constructor
        """
        # call parent constructor
        super().__init__(shared_memory_object, run_list)
        for item in run_list:
            if isinstance (item, VisionDetection) and not vis_start:
                run_list.remove(item)

        self.name = "TRICKS"

        # buffers
        self.z_buffer   = 0.3#m
        self.yaw_buffer = 30#deg
        self.t_start    = 0
        self.t_max      = 0
        self.spin_time  = 0

        self.z_buffer   = .2

        self.motor_object = MotorWrapper(self.shared_memory_object)

        # TARGET VALUES-----------------------------------------------------------------------------------------------------------------------
        self.t_drive, self.t2, self.depth = (0, 0, 0)
        with open(os.path.expanduser("~/ryan_scion_tricks/robosub_software_2025/objects.yaml"), 'r') as file: # read from yaml
            data = yaml.safe_load(file)
            self.depth  = data['tricks']['depth']
            self.t_drive= data['tricks']['t_drive']
            self.t_max  = data['tricks']['t_max']

    def start(self):
        """
        Start FSM
        """
        super().start()  # call parent start method

        while self.shared_memory_object.zed_status.value == 0:
            pass

        # set initial state
        self.next_state("DRIVE")

    def next_state(self, next):
        """
        Change to next state
        """
        if not self.active or self.state == next: return # do nothing if not enabled or no state change
        self.state = next
        print(f"{self.name}:{self.state}") # print state
        # STATES-----------------------------------------------------------------------------------------------------------------------
        match(next):
            case "DRIVE":
                self.shared_memory_object.target_x.value = 1#1 # go forward
                self.shared_memory_object.target_y.value = 0
                # self.motor_object.move_down(50)
                self.shared_memory_object.target_z.value = self.depth
                time.sleep(self.t_drive) # continue forward for a duration
                self.next_state("SPIN") # transition DRIVE -> SPIN
            # spin 360 deg 2x
            case "SPIN":
                self.t_start = time.time()
                self.process_objects[0].terminate()
                self.shared_memory_object.target_x.value = 0
                # self.shared_memory_object.target_yaw.value = -2
                os.system("cansend can0 010#AA00AA00660066000")

                time.sleep(self.t_max)
                self.next_state("DONE")
            case "DONE": # fully disable and kill
                self.stop()
                if DISPLAY_ACTIVE: self.display(255, 0, 0)
            case _: # do nothing if invalid state
                print(f"{self.name} INVALID NEXT STATE {next}")
                return
        
    def loop(self):
        """
        Loop function, mostly state transitions within conditionals
        """
        if time.time() >= self.t_start + self.t_max: 
            self.next_state("DONE") # stop after exceeding max time
        if not self.active: return # do nothing if not enabled

        # update display
        if DISPLAY_ACTIVE: self.display(255,255,0)