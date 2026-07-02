from utils.socket_send                      import set_screen
from fsm.fsm                                import FSM_Template
from enum                                   import Enum
from modules.vision.tor_pedo                import lineup

import yaml, os, time


"""
    discord: @.kech
    github: @rsunderr

    FSM for navigating through torpedo
    
"""

class States(Enum):
    """
    Enumeration for FSM states
    """
    INIT    = "INIT"
    TO_START= "TO_START"
    TO_MID  = "TO_MID"
    TO_END  = "TO_END"
    
    def __str__(self) -> str: # make elegant string
        return self.value

class Torpedo_FSM(FSM_Template):
    """
    FSM for torpedo mode - Lining up and shooting torpedoes
    """
    def __init__(self, shared_memory_object, run_list: list):
        """
        Torpedo FSM constructor
        """
        # call parent constructor
        super().__init__(shared_memory_object, run_list)
        self.name: str      = "TORPEDO"
        self.state: States  = States.INIT  # initial state
        self.wait_time: time = time.time() # time tracking variable
        self.lineup = lineup(shared_memory_object)

        # TARGET VALUES-----------------------------------------------------------------------------------------------------------------------
        self.x1 = self.y1 = self.x2 = self.y2 = self.x3 = self.y3 = self.depth = 0
        try:
            with open(os.path.expanduser("~/robosub_software_2026/objects.yaml"), 'r') as file: # read from yaml
                data = yaml.safe_load(file)
                course = data['course']
                self.x_buffer = data[course]['torpedo']['x_buf']
                self.y_buffer = data[course]['torpedo']['y_buf']
                self.z_buffer = data[course]['torpedo']['z_buf']
                self.x1 = data[course]['torpedo']['x1']
                self.y1 = data[course]['torpedo']['y1']
                self.x2 = data[course]['torpedo']['x2']
                self.y2 = data[course]['torpedo']['y2']
                self.x3 = data[course]['torpedo']['x3']
                self.y3 = data[course]['torpedo']['y3']
                self.depth = data[course]['torpedo']['z']

                self.timeout = data[course]['torpedo']['timeout'] #FIXME how long before looking for torpedoes gives up
                self.t_loop = data[course]['torpedo']['t_loop'] # FIXME how long to wait before updating torpedo coordinates in loop
                self.desired_distance = data[course]['torpedo']['desired_distance'] # FIXME how far away do we want to be facing the torpedo target

        except KeyError:
            print("ERROR: Invalid data format in objects.yaml, using all 0's")

    def start(self) -> None:
        """
        Start FSM by enabling and starting processes
        """
        super().start()  # call parent start method

        # set initial state
        self.next_state(States.TO_START)

    def next_state(self, next: States) -> None:
        """
        Change to next state
        """
        if not self.active or self.state == next: return # do nothing if not enabled or no state change
        # STATES-----------------------------------------------------------------------------------------------------------------------
        match(next):
            case States.INIT: return # initial state
            case States.TO_TORPEDO: # approach guestimate coordinates
                self.shared_memory_object.target_x.value = self.x1
                self.shared_memory_object.target_y.value = self.y1
                self.shared_memory_object.target_z.value = self.z1
            case States.AT_TORPEDO: # turn on camera and wait for vision logic
                #activate zed camera
                # Zed logic runs here and return the x, y and depth of target.
                # find the target, then transition to lining up once we have above a certain confidence
                # FIXME I WILL ALSO NEED A TIMEOUT!!
                pass
            case States.LINING_UP: #run pid to line up with target
                self.wait_time = time.time() # take now
            case States.SHOOTING: # shoot torpedos
                # FIXME run shooting function
                time.sleep(1) # give some time for torpedoes to move away from sub
                self.suspend() # finish torpedo mode, ready for next mode
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

        # TRANSITIONS------------------------------------------------------------------------------------------------------
        match(self.state):
            case States.INIT: return
            case States.TO_TORPEDO:
                if self.reached_xyz(self.x1, self.y1, self.depth):
                    self.next_state(States.TO_MID)
            case States.AT_TORPEDO: 
                # call vision logic to check if target found, if found transition to lining up, else keep looking
                self.next_state(States.LINING_UP)
            case States.LINING_UP: # transition: TO_END -> DONE
                self.update_xy_lineup(self.shared_memory_object.target_x, self.x1, ZED_X, ZED_DISTANCE, ZED_XFOV)
                self.update_xy_lineup(self.shared_memory_object.target_y, self.y1, ZED_Y, ZED_DISTANCE, ZED_YFOV)
                self.update_z_lineup(self.shared_memory_object.target_z, self.z1, ZED_DISTANCE, self.desired_distance)
                time.sleep(self.t_loop)
                # check if reached coordinate
                if self.reached_xyz(self.x3, self.y3, self.depth) or time.time() - self.wait_time > self.timeout:
                    self.next_state(States.SHOOTING)
            case _: # do nothing if invalid state
                print(f"{self.name} INVALID STATE {self.state}")

    def update_xy_pids(self, obj, self_coord, zed_coord, zed_dist, fov) -> None:
        """
        This function returns updated coordinates based on vision
        """
        obj.value = self_coord + self.lineup.vision_to_coordinates(zed_coord, zed_dist, fov)

    def update_depth_pids(self, obj, self_z_cord: float, vision_distance: float, desired_distance: float) -> None:
        """
        This function returns updated z coordinate based on vision
        """
        obj.value = self_z_cord + self.lineup.z_vision_lineup(vision_distance, desired_distance)