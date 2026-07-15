import os
import time
import yaml

from fsm.fsm                                import FSM_Template
from modules.logger.logger                  import Logger
from modules.grabber.grabber_helpers        import GrabberHelpers
from enum                                   import Enum


"""
    Bench test FSM for the grabber — camera + claw actuation only, no motors.
    Flow: SEARCH_FOR_ITEM -> VERIFY_ITEM_TARGET -> GRAB_ITEM ->
          SEARCH_FOR_BASKET -> VERIFY_BASKET_TARGET -> RELEASE_ITEM ->
          (repeat for 2nd item) -> COMPLETE
    No shared_memory target writes, no navigation, no alignment.
"""

class States(Enum):
    INIT                  = "INIT"
    SEARCH_FOR_ITEM       = "SEARCH_FOR_ITEM"
    VERIFY_ITEM_TARGET    = "VERIFY_ITEM_TARGET"
    GRAB_ITEM             = "GRAB_ITEM"
    SEARCH_FOR_BASKET     = "SEARCH_FOR_BASKET"
    VERIFY_BASKET_TARGET  = "VERIFY_BASKET_TARGET"
    RELEASE_ITEM          = "RELEASE_ITEM"
    COMPLETE              = "COMPLETE"
    FAIL                  = "FAIL"

    def __str__(self) -> str:
        return self.value


class GrabberTest_FSM(FSM_Template):
    """
    Grabber bench test FSM.
    Runs the downward camera, detects the role item, waits for a stable
    detection, closes and raises the claw, then detects the role basket,
    lowers and opens the claw to release. No motor commands are sent at any point.

    signal_wrapper: real SignalWrapper to actuate hardware, or None to print
    placeholders (same as the real Grabber_FSM).
    """
    def __init__(self, shared_memory_object, run_list: list, signal_wrapper=None):
        super().__init__(shared_memory_object, run_list)
        self.name: str     = "GRABBER_TEST"
        self.state: States = States.INIT
        self.logger = Logger()

        self.timeout = 8.0
        self.t_loop  = 0.10

        self.item_num    = 1
        self.max_items   = 2
        self.current_target = None
        self.wait_time = 0.0

        role          = "survey_and_repair"
        model_weights = "models/best.pt"

        hw_path = os.path.expanduser("~/robosub_software_2026/config/hardware.yaml")
        try:
            with open(hw_path) as f:
                hw = yaml.safe_load(f)
                g = hw.get('grabber', {})
                model_weights = g.get('model_weights', model_weights)
        except FileNotFoundError:
            self.logger.error(f"{self.name} ERROR: config/hardware.yaml not found, using defaults")
        except KeyError:
            self.logger.error(f"{self.name} ERROR: Invalid format in config/hardware.yaml, using defaults")

        try:
            with open(os.path.expanduser("~/robosub_software_2026/objects.yaml"), 'r') as file:
                data = yaml.safe_load(file)
                course = data['course']
                role = data.get('role', role)
                self.timeout = data[course]['grabber'].get('timeout', self.timeout)
                self.t_loop  = data[course]['grabber'].get('t_loop',   self.t_loop)
        except FileNotFoundError:
            self.logger.error(f"{self.name} ERROR: objects.yaml not found, using defaults")
        except KeyError:
            self.logger.error(f"{self.name} ERROR: Invalid data format in objects.yaml, using defaults")

        self.helper        = GrabberHelpers(shared_memory_object, signal_wrapper, weights_path=model_weights)
        self.role_items    = self.helper.get_role_items(role)
        self.remaining_items = list(self.role_items)
        self.basket_label  = self.helper.get_basket_label(role)

    def start(self) -> None:
        super().start()
        self.next_state(States.SEARCH_FOR_ITEM)

    def next_state(self, next: States) -> None:
        if not self.active or self.state == next: return

        match(next):
            case States.INIT:
                return

            case States.SEARCH_FOR_ITEM:
                self.helper.reset_tracking()
                self.wait_time = time.time()

            case States.VERIFY_ITEM_TARGET:
                self.wait_time = time.time()

            case States.GRAB_ITEM:
                self.helper.close_claw()
                self.helper.grab_object()

            case States.SEARCH_FOR_BASKET:
                self.helper.reset_tracking()
                self.wait_time = time.time()

            case States.VERIFY_BASKET_TARGET:
                self.wait_time = time.time()

            case States.RELEASE_ITEM:
                self.helper.release_object()
                self.helper.open_claw()

            case States.COMPLETE:
                self.suspend()

            case States.FAIL:
                self.logger.warning(f"{self.name} FAILED on item {self.item_num}, restarting search")
                self.item_num = 1
                self.remaining_items = list(self.role_items)

            case _:
                self.logger.error(f"{self.name} INVALID NEXT STATE {next}")
                return

        old_state = self.state
        self.state = next
        self.logger.info(f"State changed: {old_state} -> {self.state}")

    def loop(self) -> None:
        if not self.active: return
        self.display(0, 200, 100)

        match(self.state):
            case States.INIT:
                return

            case States.SEARCH_FOR_ITEM:
                detections = self.helper.get_target_detections()
                target = self.helper.choose_item_target(detections, self.remaining_items)

                if target is not None:
                    self.current_target = target
                    self.next_state(States.VERIFY_ITEM_TARGET)
                elif time.time() - self.wait_time > self.timeout:
                    self.next_state(States.FAIL)

                time.sleep(self.t_loop)

            case States.VERIFY_ITEM_TARGET:
                detections = self.helper.get_target_detections()
                target = self.helper.choose_item_target(detections, self.remaining_items)

                if target is not None:
                    self.current_target = target
                    if self.helper.check_target_stable(target):
                        self.next_state(States.GRAB_ITEM)
                elif time.time() - self.wait_time > self.timeout:
                    self.next_state(States.FAIL)

                time.sleep(self.t_loop)

            case States.GRAB_ITEM:
                # remove the grabbed item label so the second search finds the other item
                grabbed_label = self.current_target[0] if self.current_target else None
                if grabbed_label and grabbed_label in self.remaining_items:
                    self.remaining_items.remove(grabbed_label)
                self.next_state(States.SEARCH_FOR_BASKET)

            case States.SEARCH_FOR_BASKET:
                detections = self.helper.get_target_detections()
                target = self.helper.choose_basket_target(detections, self.basket_label)

                if target is not None:
                    self.current_target = target
                    self.next_state(States.VERIFY_BASKET_TARGET)
                elif time.time() - self.wait_time > self.timeout:
                    self.next_state(States.FAIL)

                time.sleep(self.t_loop)

            case States.VERIFY_BASKET_TARGET:
                detections = self.helper.get_target_detections()
                target = self.helper.choose_basket_target(detections, self.basket_label)

                if target is not None:
                    self.current_target = target
                    if self.helper.check_target_stable(target):
                        self.next_state(States.RELEASE_ITEM)
                elif time.time() - self.wait_time > self.timeout:
                    self.next_state(States.FAIL)

                time.sleep(self.t_loop)

            case States.RELEASE_ITEM:
                if self.item_num < self.max_items:
                    self.item_num += 1
                    self.next_state(States.SEARCH_FOR_ITEM)
                else:
                    self.next_state(States.COMPLETE)

            case States.COMPLETE:
                return

            case States.FAIL:
                self.next_state(States.SEARCH_FOR_ITEM)

            case _:
                self.logger.error(f"{self.name} INVALID STATE {self.state}")
