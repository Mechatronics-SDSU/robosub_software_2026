import os
import time
import yaml

from fsm.fsm                                import FSM_Template
from modules.logger.logger                  import Logger
from modules.vision.dropper_helpers         import DropperHelpers
from modules.vision.target_box_helpers      import convert_target_to_movement
from enum                                   import Enum


"""
    FSM for navigating through dropper
"""

class States(Enum):
    """
    Enumeration for FSM states
    """
    INIT                            = "INIT"
    MOVE_TO_PIPELINE                = "MOVE_TO_PIPELINE"
    SEARCH_FOR_BIN                  = "SEARCH_FOR_BIN"
    VERIFY_BIN_TARGET               = "VERIFY_BIN_TARGET"
    ALIGN_TO_BIN                    = "ALIGN_TO_BIN"
    VERIFY_DROP_POSITION            = "VERIFY_DROP_POSITION"
    DROP_MARKER                     = "DROP_MARKER"
    INTERACT_WITH_MAGNETIC_DETECTOR = "INTERACT_WITH_MAGNETIC_DETECTOR"
    COMPLETE                        = "COMPLETE"
    FAIL                            = "FAIL"

    def __str__(self) -> str: # make elegant string
        return self.value


class Dropper_FSM(FSM_Template):
    """
    FSM for dropper mode - finding the role's bins, lining up, and dropping markers

    NOTE: the suggested state list for this task also included separate
    SEARCH_FOR_SECOND_BIN / VERIFY_SECOND_BIN_TARGET / ALIGN_TO_SECOND_BIN /
    VERIFY_SECOND_DROP_POSITION / DROP_SECOND_MARKER states. Those were combined
    into a single set of states reused for both markers with a marker_num
    counter instead, the same pattern already used by fsm/torpedo_fsm.py's
    SHOOTING -> SEARCHING loop for its second torpedo.
    """
    def __init__(self, shared_memory_object, run_list: list, role: str = "survey_and_repair"):
        """
        Dropper FSM constructor
        """
        # call parent constructor
        super().__init__(shared_memory_object, run_list)
        self.name: str      = "DROPPER"
        self.state: States  = States.INIT  # initial state
        self.logger = Logger()

        self.helper = DropperHelpers(shared_memory_object)

        # ROLE SETTINGS-----------------------------------------------------------------------------------------------------------------------
        self.role = role # "survey_and_repair" or "search_and_rescue"
        self.bin_label = self.helper.get_bin_label(self.role)

        # TARGET VALUES-----------------------------------------------------------------------------------------------------------------------
        self.x1 = self.y1 = self.depth = 0.0
        self.x_buffer = self.y_buffer = self.z_buffer = 0.10
        self.timeout = 8.0
        self.t_loop = 0.10

        # MARKER COUNT--------------------------------------------------------------------------------------------------------------------------
        self.marker_num = 1 # which marker we are currently lining up (1 or 2)
        self.max_markers = 2
        self.current_target = None # bin detection picked out of the vision target boxes

        # VISION / LINEUP VALUES--------------------------------------------------------------------------------------------------------------
        self.x_lineup_tolerance = 0.05
        self.y_lineup_tolerance = 0.05

        self.wait_time = 0.0

        try:
            with open(os.path.expanduser("~/robosub_software_2026/objects.yaml"), 'r') as file: # read from yaml
                data = yaml.safe_load(file)
                course = data['course']

                self.x_buffer = data[course]['dropper'].get('x_buf', self.x_buffer)
                self.y_buffer = data[course]['dropper'].get('y_buf', self.y_buffer)
                self.z_buffer = data[course]['dropper'].get('z_buf', self.z_buffer)
                self.x1 = data[course]['dropper'].get('x1', self.x1)
                self.y1 = data[course]['dropper'].get('y1', self.y1)
                self.depth = data[course]['dropper'].get('z', self.depth)

                self.timeout = data[course]['dropper'].get('timeout', self.timeout)
                self.t_loop = data[course]['dropper'].get('t_loop', self.t_loop)
                self.x_lineup_tolerance = data[course]['dropper'].get('x_lineup_tolerance', self.x_lineup_tolerance)
                self.y_lineup_tolerance = data[course]['dropper'].get('y_lineup_tolerance', self.y_lineup_tolerance)

        except FileNotFoundError:
            self.logger.error(f"{self.name} ERROR: objects.yaml not found, using default dropper values")
        except KeyError:
            self.logger.error(f"{self.name} ERROR: Invalid data format in objects.yaml, using default dropper values")

    def start(self) -> None:
        """
        Start FSM by enabling and starting processes
        """
        super().start()  # call parent start method

        # set initial state
        self.next_state(States.MOVE_TO_PIPELINE)

    def next_state(self, next: States) -> None:
        """
        Change to next state
        """
        if not self.active or self.state == next: return # do nothing if not enabled or no state change

        # STATES-----------------------------------------------------------------------------------------------------------------------
        match(next):
            case States.INIT:
                return # initial state

            case States.MOVE_TO_PIPELINE: # approach guestimate coordinates
                self.shared_memory_object.target_x.value = self.x1
                self.shared_memory_object.target_y.value = self.y1
                self.shared_memory_object.target_z.value = self.depth
                self.wait_time = time.time()

            case States.SEARCH_FOR_BIN: # look for the role's bin
                self.helper.reset_detection_history()
                self.wait_time = time.time()

            case States.VERIFY_BIN_TARGET: # keep checking the bin is a stable target
                self.wait_time = time.time()

            case States.ALIGN_TO_BIN: # drive toward the bin
                move_x, move_y, move_z = convert_target_to_movement(
                    self.current_target,
                    self.shared_memory_object.dvl_x.value,
                    self.shared_memory_object.dvl_y.value,
                    self.shared_memory_object.dvl_z.value
                )
                self.shared_memory_object.target_x.value = move_x
                self.shared_memory_object.target_y.value = move_y
                self.shared_memory_object.target_z.value = move_z
                self.wait_time = time.time()

            case States.VERIFY_DROP_POSITION: # re-check the bin position before dropping
                self.wait_time = time.time()

            case States.DROP_MARKER: # drop one marker
                self.helper.activate_dropper()
                self.helper.drop_marker()
                time.sleep(1) # give some time for the marker to leave the sub

            case States.INTERACT_WITH_MAGNETIC_DETECTOR: # interact with the magnetic detector
                self.helper.interact_with_magnetic_detector()

            case States.COMPLETE:
                self.suspend() # finish dropper mode, ready for next mode

            case States.FAIL:
                self.logger.warning(f"{self.name} FAILED to complete marker {self.marker_num}")
                self.suspend() # give up, ready for next mode

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
        self.display(255, 150, 0) # update display

        # TRANSITIONS------------------------------------------------------------------------------------------------------
        match(self.state):
            case States.INIT:
                return

            case States.MOVE_TO_PIPELINE: # transition: MOVE_TO_PIPELINE -> SEARCH_FOR_BIN
                if self.reached_xyz(self.x1, self.y1, self.depth):
                    self.next_state(States.SEARCH_FOR_BIN)
                elif time.time() - self.wait_time > self.timeout:
                    self.next_state(States.SEARCH_FOR_BIN)

            case States.SEARCH_FOR_BIN: # transition: SEARCH_FOR_BIN -> VERIFY_BIN_TARGET
                detections = self.helper.get_target_detections()
                target = self.helper.choose_bin_target(detections, self.bin_label)

                if target is not None:
                    self.current_target = target
                    self.next_state(States.VERIFY_BIN_TARGET)
                elif time.time() - self.wait_time > self.timeout:
                    self.next_state(States.FAIL)

                time.sleep(self.t_loop)

            case States.VERIFY_BIN_TARGET: # transition: VERIFY_BIN_TARGET -> ALIGN_TO_BIN
                detections = self.helper.get_target_detections()
                target = self.helper.choose_bin_target(detections, self.bin_label)

                if target is not None:
                    self.current_target = target
                    if self.helper.check_target_stable(target):
                        self.next_state(States.ALIGN_TO_BIN)
                elif time.time() - self.wait_time > self.timeout:
                    self.next_state(States.FAIL)

                time.sleep(self.t_loop)

            case States.ALIGN_TO_BIN: # transition: ALIGN_TO_BIN -> VERIFY_DROP_POSITION
                if self.reached_xyz(
                    self.shared_memory_object.target_x.value,
                    self.shared_memory_object.target_y.value,
                    self.shared_memory_object.target_z.value
                ):
                    self.next_state(States.VERIFY_DROP_POSITION)
                elif time.time() - self.wait_time > self.timeout:
                    self.next_state(States.VERIFY_DROP_POSITION)

            case States.VERIFY_DROP_POSITION: # transition: VERIFY_DROP_POSITION -> DROP_MARKER
                if self.helper.is_target_centered(self.current_target, self.x_lineup_tolerance, self.y_lineup_tolerance):
                    self.next_state(States.DROP_MARKER)
                elif time.time() - self.wait_time > self.timeout:
                    self.next_state(States.FAIL)

                time.sleep(self.t_loop)

            case States.DROP_MARKER: # transition: DROP_MARKER -> SEARCH_FOR_BIN (2nd marker) or INTERACT_WITH_MAGNETIC_DETECTOR
                if self.marker_num < self.max_markers:
                    self.marker_num += 1
                    self.next_state(States.SEARCH_FOR_BIN)
                else:
                    self.next_state(States.INTERACT_WITH_MAGNETIC_DETECTOR)

            case States.INTERACT_WITH_MAGNETIC_DETECTOR: # transition: INTERACT_WITH_MAGNETIC_DETECTOR -> COMPLETE
                self.next_state(States.COMPLETE)

            case States.COMPLETE:
                return

            case States.FAIL:
                return

            case _: # do nothing if invalid state
                self.logger.error(f"{self.name} INVALID STATE {self.state}")
