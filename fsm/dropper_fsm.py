import os
import time
import yaml

from fsm.fsm                                import FSM_Template
from modules.logger.logger                  import Logger
from modules.dropper.dropper_helpers        import DropperHelpers
from modules.vision.target_box_helpers      import FINAL_SETTLE_TIME_S
from enum                                   import Enum


"""
    FSM for navigating through Recon Bins (dropper task)
"""

class States(Enum):
    """
    Enumeration for FSM states
    """
    INIT                 = "INIT"
    MOVE_TO_PIPELINE     = "MOVE_TO_PIPELINE"
    SEARCH_FOR_BIN       = "SEARCH_FOR_BIN"
    VERIFY_BIN_TARGET    = "VERIFY_BIN_TARGET"
    ALIGN_TO_BIN         = "ALIGN_TO_BIN"
    VERIFY_DROP_POSITION = "VERIFY_DROP_POSITION"
    DROP_MARKER          = "DROP_MARKER"
    COMPLETE             = "COMPLETE"
    FAIL                 = "FAIL"

    def __str__(self) -> str: # make elegant string
        return self.value


class Dropper_FSM(FSM_Template):
    """
    FSM for dropper mode (Recon Bins) - finding the role's bins, lining up
    the dropper (not just the camera) using the downward camera + DVL world
    position, and dropping markers.

    The suggested state list for this task also included separate
    SEARCH_FOR_SECOND_BIN / VERIFY_SECOND_BIN_TARGET / ALIGN_TO_SECOND_BIN /
    VERIFY_SECOND_DROP_POSITION / DROP_SECOND_MARKER states. Those are
    combined into a single set of states reused for both markers with a
    marker_num counter instead, the same pattern already used by
    fsm/torpedo_fsm.py's SHOOTING -> SEARCHING loop for its second torpedo.
    Rejecting candidate bins near completed_bins (see DropperHelpers) is what
    makes SEARCH_FOR_BIN naturally find the *other* bin on the second pass.
    """
    def __init__(self, shared_memory_object, run_list: list, signal_wrapper=None):
        """
        Dropper FSM constructor

        signal_wrapper: a real SignalWrapper (modules/signals/SignalWrapper.py)
        built from the shared USB_Transmitter, or None to use safe print
        placeholders instead of actuating real hardware (e.g. test mode).
        """
        # call parent constructor
        super().__init__(shared_memory_object, run_list)
        self.name: str      = "DROPPER"
        self.state: States  = States.INIT  # initial state
        self.logger = Logger()

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
        # camera looks straight down, so this is how high above the bin to hover before dropping
        # FIXME: 0.3m is a guess, confirm this is the right hover height for the real marker/dropper mechanism
        self.desired_height = 0.3 # meters
        # FIXME: waiting on the route plan to know which bin height applies to
        # which bin. Using one placeholder target_depth for now, update per-bin
        # once the route plan is decided.
        self.target_depth = 1.0 # meters, placeholder
        self.x_lineup_tolerance = 0.05 # meters (metric back-projection, not normalized image fraction)
        self.y_lineup_tolerance = 0.05 # meters

        self.same_bin_radius = 0.5
        self.max_object_yaml_error = 1.0
        self.final_settle_time = FINAL_SETTLE_TIME_S
        self.verify_entered_time = 0.0
        self.wait_time = 0.0

        # FIXME: role is a static value read from objects.yaml's top-level `role:` key,
        # meaning someone has to edit that file by hand before each run to match the
        # competition-assigned role. Say if you'd rather this come from somewhere else
        # (CLI flag, a file, another FSM's output) instead.
        role = "survey_and_repair"
        dropper_offset_x = dropper_offset_y = 0.0
        model_weights = "models/best.pt"

        # hardware settings live in hardware.yaml (camera-independent, deployment-specific)
        hw_path = os.path.expanduser("~/robosub_software_2026/config/hardware.yaml")
        try:
            with open(hw_path) as f:
                hw = yaml.safe_load(f)
                d = hw.get('dropper', {})
                model_weights    = d.get('model_weights', model_weights)
                dropper_offset_x = d.get('offset_x', dropper_offset_x)
                dropper_offset_y = d.get('offset_y', dropper_offset_y)
        except FileNotFoundError:
            self.logger.error(f"{self.name} ERROR: config/hardware.yaml not found, using default dropper hardware values")
        except KeyError:
            self.logger.error(f"{self.name} ERROR: Invalid format in config/hardware.yaml, using default dropper hardware values")

        try:
            with open(os.path.expanduser("~/robosub_software_2026/objects.yaml"), 'r') as file: # read from yaml
                data = yaml.safe_load(file)
                course = data['course']
                # role is a single top-level switch for the whole run, not duplicated per-course/per-task
                role = data.get('role', role)

                self.x_buffer = data[course]['dropper'].get('x_buf', self.x_buffer)
                self.y_buffer = data[course]['dropper'].get('y_buf', self.y_buffer)
                self.z_buffer = data[course]['dropper'].get('z_buf', self.z_buffer)
                self.x1 = data[course]['dropper'].get('x1', self.x1)
                self.y1 = data[course]['dropper'].get('y1', self.y1)
                self.depth = data[course]['dropper'].get('z', self.depth)

                self.timeout = data[course]['dropper'].get('timeout', self.timeout)
                self.t_loop = data[course]['dropper'].get('t_loop', self.t_loop)
                self.desired_height = data[course]['dropper'].get('desired_height', self.desired_height)
                self.target_depth = data[course]['dropper'].get('target_depth', self.target_depth)
                self.x_lineup_tolerance = data[course]['dropper'].get('x_lineup_tolerance', self.x_lineup_tolerance)
                self.y_lineup_tolerance = data[course]['dropper'].get('y_lineup_tolerance', self.y_lineup_tolerance)

                self.same_bin_radius = data[course]['dropper'].get('same_bin_radius', self.same_bin_radius)
                self.max_object_yaml_error = data[course]['dropper'].get('max_object_yaml_error', self.max_object_yaml_error)
                self.final_settle_time = data[course]['dropper'].get('final_settle_time', self.final_settle_time)

        except FileNotFoundError:
            self.logger.error(f"{self.name} ERROR: objects.yaml not found, using default dropper values")
        except KeyError:
            self.logger.error(f"{self.name} ERROR: Invalid data format in objects.yaml, using default dropper values")

        self.role = role # "survey_and_repair" or "search_and_rescue", set once for the whole run in objects.yaml
        self.helper = DropperHelpers(shared_memory_object, signal_wrapper, weights_path=model_weights,
                                      dropper_offset_body=(dropper_offset_x, dropper_offset_y), same_bin_radius=self.same_bin_radius)
        self.bin_label = self.helper.get_bin_label(self.role)

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
                self.helper.reset_tracking()
                self.wait_time = time.time()

            case States.VERIFY_BIN_TARGET: # keep checking the bin is a stable target
                self.wait_time = time.time()

            case States.ALIGN_TO_BIN: # start driving the dropper toward the bin using the downward camera
                self.wait_time = time.time()

            case States.VERIFY_DROP_POSITION: # hold position, re-check the bin with a stricter pass before dropping
                self.wait_time = time.time()
                self.verify_entered_time = time.time()

            case States.DROP_MARKER: # release one marker, release_marker() handles its own timing and saves completed_bins
                self.helper.release_marker()

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

        assumed_bin_world = (self.x1, self.y1)

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
                result = self.helper.align_step(self.bin_label, self.target_depth, self.desired_height,
                                                 self.x_lineup_tolerance, self.y_lineup_tolerance,
                                                 assumed_bin_world, self.max_object_yaml_error)
                self.current_target = result["target"]

                if result["lost"] or result["rejected"]:
                    self.next_state(States.SEARCH_FOR_BIN)
                elif result["centered"] and result["dwell_ok"]:
                    self.next_state(States.VERIFY_DROP_POSITION)
                elif time.time() - self.wait_time > self.timeout:
                    self.next_state(States.FAIL)

                time.sleep(self.t_loop)

            case States.VERIFY_DROP_POSITION: # transition: VERIFY_DROP_POSITION -> DROP_MARKER
                result = self.helper.align_step(self.bin_label, self.target_depth, self.desired_height,
                                                 self.x_lineup_tolerance, self.y_lineup_tolerance,
                                                 assumed_bin_world, self.max_object_yaml_error)
                self.current_target = result["target"]

                if result["lost"] or result["rejected"]:
                    self.next_state(States.SEARCH_FOR_BIN)
                elif result["centered"] and result["dwell_ok"]:
                    settled = time.time() - self.verify_entered_time >= self.final_settle_time
                    verified = result["target"] is not None and self.helper.check_target_verified(result["target"])
                    if settled and verified:
                        self.next_state(States.DROP_MARKER)
                elif time.time() - self.wait_time > self.timeout:
                    self.next_state(States.FAIL)

                time.sleep(self.t_loop)

            case States.DROP_MARKER: # transition: DROP_MARKER -> SEARCH_FOR_BIN (2nd marker) or COMPLETE
                if self.marker_num < self.max_markers:
                    self.marker_num += 1
                    self.next_state(States.SEARCH_FOR_BIN)
                else:
                    self.next_state(States.COMPLETE)

            case States.COMPLETE:
                return

            case States.FAIL:
                return

            case _: # do nothing if invalid state
                self.logger.error(f"{self.name} INVALID STATE {self.state}")
