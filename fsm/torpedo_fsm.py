import os
import time
import yaml

from utils.socket_send                      import set_screen
from fsm.fsm                                import FSM_Template
from enum                                   import Enum
from modules.vision.torpedo_helpers         import TorpedoLineup


"""
    FSM for navigating through torpedo
"""

class States(Enum):
    """
    Enumeration for FSM states
    """
    INIT            = "INIT"
    TO_TORPEDO      = "TO_TORPEDO"
    SEARCHING       = "SEARCHING"
    MOVING_TO_TARGET= "MOVING_TO_TARGET"
    VERIFY_LINEUP   = "VERIFY_LINEUP"
    SHOOTING        = "SHOOTING"
    DONE            = "DONE"

    def __str__(self) -> str: # make elegant string
        return self.value


class Torpedo_FSM(FSM_Template):
    """
    FSM for torpedo mode - finding target, lining up, and shooting torpedoes
    """
    def __init__(self, shared_memory_object, run_list: list):
        """
        Torpedo FSM constructor
        """
        # call parent constructor
        super().__init__(shared_memory_object, run_list)
        self.name: str      = "TORPEDO"
        self.state: States  = States.INIT  # initial state

        self.lineup = TorpedoLineup(shared_memory_object)

        # TARGET VALUES-----------------------------------------------------------------------------------------------------------------------
        self.x1 = self.y1 = self.depth = 0.0
        self.x_buffer = self.y_buffer = self.z_buffer = 0.10
        self.timeout = 8.0
        self.t_loop = 0.10

        # VISION / LINEUP VALUES--------------------------------------------------------------------------------------------------------------
        self.min_confidence = 70.0
        self.bbox_history_size = 5
        self.bbox_tolerance = 0.20
        self.x_lineup_tolerance = 0.05
        self.y_lineup_tolerance = 0.05
        self.distance_tolerance = 0.05
        self.distance_mode = "medium"
        self.desired_distance = self.lineup.select_target_distance(self.distance_mode)

        # Change these to match the ZED camera values used by the team.
        self.zed_x_fov = 90.0
        self.zed_y_fov = 60.0

        self.move_target_x = 0.0
        self.move_target_y = 0.0
        self.move_target_z = 0.0
        self.wait_time = 0.0

        try:
            with open(os.path.expanduser("~/robosub_software_2026/objects.yaml"), 'r') as file: # read from yaml
                data = yaml.safe_load(file)
                course = data['course']

                self.x_buffer = data[course]['torpedo'].get('x_buf', self.x_buffer)
                self.y_buffer = data[course]['torpedo'].get('y_buf', self.y_buffer)
                self.z_buffer = data[course]['torpedo'].get('z_buf', self.z_buffer)
                self.x1 = data[course]['torpedo'].get('x1', self.x1)
                self.y1 = data[course]['torpedo'].get('y1', self.y1)
                self.depth = data[course]['torpedo'].get('z', self.depth)

                self.timeout = data[course]['torpedo'].get('timeout', self.timeout)
                self.t_loop = data[course]['torpedo'].get('t_loop', self.t_loop)
                self.distance_mode = data[course]['torpedo'].get('distance_mode', self.distance_mode)
                self.desired_distance = self.lineup.select_target_distance(self.distance_mode)

                self.min_confidence = data[course]['torpedo'].get('min_confidence', self.min_confidence)
                self.bbox_history_size = data[course]['torpedo'].get('bbox_history_size', self.bbox_history_size)
                self.bbox_tolerance = data[course]['torpedo'].get('bbox_tolerance', self.bbox_tolerance)
                self.x_lineup_tolerance = data[course]['torpedo'].get('x_lineup_tolerance', self.x_lineup_tolerance)
                self.y_lineup_tolerance = data[course]['torpedo'].get('y_lineup_tolerance', self.y_lineup_tolerance)
                self.distance_tolerance = data[course]['torpedo'].get('distance_tolerance', self.distance_tolerance)
                self.zed_x_fov = data[course]['torpedo'].get('zed_x_fov', self.zed_x_fov)
                self.zed_y_fov = data[course]['torpedo'].get('zed_y_fov', self.zed_y_fov)

        except FileNotFoundError:
            print("ERROR: objects.yaml not found, using default torpedo values")
        except KeyError:
            print("ERROR: Invalid data format in objects.yaml, using default torpedo values")

    def start(self) -> None:
        """
        Start FSM by enabling and starting processes
        """
        super().start()  # call parent start method

        # set initial state
        self.next_state(States.TO_TORPEDO)

    def next_state(self, next: States) -> None:
        """
        Change to next state
        """
        if not self.active or self.state == next: return # do nothing if not enabled or no state change

        # STATES-----------------------------------------------------------------------------------------------------------------------
        match(next):
            case States.INIT:
                return # initial state

            case States.TO_TORPEDO: # approach guestimate coordinates
                self.shared_memory_object.target_x.value = self.x1
                self.shared_memory_object.target_y.value = self.y1
                self.shared_memory_object.target_z.value = self.depth
                self.wait_time = time.time()

            case States.SEARCHING: # run vision until target checks pass
                self.wait_time = time.time()

            case States.MOVING_TO_TARGET: # run pid to detected target location
                self.lineup.send_movement_command(
                    self.shared_memory_object,
                    self.move_target_x,
                    self.move_target_y,
                    self.move_target_z
                )
                self.wait_time = time.time()

            case States.VERIFY_LINEUP: # run vision again after movement
                self.wait_time = time.time()

            case States.SHOOTING: # shoot torpedoes
                self.lineup.fire_torpedo()
                time.sleep(1) # give some time for torpedoes to move away from sub

            case States.DONE:
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
            case States.INIT:
                return

            case States.TO_TORPEDO:
                if self.reached_xyz(self.x1, self.y1, self.depth):
                    self.next_state(States.SEARCHING)
                elif time.time() - self.wait_time > self.timeout:
                    self.next_state(States.SEARCHING)

            case States.SEARCHING:
                detection = self.get_checked_detection()

                if detection is not None:
                    self.set_movement_from_detection(detection)
                    self.next_state(States.MOVING_TO_TARGET)
                elif time.time() - self.wait_time > self.timeout:
                    # Could not find a good target. Keep this safe and stop torpedo mode.
                    self.next_state(States.DONE)

                time.sleep(self.t_loop)

            case States.MOVING_TO_TARGET:
                if self.reached_xyz(self.move_target_x, self.move_target_y, self.move_target_z):
                    self.next_state(States.VERIFY_LINEUP)
                elif time.time() - self.wait_time > self.timeout:
                    self.next_state(States.VERIFY_LINEUP)

            case States.VERIFY_LINEUP:
                detection = self.get_checked_detection()

                if detection is not None and self.lineup.lineup_passed(
                    detection,
                    self.desired_distance,
                    self.x_lineup_tolerance,
                    self.y_lineup_tolerance,
                    self.distance_tolerance
                ):
                    self.next_state(States.SHOOTING)

                elif detection is not None:
                    # Detection is good, but not lined up yet. Move again.
                    self.set_movement_from_detection(detection)
                    self.next_state(States.MOVING_TO_TARGET)

                elif time.time() - self.wait_time > self.timeout:
                    # Vision did not confirm lineup, so do not fire.
                    self.next_state(States.DONE)

                time.sleep(self.t_loop)

            case States.SHOOTING:
                self.next_state(States.DONE)

            case States.DONE:
                return

            case _: # do nothing if invalid state
                print(f"{self.name} INVALID STATE {self.state}")

    def get_checked_detection(self):
        """
        Calls vision, parses the dictionary, then checks confidence and box stability.
        """
        vision_dict = self.lineup.call_vision_pipeline()
        detection = self.lineup.parse_detection(vision_dict)

        if self.lineup.target_check_passed(
            detection,
            self.min_confidence,
            self.bbox_history_size,
            self.bbox_tolerance
        ):
            return detection

        return None

    def set_movement_from_detection(self, detection) -> None:
        """
        Converts the vision output into movement coordinates and stores them.
        """
        current_x = self.shared_memory_object.current_x.value
        current_y = self.shared_memory_object.current_y.value
        current_z = self.shared_memory_object.current_z.value

        self.move_target_x, self.move_target_y, self.move_target_z = self.lineup.calculate_target_coordinates(
            current_x,
            current_y,
            current_z,
            detection,
            self.desired_distance,
            self.zed_x_fov,
            self.zed_y_fov
        )
