import os
import time
import yaml

from fsm.fsm                                import FSM_Template
from modules.logger.logger                  import Logger
from modules.torpedo.torpedo_helpers        import TorpedoLineup
from enum                                   import Enum


"""
    FSM for navigating through torpedo
"""

class States(Enum):
    """
    Enumeration for FSM states
    """
    INIT             = "INIT"
    TO_TORPEDO       = "TO_TORPEDO"
    SEARCHING        = "SEARCHING"
    MOVING_TO_TARGET = "MOVING_TO_TARGET"
    VERIFY_LINEUP    = "VERIFY_LINEUP"
    SHOOTING         = "SHOOTING"
    DONE             = "DONE"

    def __str__(self) -> str: # make elegant string
        return self.value


class Torpedo_FSM(FSM_Template):
    """
    FSM for torpedo mode - finding a hole in the board, lining up, and shooting torpedoes
    """
    def __init__(self, shared_memory_object, run_list: list, signal_wrapper=None):
        """
        Torpedo FSM constructor

        signal_wrapper: a real SignalWrapper (modules/signals/SignalWrapper.py)
        built from the shared USB_Transmitter, or None to use safe print
        placeholders instead of actuating real hardware (e.g. test mode).
        """
        # call parent constructor
        super().__init__(shared_memory_object, run_list)
        self.name: str      = "TORPEDO"
        self.state: States  = States.INIT  # initial state
        self.logger = Logger()

        self.lineup = TorpedoLineup(shared_memory_object, signal_wrapper)

        # TARGET VALUES-----------------------------------------------------------------------------------------------------------------------
        self.x1 = self.y1 = self.depth = 0.0
        self.x_buffer = self.y_buffer = self.z_buffer = 0.10
        self.timeout = 8.0
        self.t_loop = 0.10

        # TORPEDO COUNT-------------------------------------------------------------------------------------------------------------------------
        self.torpedo_num = 1       # which torpedo we are currently lining up (1 or 2)
        self.max_torpedoes = 2
        self.current_target = None # hole picked out of the circle data dictionary

        # VISION / LINEUP VALUES--------------------------------------------------------------------------------------------------------------
        self.x_lineup_tolerance = 0.05
        self.y_lineup_tolerance = 0.05
        self.min_radius = 0.0 # optional minimum hole radius before firing, 0 = off
        self.distance_mode = "medium"
        self.desired_distance = self.lineup.select_target_distance(self.distance_mode)

        # Change these to match the ZED camera values used by the team.
        self.zed_x_fov = 90.0
        self.zed_y_fov = 60.0

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

                self.x_lineup_tolerance = data[course]['torpedo'].get('x_lineup_tolerance', self.x_lineup_tolerance)
                self.y_lineup_tolerance = data[course]['torpedo'].get('y_lineup_tolerance', self.y_lineup_tolerance)
                self.min_radius = data[course]['torpedo'].get('min_radius', self.min_radius)
                self.zed_x_fov = data[course]['torpedo'].get('zed_x_fov', self.zed_x_fov)
                self.zed_y_fov = data[course]['torpedo'].get('zed_y_fov', self.zed_y_fov)

        except FileNotFoundError:
            self.logger.error(f"{self.name} ERROR: objects.yaml not found, using default torpedo values")
        except KeyError:
            self.logger.error(f"{self.name} ERROR: Invalid data format in objects.yaml, using default torpedo values")

    def start(self) -> None:
        """
        Start FSM by enabling and starting processes
        """
        super().start()  # call parent start method

        # set initial state
        self.next_state(States.TO_TORPEDO)

    def choose_target(self, circle_data: dict):
        """
        Picks which hole to aim at based on which torpedo we're currently lining up
        """
        if self.torpedo_num == 1:
            return self.lineup.choose_first_torpedo_target(circle_data)
        return self.lineup.choose_second_torpedo_target(circle_data)

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

            case States.SEARCHING: # look for a hole to aim at
                self.wait_time = time.time()

            case States.MOVING_TO_TARGET: # drive toward the chosen hole
                self.lineup.move_to_torpedo_target(
                    self.shared_memory_object,
                    self.shared_memory_object.dvl_x.value,
                    self.shared_memory_object.dvl_y.value,
                    self.shared_memory_object.dvl_z.value,
                    self.current_target,
                    self.desired_distance,
                    self.zed_x_fov,
                    self.zed_y_fov
                )
                self.wait_time = time.time()

            case States.VERIFY_LINEUP: # re-check the hole position before firing
                self.wait_time = time.time()

            case States.SHOOTING: # shoot one torpedo, fire_torpedo() handles its own timing/re-arm
                self.lineup.fire_torpedo(self.torpedo_num)

            case States.DONE:
                self.suspend() # finish torpedo mode, ready for next mode

            case _: # do nothing if invalid state
                self.logger.error(f"{self.name} INVALID NEXT STATE {next}")
                return

        old_state = self.state
        self.state = next
        self.logger.info(f"State changed: {old_state} -> {self.state}")

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

            case States.TO_TORPEDO: # transition: TO_TORPEDO -> SEARCHING
                if self.reached_xyz(self.x1, self.y1, self.depth):
                    self.next_state(States.SEARCHING)
                elif time.time() - self.wait_time > self.timeout:
                    self.next_state(States.SEARCHING)

            case States.SEARCHING: # transition: SEARCHING -> MOVING_TO_TARGET
                circle_data = self.lineup.get_torpedo_circle_data()
                target = self.choose_target(circle_data)

                if target is not None:
                    self.current_target = target
                    self.next_state(States.MOVING_TO_TARGET)
                elif time.time() - self.wait_time > self.timeout:
                    # no usable hole found in time, do not fire
                    self.logger.warning(f"{self.name} no usable hole found, skipping torpedo {self.torpedo_num}")
                    self.next_state(States.DONE)

                time.sleep(self.t_loop)

            case States.MOVING_TO_TARGET: # transition: MOVING_TO_TARGET -> VERIFY_LINEUP
                if self.reached_xyz(
                    self.shared_memory_object.target_x.value,
                    self.shared_memory_object.target_y.value,
                    self.shared_memory_object.target_z.value
                ):
                    self.next_state(States.VERIFY_LINEUP)
                elif time.time() - self.wait_time > self.timeout:
                    self.next_state(States.VERIFY_LINEUP)

            case States.VERIFY_LINEUP: # transition: VERIFY_LINEUP -> SHOOTING (or back to MOVING_TO_TARGET)
                circle_data = self.lineup.get_torpedo_circle_data()
                target = self.choose_target(circle_data)

                if target is not None and self.lineup.verify_fire_position(
                    target, self.x_lineup_tolerance, self.y_lineup_tolerance, self.min_radius
                ):
                    self.current_target = target
                    self.next_state(States.SHOOTING)

                elif target is not None:
                    # still see a hole, but not lined up yet, move again
                    self.current_target = target
                    self.next_state(States.MOVING_TO_TARGET)

                elif time.time() - self.wait_time > self.timeout:
                    # lost the hole, do not fire
                    self.logger.warning(f"{self.name} lost the hole before firing torpedo {self.torpedo_num}")
                    self.next_state(States.DONE)

                time.sleep(self.t_loop)

            case States.SHOOTING: # transition: SHOOTING -> SEARCHING (2nd torpedo) or DONE
                if self.torpedo_num < self.max_torpedoes:
                    self.torpedo_num += 1
                    self.next_state(States.SEARCHING)
                else:
                    self.next_state(States.DONE)

            case States.DONE:
                return

            case _: # do nothing if invalid state
                self.logger.error(f"{self.name} INVALID STATE {self.state}")
