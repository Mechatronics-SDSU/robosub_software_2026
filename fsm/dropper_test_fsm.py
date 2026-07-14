import os
import time
import yaml

from fsm.fsm                                import FSM_Template
from modules.logger.logger                  import Logger
from modules.dropper.dropper_helpers        import DropperHelpers
from enum                                   import Enum


"""
    Bench test FSM for the dropper — camera + dropper actuation only, no motors.
    Flow: SEARCH_FOR_BIN -> VERIFY_BIN_TARGET -> DROP_MARKER -> (repeat for 2nd marker) -> COMPLETE
    No shared_memory target writes, no navigation, no alignment.
"""

class States(Enum):
    INIT             = "INIT"
    SEARCH_FOR_BIN   = "SEARCH_FOR_BIN"
    VERIFY_BIN_TARGET = "VERIFY_BIN_TARGET"
    DROP_MARKER      = "DROP_MARKER"
    COMPLETE         = "COMPLETE"
    FAIL             = "FAIL"

    def __str__(self) -> str:
        return self.value


class DropperTest_FSM(FSM_Template):
    """
    Dropper bench test FSM.
    Runs the downward camera, detects the role bin, waits for a stable
    detection, fires the dropper, then searches for the second bin.
    No motor commands are sent at any point.

    signal_wrapper: real SignalWrapper to actuate hardware, or None to print
    placeholders (same as the real Dropper_FSM).
    """
    def __init__(self, shared_memory_object, run_list: list, signal_wrapper=None):
        super().__init__(shared_memory_object, run_list)
        self.name: str     = "DROPPER_TEST"
        self.state: States = States.INIT
        self.logger = Logger()

        self.timeout = 8.0
        self.t_loop  = 0.10

        self.marker_num  = 1
        self.max_markers = 2
        self.current_target = None
        self.wait_time = 0.0

        role         = "survey_and_repair"
        model_weights = "models/best.pt"

        hw_path = os.path.expanduser("~/robosub_software_2026/config/hardware.yaml")
        try:
            with open(hw_path) as f:
                hw = yaml.safe_load(f)
                d = hw.get('dropper', {})
                model_weights = d.get('model_weights', model_weights)
        except FileNotFoundError:
            self.logger.error(f"{self.name} ERROR: config/hardware.yaml not found, using defaults")
        except KeyError:
            self.logger.error(f"{self.name} ERROR: Invalid format in config/hardware.yaml, using defaults")

        try:
            with open(os.path.expanduser("~/robosub_software_2026/objects.yaml"), 'r') as file:
                data = yaml.safe_load(file)
                course = data['course']
                role = data.get('role', role)
                self.timeout = data[course]['dropper'].get('timeout', self.timeout)
                self.t_loop  = data[course]['dropper'].get('t_loop',   self.t_loop)
        except FileNotFoundError:
            self.logger.error(f"{self.name} ERROR: objects.yaml not found, using defaults")
        except KeyError:
            self.logger.error(f"{self.name} ERROR: Invalid data format in objects.yaml, using defaults")

        self.helper    = DropperHelpers(shared_memory_object, signal_wrapper, weights_path=model_weights)
        self.bin_label = self.helper.get_bin_label(role)

    def start(self) -> None:
        super().start()
        self.next_state(States.SEARCH_FOR_BIN)

    def next_state(self, next: States) -> None:
        if not self.active or self.state == next: return

        match(next):
            case States.INIT:
                return

            case States.SEARCH_FOR_BIN:
                self.helper.reset_tracking()
                self.wait_time = time.time()

            case States.VERIFY_BIN_TARGET:
                self.wait_time = time.time()

            case States.DROP_MARKER:
                self.helper.release_marker()

            case States.COMPLETE:
                self.suspend()

            case States.FAIL:
                self.logger.warning(f"{self.name} FAILED to complete marker {self.marker_num}")
                self.suspend()

            case _:
                self.logger.error(f"{self.name} INVALID NEXT STATE {next}")
                return

        old_state = self.state
        self.state = next
        self.logger.info(f"State changed: {old_state} -> {self.state}")

    def loop(self) -> None:
        if not self.active: return
        self.display(255, 100, 0)

        match(self.state):
            case States.INIT:
                return

            case States.SEARCH_FOR_BIN:
                detections = self.helper.get_target_detections()
                target = self.helper.choose_bin_target(detections, self.bin_label)

                if target is not None:
                    self.current_target = target
                    self.next_state(States.VERIFY_BIN_TARGET)
                elif time.time() - self.wait_time > self.timeout:
                    self.next_state(States.FAIL)

                time.sleep(self.t_loop)

            case States.VERIFY_BIN_TARGET:
                detections = self.helper.get_target_detections()
                target = self.helper.choose_bin_target(detections, self.bin_label)

                if target is not None:
                    self.current_target = target
                    if self.helper.check_target_stable(target):
                        self.next_state(States.DROP_MARKER)
                elif time.time() - self.wait_time > self.timeout:
                    self.next_state(States.FAIL)

                time.sleep(self.t_loop)

            case States.DROP_MARKER:
                if self.marker_num < self.max_markers:
                    self.marker_num += 1
                    self.next_state(States.SEARCH_FOR_BIN)
                else:
                    self.next_state(States.COMPLETE)

            case States.COMPLETE:
                return

            case States.FAIL:
                return

            case _:
                self.logger.error(f"{self.name} INVALID STATE {self.state}")
