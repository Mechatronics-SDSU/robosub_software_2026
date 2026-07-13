import os
import time
import yaml

from fsm.fsm                                import FSM_Template
from modules.logger.logger                  import Logger
from modules.grabber.grabber_helpers        import GrabberHelpers
from modules.vision.target_box_helpers      import FINAL_SETTLE_TIME_S
from enum                                   import Enum


"""
    FSM for navigating through Octagon/Resupply (grabber task)
"""

class States(Enum):
    """
    Enumeration for FSM states
    """
    INIT                    = "INIT"
    MOVE_TO_OCTAGON         = "MOVE_TO_OCTAGON"
    SEARCH_FOR_ITEM         = "SEARCH_FOR_ITEM"
    VERIFY_ITEM_TARGET      = "VERIFY_ITEM_TARGET"
    ALIGN_TO_ITEM           = "ALIGN_TO_ITEM"
    VERIFY_GRAB_POSITION    = "VERIFY_GRAB_POSITION"
    GRAB_ITEM               = "GRAB_ITEM"
    MOVE_TO_BASKET          = "MOVE_TO_BASKET"
    SEARCH_FOR_BASKET       = "SEARCH_FOR_BASKET"
    VERIFY_BASKET_TARGET    = "VERIFY_BASKET_TARGET"
    ALIGN_TO_BASKET         = "ALIGN_TO_BASKET"
    VERIFY_RELEASE_POSITION = "VERIFY_RELEASE_POSITION"
    RELEASE_ITEM            = "RELEASE_ITEM"
    SURFACE_IN_OCTAGON      = "SURFACE_IN_OCTAGON"
    ROTATE_FOR_BONUS        = "ROTATE_FOR_BONUS"
    FACE_TARGET_ICON        = "FACE_TARGET_ICON"
    COMPLETE                = "COMPLETE"
    FAIL                    = "FAIL"

    def __str__(self) -> str: # make elegant string
        return self.value


class Grabber_FSM(FSM_Template):
    """
    FSM for grabber mode (Octagon/Resupply) - finding role items on the
    center table using the downward camera, grabbing them, carrying each to
    the role basket on the octagon edge, releasing them, then surfacing,
    rotating once per item placed (scoring bonus), and facing the correct icon.

    The suggested state list for this task also included separate
    SEARCH_FOR_SECOND_ITEM / GRAB_SECOND_ITEM / RELEASE_SECOND_ITEM states.
    Those are combined into a single set of states reused for both items with
    an item_num/remaining_items counter instead, the same pattern already
    used by fsm/torpedo_fsm.py's SHOOTING -> SEARCHING loop and fsm/dropper_fsm.py.
    """
    def __init__(self, shared_memory_object, run_list: list, signal_wrapper=None):
        """
        Grabber FSM constructor

        signal_wrapper: a real SignalWrapper (modules/signals/SignalWrapper.py)
        built from the shared USB_Transmitter, or None to use safe print
        placeholders instead of actuating real hardware (e.g. test mode).
        """
        # call parent constructor
        super().__init__(shared_memory_object, run_list)
        self.name: str      = "GRABBER"
        self.state: States  = States.INIT  # initial state
        self.logger = Logger()

        # TABLE APPROACH VALUES----------------------------------------------------------------------------------------------------------
        self.x1 = self.y1 = self.depth = 0.0
        self.x_buffer = self.y_buffer = self.z_buffer = 0.10
        self.timeout = 8.0
        self.t_loop = 0.10

        # BASKET APPROACH VALUES (different location than the table, on the octagon edge)-------------------------------------------------
        self.basket_x = self.basket_y = 0.0

        # ITEM COUNT----------------------------------------------------------------------------------------------------------------------------
        self.item_num = 1 # which item we are currently working on (1 or 2)
        self.max_items = 2
        self.items_released = 0
        self.current_target = None # item or basket detection picked out of the vision target boxes

        # VISION / LINEUP VALUES--------------------------------------------------------------------------------------------------------------
        # camera looks straight down, so this is how high above the item/basket to hover
        self.desired_height = 0.3 # meters
        # FIXME: waiting on real measured depths for the table/baskets, placeholders for now
        self.item_target_depth = 1.0 # meters, placeholder
        self.basket_target_depth = 1.0 # meters, placeholder
        self.x_lineup_tolerance = 0.05 # meters (metric back-projection, not normalized image fraction)
        self.y_lineup_tolerance = 0.05 # meters

        self.max_object_yaml_error = 1.0
        self.final_settle_time = FINAL_SETTLE_TIME_S
        self.verify_entered_time = 0.0
        self.wait_time = 0.0

        role = "survey_and_repair"
        claw_offset_x = claw_offset_y = 0.0
        model_weights = "models/best.pt"

        try:
            with open(os.path.expanduser("~/robosub_software_2026/objects.yaml"), 'r') as file: # read from yaml
                data = yaml.safe_load(file)
                course = data['course']
                # role is a single top-level switch for the whole run, shared with dropper
                role = data.get('role', role)

                self.x_buffer = data[course]['grabber'].get('x_buf', self.x_buffer)
                self.y_buffer = data[course]['grabber'].get('y_buf', self.y_buffer)
                self.z_buffer = data[course]['grabber'].get('z_buf', self.z_buffer)
                self.x1 = data[course]['grabber'].get('x1', self.x1)
                self.y1 = data[course]['grabber'].get('y1', self.y1)
                self.depth = data[course]['grabber'].get('z', self.depth)

                self.basket_x = data[course]['grabber'].get('basket_x', self.basket_x)
                self.basket_y = data[course]['grabber'].get('basket_y', self.basket_y)

                self.timeout = data[course]['grabber'].get('timeout', self.timeout)
                self.t_loop = data[course]['grabber'].get('t_loop', self.t_loop)
                self.desired_height = data[course]['grabber'].get('desired_height', self.desired_height)
                self.item_target_depth = data[course]['grabber'].get('item_target_depth', self.item_target_depth)
                self.basket_target_depth = data[course]['grabber'].get('basket_target_depth', self.basket_target_depth)
                self.x_lineup_tolerance = data[course]['grabber'].get('x_lineup_tolerance', self.x_lineup_tolerance)
                self.y_lineup_tolerance = data[course]['grabber'].get('y_lineup_tolerance', self.y_lineup_tolerance)

                self.max_object_yaml_error = data[course]['grabber'].get('max_object_yaml_error', self.max_object_yaml_error)
                self.final_settle_time = data[course]['grabber'].get('final_settle_time', self.final_settle_time)
                # FIXME: claw_offset_x/y are unmeasured placeholders (0.0), see objects.yaml
                claw_offset_x = data[course]['grabber'].get('claw_offset_x', claw_offset_x)
                claw_offset_y = data[course]['grabber'].get('claw_offset_y', claw_offset_y)
                model_weights = data[course]['grabber'].get('model_weights', model_weights)

        except FileNotFoundError:
            self.logger.error(f"{self.name} ERROR: objects.yaml not found, using default grabber values")
        except KeyError:
            self.logger.error(f"{self.name} ERROR: Invalid data format in objects.yaml, using default grabber values")

        self.role = role # "survey_and_repair" or "search_and_rescue", set once for the whole run in objects.yaml
        self.helper = GrabberHelpers(shared_memory_object, signal_wrapper, weights_path=model_weights,
                                      claw_offset_body=(claw_offset_x, claw_offset_y))
        self.role_items = self.helper.get_role_items(self.role) # both item labels for this role
        self.remaining_items = list(self.role_items) # items not grabbed yet
        self.basket_label = self.helper.get_basket_label(self.role)

    def start(self) -> None:
        """
        Start FSM by enabling and starting processes
        """
        super().start()  # call parent start method

        # set initial state
        self.next_state(States.MOVE_TO_OCTAGON)

    def next_state(self, next: States) -> None:
        """
        Change to next state
        """
        if not self.active or self.state == next: return # do nothing if not enabled or no state change

        # STATES-----------------------------------------------------------------------------------------------------------------------
        match(next):
            case States.INIT:
                return # initial state

            case States.MOVE_TO_OCTAGON: # approach guestimate coordinates for the center table
                self.shared_memory_object.target_x.value = self.x1
                self.shared_memory_object.target_y.value = self.y1
                self.shared_memory_object.target_z.value = self.depth
                self.wait_time = time.time()

            case States.SEARCH_FOR_ITEM: # look for a remaining role item
                self.helper.reset_tracking()
                self.wait_time = time.time()

            case States.VERIFY_ITEM_TARGET: # keep checking the item is a stable target
                self.wait_time = time.time()

            case States.ALIGN_TO_ITEM: # start driving the claw toward the item using the downward camera
                self.wait_time = time.time()

            case States.VERIFY_GRAB_POSITION: # hold position, re-check the item with a stricter pass before grabbing
                self.wait_time = time.time()
                self.verify_entered_time = time.time()

            case States.GRAB_ITEM: # grab the item
                self.helper.close_claw()
                self.helper.grab_object()
                if self.current_target is not None and self.current_target[0] in self.remaining_items:
                    self.remaining_items.remove(self.current_target[0])
                time.sleep(1) # give some time for the claw to close

            case States.MOVE_TO_BASKET: # approach guestimate coordinates for the role basket (different location than the table)
                self.shared_memory_object.target_x.value = self.basket_x
                self.shared_memory_object.target_y.value = self.basket_y
                self.shared_memory_object.target_z.value = self.depth
                self.wait_time = time.time()

            case States.SEARCH_FOR_BASKET: # look for the role's basket
                self.helper.reset_tracking()
                self.wait_time = time.time()

            case States.VERIFY_BASKET_TARGET: # keep checking the basket is a stable target
                self.wait_time = time.time()

            case States.ALIGN_TO_BASKET: # start driving the claw toward the basket using the downward camera
                self.wait_time = time.time()

            case States.VERIFY_RELEASE_POSITION: # hold position, re-check the basket with a stricter pass before releasing
                self.wait_time = time.time()
                self.verify_entered_time = time.time()

            case States.RELEASE_ITEM: # release the item into the basket
                self.helper.release_object()
                self.helper.open_claw()
                self.items_released += 1
                time.sleep(1) # give some time for the claw to open

            case States.SURFACE_IN_OCTAGON: # surface while staying inside the octagon
                self.helper.surface_in_octagon()
                self.wait_time = time.time()

            case States.ROTATE_FOR_BONUS: # rotate once per item successfully placed (section 3.2.6 bonus)
                self.helper.start_rotation(self.items_released)

            case States.FACE_TARGET_ICON: # face the correct icon for the role/item count
                icon_label = self.helper.get_target_icon(self.role, self.items_released)
                self.helper.face_target_icon(icon_label)

            case States.COMPLETE:
                self.suspend() # finish grabber mode, ready for next mode

            case States.FAIL:
                self.logger.warning(f"{self.name} FAILED to complete item {self.item_num}")
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
        self.display(0, 150, 150) # update display

        assumed_table_world = (self.x1, self.y1)
        assumed_basket_world = (self.basket_x, self.basket_y)

        # TRANSITIONS------------------------------------------------------------------------------------------------------
        match(self.state):
            case States.INIT:
                return

            case States.MOVE_TO_OCTAGON: # transition: MOVE_TO_OCTAGON -> SEARCH_FOR_ITEM
                if self.reached_xyz(self.x1, self.y1, self.depth):
                    self.next_state(States.SEARCH_FOR_ITEM)
                elif time.time() - self.wait_time > self.timeout:
                    self.next_state(States.SEARCH_FOR_ITEM)

            case States.SEARCH_FOR_ITEM: # transition: SEARCH_FOR_ITEM -> VERIFY_ITEM_TARGET
                detections = self.helper.get_target_detections()
                target = self.helper.choose_item_target(detections, self.remaining_items)

                if target is not None:
                    self.current_target = target
                    self.next_state(States.VERIFY_ITEM_TARGET)
                elif time.time() - self.wait_time > self.timeout:
                    self.next_state(States.FAIL)

                time.sleep(self.t_loop)

            case States.VERIFY_ITEM_TARGET: # transition: VERIFY_ITEM_TARGET -> ALIGN_TO_ITEM
                detections = self.helper.get_target_detections()
                target = self.helper.choose_item_target(detections, self.remaining_items)

                if target is not None:
                    self.current_target = target
                    if self.helper.check_target_stable(target):
                        self.next_state(States.ALIGN_TO_ITEM)
                elif time.time() - self.wait_time > self.timeout:
                    self.next_state(States.FAIL)

                time.sleep(self.t_loop)

            case States.ALIGN_TO_ITEM: # transition: ALIGN_TO_ITEM -> VERIFY_GRAB_POSITION
                result = self.helper.align_step(
                    lambda detections: self.helper.choose_item_target(detections, self.remaining_items),
                    self.item_target_depth, self.desired_height, self.x_lineup_tolerance, self.y_lineup_tolerance,
                    assumed_table_world, self.max_object_yaml_error
                )
                self.current_target = result["target"]

                if result["lost"] or result["rejected"]:
                    self.next_state(States.SEARCH_FOR_ITEM)
                elif result["centered"] and result["dwell_ok"]:
                    self.next_state(States.VERIFY_GRAB_POSITION)
                elif time.time() - self.wait_time > self.timeout:
                    self.next_state(States.FAIL)

                time.sleep(self.t_loop)

            case States.VERIFY_GRAB_POSITION: # transition: VERIFY_GRAB_POSITION -> GRAB_ITEM
                result = self.helper.align_step(
                    lambda detections: self.helper.choose_item_target(detections, self.remaining_items),
                    self.item_target_depth, self.desired_height, self.x_lineup_tolerance, self.y_lineup_tolerance,
                    assumed_table_world, self.max_object_yaml_error
                )
                self.current_target = result["target"]

                if result["lost"] or result["rejected"]:
                    self.next_state(States.SEARCH_FOR_ITEM)
                elif result["centered"] and result["dwell_ok"]:
                    settled = time.time() - self.verify_entered_time >= self.final_settle_time
                    verified = result["target"] is not None and self.helper.check_target_verified(result["target"])
                    if settled and verified:
                        self.next_state(States.GRAB_ITEM)
                elif time.time() - self.wait_time > self.timeout:
                    self.next_state(States.FAIL)

                time.sleep(self.t_loop)

            case States.GRAB_ITEM: # transition: GRAB_ITEM -> MOVE_TO_BASKET
                self.next_state(States.MOVE_TO_BASKET)

            case States.MOVE_TO_BASKET: # transition: MOVE_TO_BASKET -> SEARCH_FOR_BASKET
                if self.reached_xyz(self.basket_x, self.basket_y, self.depth):
                    self.next_state(States.SEARCH_FOR_BASKET)
                elif time.time() - self.wait_time > self.timeout:
                    self.next_state(States.SEARCH_FOR_BASKET)

            case States.SEARCH_FOR_BASKET: # transition: SEARCH_FOR_BASKET -> VERIFY_BASKET_TARGET
                detections = self.helper.get_target_detections()
                target = self.helper.choose_basket_target(detections, self.basket_label)

                if target is not None:
                    self.current_target = target
                    self.next_state(States.VERIFY_BASKET_TARGET)
                elif time.time() - self.wait_time > self.timeout:
                    self.next_state(States.FAIL)

                time.sleep(self.t_loop)

            case States.VERIFY_BASKET_TARGET: # transition: VERIFY_BASKET_TARGET -> ALIGN_TO_BASKET
                detections = self.helper.get_target_detections()
                target = self.helper.choose_basket_target(detections, self.basket_label)

                if target is not None:
                    self.current_target = target
                    if self.helper.check_target_stable(target):
                        self.next_state(States.ALIGN_TO_BASKET)
                elif time.time() - self.wait_time > self.timeout:
                    self.next_state(States.FAIL)

                time.sleep(self.t_loop)

            case States.ALIGN_TO_BASKET: # transition: ALIGN_TO_BASKET -> VERIFY_RELEASE_POSITION
                result = self.helper.align_step(
                    lambda detections: self.helper.choose_basket_target(detections, self.basket_label),
                    self.basket_target_depth, self.desired_height, self.x_lineup_tolerance, self.y_lineup_tolerance,
                    assumed_basket_world, self.max_object_yaml_error
                )
                self.current_target = result["target"]

                if result["lost"] or result["rejected"]:
                    self.next_state(States.SEARCH_FOR_BASKET)
                elif result["centered"] and result["dwell_ok"]:
                    self.next_state(States.VERIFY_RELEASE_POSITION)
                elif time.time() - self.wait_time > self.timeout:
                    self.next_state(States.FAIL)

                time.sleep(self.t_loop)

            case States.VERIFY_RELEASE_POSITION: # transition: VERIFY_RELEASE_POSITION -> RELEASE_ITEM
                result = self.helper.align_step(
                    lambda detections: self.helper.choose_basket_target(detections, self.basket_label),
                    self.basket_target_depth, self.desired_height, self.x_lineup_tolerance, self.y_lineup_tolerance,
                    assumed_basket_world, self.max_object_yaml_error
                )
                self.current_target = result["target"]

                if result["lost"] or result["rejected"]:
                    self.next_state(States.SEARCH_FOR_BASKET)
                elif result["centered"] and result["dwell_ok"]:
                    settled = time.time() - self.verify_entered_time >= self.final_settle_time
                    verified = result["target"] is not None and self.helper.check_target_verified(result["target"])
                    if settled and verified:
                        self.next_state(States.RELEASE_ITEM)
                elif time.time() - self.wait_time > self.timeout:
                    self.next_state(States.FAIL)

                time.sleep(self.t_loop)

            case States.RELEASE_ITEM: # transition: RELEASE_ITEM -> MOVE_TO_OCTAGON (2nd item) or SURFACE_IN_OCTAGON
                if self.item_num < self.max_items and self.remaining_items:
                    self.item_num += 1
                    self.next_state(States.MOVE_TO_OCTAGON)
                else:
                    self.next_state(States.SURFACE_IN_OCTAGON)

            case States.SURFACE_IN_OCTAGON: # transition: SURFACE_IN_OCTAGON -> ROTATE_FOR_BONUS
                self.next_state(States.ROTATE_FOR_BONUS)

            case States.ROTATE_FOR_BONUS: # transition: ROTATE_FOR_BONUS -> FACE_TARGET_ICON
                if self.helper.advance_rotation_step():
                    self.next_state(States.FACE_TARGET_ICON)

                time.sleep(self.t_loop)

            case States.FACE_TARGET_ICON: # transition: FACE_TARGET_ICON -> COMPLETE
                self.next_state(States.COMPLETE)

            case States.COMPLETE:
                return

            case States.FAIL:
                return

            case _: # do nothing if invalid state
                self.logger.error(f"{self.name} INVALID STATE {self.state}")
