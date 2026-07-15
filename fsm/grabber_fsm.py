import os
import time
import yaml

from fsm.fsm                                import FSM_Template
from modules.logger.logger                  import Logger
from modules.grabber.grabber_helpers        import GrabberHelpers, CLASS_LABELS, DEFAULT_ITEM_IDS, DEFAULT_ITEM_TO_BIN
from modules.vision.target_box_helpers      import FINAL_SETTLE_TIME_S, stop_vehicle_motion
from enum                                   import Enum


"""
    FSM for the Octagon/Resupply grabber task (handbook 3.2.6):
    all four emoji items off the center table, each carried to its
    role-matched basket, surfacing with every item, finishing with the icon
    face + rotation bonus. Class ids everywhere (configured in objects.yaml):
        items 5 (electric) / 6 (nutbolt) -> basket 13 (warning)
        items 4 (bandaid)  / 7 (pill)    -> basket 8  (redcross)
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
    LIFT_AND_VERIFY         = "LIFT_AND_VERIFY"
    SURFACE_WITH_ITEM       = "SURFACE_WITH_ITEM"
    DESCEND_TO_BINS         = "DESCEND_TO_BINS"
    MOVE_TO_BASKET          = "MOVE_TO_BASKET"
    SEARCH_FOR_BASKET       = "SEARCH_FOR_BASKET"
    VERIFY_BASKET_TARGET    = "VERIFY_BASKET_TARGET"
    ALIGN_TO_BASKET         = "ALIGN_TO_BASKET"
    VERIFY_RELEASE_POSITION = "VERIFY_RELEASE_POSITION"
    RELEASE_ITEM            = "RELEASE_ITEM"
    POST_RELEASE_CHECK      = "POST_RELEASE_CHECK"
    SURFACE_IN_OCTAGON      = "SURFACE_IN_OCTAGON"
    ROTATE_FOR_BONUS        = "ROTATE_FOR_BONUS"
    FACE_TARGET_ICON        = "FACE_TARGET_ICON"
    COMPLETE                = "COMPLETE"
    FAIL                    = "FAIL"

    def __str__(self) -> str: # make elegant string
        return self.value


# states during which the sub believes it is carrying an item - the carry
# monitor watches for the item re-appearing on a surface below in all of them
CARRYING_STATES = {
    States.SURFACE_WITH_ITEM, States.DESCEND_TO_BINS, States.MOVE_TO_BASKET,
    States.SEARCH_FOR_BASKET, States.VERIFY_BASKET_TARGET,
    States.ALIGN_TO_BASKET, States.VERIFY_RELEASE_POSITION,
}

FINALE_STATES = {States.SURFACE_IN_OCTAGON, States.FACE_TARGET_ICON, States.ROTATE_FOR_BONUS, States.COMPLETE, States.FAIL}


class Grabber_FSM(FSM_Template):
    """
    FSM for grabber mode (Octagon/Resupply) - finds the four role items on
    the center table with the downward camera, and for EACH item: aligns,
    grabs, lifts and visually verifies the grab (the item still sitting on
    the table = failed grab, retry), surfaces with the item (scored), dives
    back down, carries it to the item's OWN basket (5/6 -> 13, 4/7 -> 8),
    places it beside the basket marker so the marker stays visible for the
    second placement, and releases. Ends by surfacing, facing the correct
    icon (vision scan, heading fallback), then the rotation bonus - the
    spins are the very last scored action.

    Every state degrades toward "bank the points we have" instead of a dead
    FAIL: timeouts skip items rather than aborting, a lost carry re-adds the
    item's class, and the finale is always attempted.
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

        # TABLE APPROACH VALUES----------------------------------------------------------------------------------------------------
        self.x1 = self.y1 = self.depth = 0.0
        self.x_buffer = self.y_buffer = self.z_buffer = 0.10
        self.timeout = 8.0
        self.t_loop = 0.10

        # ITEMS / BINS------------------------------------------------------------------------------------------------------------
        self.item_class_ids = list(DEFAULT_ITEM_IDS)
        self.item_order = list(DEFAULT_ITEM_IDS)
        self.item_to_bin = dict(DEFAULT_ITEM_TO_BIN)
        self.baskets = { # bin class id -> {x, y, face_yaw}
            13: {"x": 0.0, "y": 0.0, "face_yaw": 0.0},
            8:  {"x": 0.0, "y": 0.0, "face_yaw": 0.0},
        }

        # VISION / LINEUP VALUES--------------------------------------------------------------------------------------------------
        # camera looks straight down, so this is how high above the item/basket to hover
        self.desired_height = 0.3 # meters
        # FIXME: waiting on real measured depths for the table/baskets, placeholders for now
        self.item_target_depth = 1.0 # meters, placeholder
        self.basket_target_depth = 1.0 # meters, placeholder
        self.x_lineup_tolerance = 0.05 # meters (metric back-projection, not normalized image fraction)
        self.y_lineup_tolerance = 0.05 # meters
        self.max_object_yaml_error = 1.0
        self.final_settle_time = FINAL_SETTLE_TIME_S

        # GRAB VERIFY / SURFACING / PLACEMENT---------------------------------------------------------------------------------------
        self.grab_retries = 2
        self.grab_verify_height = 0.6  # hover height for the lift-and-look check
        self.grab_verify_time = 2.5    # seconds of clean frames before a grab counts as verified
        self.verify_extend = 1.5       # extra window when sightings are intermittent
        self.surface_z = 0.0
        self.surface_pause = 1.0
        self.place_side = "left"       # which side of the bin marker the FIRST item lands on
        self.place_margin = 0.10       # meters past the marker's half-width
        self.place_margin_max = 0.25   # clamp so a huge box can't push the drop out of the basket
        self.post_release_check = True
        self.post_release_time = 2.0   # seconds of looking down for the released item before marking UNSURE

        # STABILITY CONTRACT------------------------------------------------------------------------------------------------------
        self.stable_frames = 4         # consecutive frames a detection must persist before it counts
        self.stable_iou = 0.60         # positional overlap (IoU) required between those frames
        self.class_swap_wait = 0.2     # settle after swapping the YOLO classes filter (first inference lags)

        # FALLBACK KNOBS----------------------------------------------------------------------------------------------------------
        self.carry_max_width = 0.35    # size gate: wider = the item in our own claw, not on a surface
        self.carry_ignore_region = None
        self.search_lift = 0.4         # rise once for a wider FOV when a search times out
        self.search_cycles = 2         # verify/align re-search cycles before skipping an item
        self.allow_wrong_bin = True
        self.blind_release = True
        self.task_time_budget = 600.0
        self.dvl_grace = 5.0
        self.max_depth_limit = 3.0

        # FINALE------------------------------------------------------------------------------------------------------------------
        self.finale_order = "icon_first" # icon_first (spins are the very last thing) | spin_first
        self.finale_turn_degrees = 360.0
        self.finale_assume_items = 2   # the "default to 2 when unsure" rule
        self.icon_scan_step = 15.0
        self.icon_timeout = 20.0
        self.icon_deg_per_image = 90.0 # forward camera horizontal FOV
        self.icon_yaw_sign = 1.0
        self.rotation_step_timeout = 6.0

        camera_rotate_180 = False
        claw_offset_x = claw_offset_y = 0.0
        model_weights = "models/best.pt"

        # hardware settings live in config/hardware.yaml (deployment-specific, course-independent)
        hw_path = os.path.expanduser("~/robosub_software_2026/config/hardware.yaml")
        try:
            with open(hw_path) as f:
                hw = yaml.safe_load(f)
                g = hw.get('grabber', {})
                model_weights = g.get('model_weights', model_weights)
                claw_offset_x = g.get('claw_offset_x', claw_offset_x)
                claw_offset_y = g.get('claw_offset_y', claw_offset_y)
                camera_rotate_180 = g.get('camera_rotate_180', camera_rotate_180)
        except FileNotFoundError:
            self.logger.error(f"{self.name} ERROR: config/hardware.yaml not found, using default grabber hardware values")
        except KeyError:
            self.logger.error(f"{self.name} ERROR: Invalid format in config/hardware.yaml, using default grabber hardware values")

        try:
            with open(os.path.expanduser("~/robosub_software_2026/objects.yaml"), 'r') as file: # read from yaml
                data = yaml.safe_load(file)
                course = data['course']
                grabber = data[course]['grabber']

                self.x_buffer = grabber.get('x_buf', self.x_buffer)
                self.y_buffer = grabber.get('y_buf', self.y_buffer)
                self.z_buffer = grabber.get('z_buf', self.z_buffer)
                self.x1 = grabber.get('x1', self.x1)
                self.y1 = grabber.get('y1', self.y1)
                self.depth = grabber.get('z', self.depth)

                self.item_class_ids = list(grabber.get('item_class_ids', self.item_class_ids))
                self.item_order = list(grabber.get('item_order', self.item_class_ids))
                self.item_to_bin = {int(k): int(v) for k, v in grabber.get('item_to_bin', self.item_to_bin).items()}
                for key in ('basket_a', 'basket_b'):
                    basket = grabber.get(key)
                    if basket and 'bin_id' in basket:
                        self.baskets[int(basket['bin_id'])] = {
                            "x": basket.get('x', 0.0), "y": basket.get('y', 0.0),
                            "face_yaw": basket.get('face_yaw', 0.0),
                        }

                self.timeout = grabber.get('timeout', self.timeout)
                self.t_loop = grabber.get('t_loop', self.t_loop)
                self.desired_height = grabber.get('desired_height', self.desired_height)
                self.item_target_depth = grabber.get('item_target_depth', self.item_target_depth)
                self.basket_target_depth = grabber.get('basket_target_depth', self.basket_target_depth)
                self.x_lineup_tolerance = grabber.get('x_lineup_tolerance', self.x_lineup_tolerance)
                self.y_lineup_tolerance = grabber.get('y_lineup_tolerance', self.y_lineup_tolerance)
                self.max_object_yaml_error = grabber.get('max_object_yaml_error', self.max_object_yaml_error)
                self.final_settle_time = grabber.get('final_settle_time', self.final_settle_time)

                self.grab_retries = grabber.get('grab_retries', self.grab_retries)
                self.grab_verify_height = grabber.get('grab_verify_height', self.grab_verify_height)
                self.grab_verify_time = grabber.get('grab_verify_time', self.grab_verify_time)
                self.verify_extend = grabber.get('verify_extend', self.verify_extend)
                self.surface_z = grabber.get('surface_z', self.surface_z)
                self.surface_pause = grabber.get('surface_pause', self.surface_pause)
                self.place_side = grabber.get('place_side', self.place_side)
                self.place_margin = grabber.get('place_margin', self.place_margin)
                self.place_margin_max = grabber.get('place_margin_max', self.place_margin_max)
                self.post_release_check = grabber.get('post_release_check', self.post_release_check)
                self.post_release_time = grabber.get('post_release_time', self.post_release_time)

                self.stable_frames = grabber.get('stable_frames', self.stable_frames)
                self.stable_iou = grabber.get('stable_iou', self.stable_iou)
                self.class_swap_wait = grabber.get('class_swap_wait', self.class_swap_wait)

                self.carry_max_width = grabber.get('carry_max_width', self.carry_max_width)
                self.carry_ignore_region = grabber.get('carry_ignore_region', self.carry_ignore_region)
                self.search_lift = grabber.get('search_lift', self.search_lift)
                self.search_cycles = grabber.get('search_cycles', self.search_cycles)
                self.allow_wrong_bin = grabber.get('allow_wrong_bin', self.allow_wrong_bin)
                self.blind_release = grabber.get('blind_release', self.blind_release)
                self.task_time_budget = grabber.get('task_time_budget', self.task_time_budget)
                self.dvl_grace = grabber.get('dvl_grace', self.dvl_grace)
                self.max_depth_limit = grabber.get('max_depth_limit', self.max_depth_limit)

                self.finale_order = grabber.get('finale_order', self.finale_order)
                self.finale_turn_degrees = grabber.get('finale_turn_degrees', self.finale_turn_degrees)
                self.finale_assume_items = grabber.get('finale_assume_items', self.finale_assume_items)
                self.icon_scan_step = grabber.get('icon_scan_step', self.icon_scan_step)
                self.icon_timeout = grabber.get('icon_timeout', self.icon_timeout)
                self.icon_deg_per_image = grabber.get('icon_deg_per_image', self.icon_deg_per_image)
                self.icon_yaw_sign = grabber.get('icon_yaw_sign', self.icon_yaw_sign)
                self.rotation_step_timeout = grabber.get('rotation_step_timeout', self.rotation_step_timeout)

        except FileNotFoundError:
            self.logger.error(f"{self.name} ERROR: objects.yaml not found, using default grabber values")
        except KeyError:
            self.logger.error(f"{self.name} ERROR: Invalid data format in objects.yaml, using default grabber values")

        self.helper = GrabberHelpers(shared_memory_object, signal_wrapper, weights_path=model_weights,
                                      claw_offset_body=(claw_offset_x, claw_offset_y), camera_rotate_180=camera_rotate_180,
                                      stable_frames=self.stable_frames, stable_iou=self.stable_iou, class_swap_wait=self.class_swap_wait)

        # ITEM/RUN PROGRESS-------------------------------------------------------------------------------------------------------
        self.remaining_items = list(self.item_class_ids) # class ids not yet confirmed off the table
        self.retries_left = {class_id: self.grab_retries for class_id in self.item_class_ids}
        self.placed_count = {bin_id: 0 for bin_id in self.baskets} # per-basket placements (occlusion side logic)
        self.items_released = 0
        self.items_skipped = 0
        self.count_uncertain = False # any UNSURE placement -> the finale falls back to finale_assume_items
        self.pending_class = None    # class id we believe is in the claw
        self.pending_bin = None      # that item's basket class id
        self.current_target = None   # item or basket detection picked out of the vision target boxes

        # PER-STATE FALLBACK BOOKKEEPING------------------------------------------------------------------------------------------
        self.wait_time = 0.0
        self.verify_entered_time = 0.0
        self.search_lifted = False
        self.align_cycles = 0
        self.basket_widened = False
        self.blind_pending = False
        self.surface_nudged = False
        self.at_surface_since = None
        self.verify_deadline = 0.0
        self.verify_extended = False
        self.face_started = 0.0
        self.task_start_time = 0.0
        self.dvl_invalid_since = None
        self.finale_aborted = False

        # finale phase order: the spins are the very last scored action (icon_first),
        # or swap via objects.yaml finale_order: spin_first
        if self.finale_order == "spin_first":
            self.finale_sequence = [States.SURFACE_IN_OCTAGON, States.ROTATE_FOR_BONUS, States.FACE_TARGET_ICON, States.COMPLETE]
        else:
            self.finale_sequence = [States.SURFACE_IN_OCTAGON, States.FACE_TARGET_ICON, States.ROTATE_FOR_BONUS, States.COMPLETE]

    # HELPERS----------------------------------------------------------------------------------------------------------------------
    def _finale_next(self, current: States) -> States:
        """
        Returns the finale state that follows `current` per finale_order.
        """
        index = self.finale_sequence.index(current)
        return self.finale_sequence[min(index + 1, len(self.finale_sequence) - 1)]

    def _effective_items(self) -> int:
        """
        Item count used for the rotation bonus and icon choice: the real
        count when it's trustworthy, finale_assume_items (default 2) when
        nothing was placed or any placement was UNSURE - the "take a chance"
        rule.
        """
        if self.items_released > 0 and not self.count_uncertain:
            return self.items_released
        return self.finale_assume_items

    def _abort_to_finale(self, reason: str) -> None:
        """
        Abandon whatever remains and go bank the finale points (surface +
        icon + spins). Never a dead FAIL.
        """
        if self.state in FINALE_STATES:
            return
        self.logger.warning(f"{self.name} aborting to finale: {reason} "
                            f"(released={self.items_released} skipped={self.items_skipped} remaining={self.remaining_items})")
        self.finale_aborted = True
        self.next_state(States.SURFACE_IN_OCTAGON)

    def _bin_filter_ids(self) -> list:
        """
        Basket class ids to look for, correct bin first; widened to both
        bins after the wrong-bin fallback kicks in.
        """
        ids = [self.pending_bin]
        if self.basket_widened:
            ids += [bin_id for bin_id in self.baskets if bin_id != self.pending_bin]
        return ids

    def _placement_offset_body(self) -> tuple:
        """
        Body-frame lateral offset for the release point. First item into a
        basket goes place_side of the marker (so the dropped item can't
        occlude the marker the second approach needs); the second goes the
        OPPOSITE side (never stacked on the marker or on item one). Offset
        magnitude = marker half-width back-projected to meters + place_margin,
        clamped by place_margin_max so the drop stays inside the basket.
        FIXME: which physical direction "left" maps to depends on the camera/
        body axis convention - verify in the pool and flip place_side if the
        first drop lands on the wrong side.
        """
        first_into_bin = self.placed_count.get(self.pending_bin, 0) == 0
        side = self.place_side if first_into_bin else ("right" if self.place_side == "left" else "left")
        sign = -1.0 if side == "left" else 1.0
        half_width_m = 0.0
        if self.current_target is not None:
            half_width_m = self.helper.detection_width_m(self.current_target, self.basket_target_depth) / 2.0
        offset_m = min(half_width_m + self.place_margin, self.place_margin_max)
        return (sign * offset_m, 0.0)

    def _handle_drop(self, verdict: str) -> bool:
        """
        Carry-monitor response. Returns True if a transition happened (the
        caller's state tick should stop).
        """
        if verdict is None or self.pending_class is None:
            return False
        label = CLASS_LABELS.get(self.pending_class, self.pending_class)
        if verdict == "dropped_near_table" and self.retries_left.get(self.pending_class, 0) > 0:
            self.logger.warning(f"{self.name} carry monitor: {label} spotted back on the table - failed/slipped grab, retrying")
            self.retries_left[self.pending_class] -= 1
            if self.pending_class not in self.remaining_items:
                self.remaining_items.insert(0, self.pending_class)
            self.pending_class = self.pending_bin = None
            self.next_state(States.MOVE_TO_OCTAGON)
            return True
        # dropped somewhere unrecoverable (or out of retries) - write it off, keep moving
        self.logger.warning(f"{self.name} carry monitor: {label} lost ({verdict}, retries_left={self.retries_left.get(self.pending_class, 0)}) - writing it off")
        if self.pending_class in self.remaining_items:
            self.remaining_items.remove(self.pending_class)
        self.items_skipped += 1
        self.pending_class = self.pending_bin = None
        if self.remaining_items:
            self.next_state(States.MOVE_TO_OCTAGON)
        else:
            self._abort_to_finale("no items left after a lost carry")
        return True

    def _carry_monitor_tick(self, detections: list = None) -> bool:
        """
        Runs the carry monitor while an item should be in the claw. Pass
        detections when the state already ran an inference this tick (basket
        search/align states); transit states let the helper run its own.
        Returns True if a drop was handled (state changed).
        """
        if self.pending_class is None or self.state not in CARRYING_STATES:
            return False
        if detections is not None:
            verdict = self.helper.carry_monitor_ingest(detections, self.pending_class, (self.x1, self.y1), self.item_target_depth,
                                                        self.carry_max_width, self.carry_ignore_region, self.max_object_yaml_error)
        else:
            verdict = self.helper.carry_monitor_step(self.pending_class, (self.x1, self.y1), self.item_target_depth,
                                                      self.carry_max_width, self.carry_ignore_region, self.max_object_yaml_error)
        return self._handle_drop(verdict)

    def _after_release(self) -> None:
        """
        Routes to the next item (table) or the finale once a release (and its
        optional post-check) is done.
        """
        self.pending_class = self.pending_bin = None
        self.current_target = None
        if self.remaining_items:
            self.next_state(States.MOVE_TO_OCTAGON)
        else:
            self.next_state(States.SURFACE_IN_OCTAGON)

    def _skip_current_item(self, reason: str) -> None:
        """
        Gives up on the item currently being worked (align/verify/grab phase),
        removes its class so the search stops chasing it, and moves on.
        """
        class_id = None
        if self.current_target is not None:
            class_id = self.current_target[1] # CLASS_ID index
        elif self.pending_class is not None:
            class_id = self.pending_class
        if class_id is not None and class_id in self.remaining_items:
            self.remaining_items.remove(class_id)
            self.items_skipped += 1
            self.logger.warning(f"{self.name} skipping item {CLASS_LABELS.get(class_id, class_id)}: {reason}")
        self.pending_class = self.pending_bin = None
        self.current_target = None
        self.align_cycles = 0
        if self.remaining_items:
            self.next_state(States.SEARCH_FOR_ITEM)
        else:
            self._abort_to_finale("no items left to work")

    # LIFECYCLE--------------------------------------------------------------------------------------------------------------------
    def start(self) -> None:
        """
        Start FSM by enabling and starting processes
        """
        super().start()  # call parent start method

        self.task_start_time = time.time()

        # loud early warning if the weights on the sub can't even produce the configured ids
        try:
            required = set(self.item_class_ids) | set(self.item_to_bin.values())
            missing = self.helper.verify_model_classes(sorted(required))
            if missing:
                self.logger.error(f"{self.name} MODEL MISSING CLASS IDS {missing} - "
                                  f"weights '{self.helper.weights_path}' can't see those items/baskets, update the model!")
        except Exception as error:
            self.logger.error(f"{self.name} could not verify model classes: {error}")

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
                self.align_cycles = 0 # fresh re-search budget for the new item cycle
                self.wait_time = time.time()

            case States.SEARCH_FOR_ITEM: # look for a remaining item (class-id filtered at the model)
                self.helper.reset_tracking()
                self.search_lifted = False
                self.wait_time = time.time()

            case States.VERIFY_ITEM_TARGET: # keep checking the item is a stable target
                self.wait_time = time.time()

            case States.ALIGN_TO_ITEM: # start driving the claw toward the item using the downward camera
                self.wait_time = time.time()

            case States.VERIFY_GRAB_POSITION: # hold position, re-check the item with a stricter pass before grabbing
                self.wait_time = time.time()
                self.verify_entered_time = time.time()

            case States.GRAB_ITEM: # grab the item - possession is NOT assumed, LIFT_AND_VERIFY decides
                self.helper.close_claw()
                self.helper.grab_object()
                if self.current_target is not None:
                    self.pending_class = self.current_target[1] # CLASS_ID index
                    self.pending_bin = self.item_to_bin.get(self.pending_class)
                time.sleep(1) # give some time for the claw to close

            case States.LIFT_AND_VERIFY: # rise over the table and look: item still there = failed grab
                self.helper.verify_grab_reset()
                self.shared_memory_object.target_z.value = self.item_target_depth - self.grab_verify_height
                self.wait_time = time.time()
                self.verify_deadline = self.grab_verify_time
                self.verify_extended = False

            case States.SURFACE_WITH_ITEM: # straight up - surfacing with each item is scored
                self.helper.carry_monitor_reset()
                self.helper.surface_in_octagon(self.surface_z)
                self.surface_nudged = False
                self.at_surface_since = None
                self.wait_time = time.time()

            case States.DESCEND_TO_BINS: # back down to working depth before heading for the basket
                self.shared_memory_object.target_z.value = self.depth
                self.wait_time = time.time()

            case States.MOVE_TO_BASKET: # approach this item's OWN basket, holding its face_yaw so
                                        # the marker appears in the orientation the model trained on
                basket = self.baskets.get(self.pending_bin, {"x": 0.0, "y": 0.0, "face_yaw": 0.0})
                self.shared_memory_object.target_x.value = basket["x"]
                self.shared_memory_object.target_y.value = basket["y"]
                self.shared_memory_object.target_z.value = self.depth
                self.shared_memory_object.target_yaw.value = basket["face_yaw"]
                self.align_cycles = 0 # fresh re-search budget for the basket phase
                self.basket_widened = False
                self.blind_pending = False
                self.wait_time = time.time()

            case States.SEARCH_FOR_BASKET: # look for this item's basket marker
                self.helper.reset_tracking()
                self.wait_time = time.time()

            case States.VERIFY_BASKET_TARGET: # keep checking the basket is a stable target
                self.wait_time = time.time()

            case States.ALIGN_TO_BASKET: # drive the claw toward the OFFSET release point beside the marker
                self.wait_time = time.time()

            case States.VERIFY_RELEASE_POSITION: # hold position, re-check the basket with a stricter pass before releasing
                self.wait_time = time.time()
                self.verify_entered_time = time.time()

            case States.RELEASE_ITEM: # release the item into the basket
                self.helper.release_object()
                self.helper.open_claw()
                self.items_released += 1
                if self.pending_bin in self.placed_count:
                    self.placed_count[self.pending_bin] += 1
                if self.blind_pending:
                    self.count_uncertain = True
                    self.logger.warning(f"{self.name} BLIND release of {CLASS_LABELS.get(self.pending_class, self.pending_class)} "
                                        f"at dead-reckoned basket coords - placement UNSURE")
                time.sleep(1) # give some time for the claw to open
                self.wait_time = time.time()

            case States.POST_RELEASE_CHECK: # quick look down - do we see the item near the marker?
                self.helper.verify_grab_reset()
                self.wait_time = time.time()

            case States.SURFACE_IN_OCTAGON: # finale surface (also the landing spot for every abort)
                self.helper.surface_in_octagon(self.surface_z)
                self.wait_time = time.time()

            case States.ROTATE_FOR_BONUS: # rotate once per item placed (section 3.2.6 bonus)
                self.helper.start_rotation(self._effective_items(), self.finale_turn_degrees)

            case States.FACE_TARGET_ICON: # face the correct icon for the item count (vision scan, heading fallback)
                self.helper.start_icon_scan()
                self.face_started = time.time()

            case States.COMPLETE:
                self.logger.info(f"{self.name} DONE: released={self.items_released} skipped={self.items_skipped} "
                                 f"uncertain={self.count_uncertain} effective_items={self._effective_items()}")
                self.suspend() # finish grabber mode, ready for next mode

            case States.FAIL: # only for truly invalid situations - normal failures abort to the finale instead
                self.logger.warning(f"{self.name} FAILED (released={self.items_released} skipped={self.items_skipped})")
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

        # GLOBAL WATCHDOGS-------------------------------------------------------------------------------------------------------
        # never dive past the course's hard depth limit, whatever wrote target_z
        if self.shared_memory_object.target_z.value > self.max_depth_limit:
            self.shared_memory_object.target_z.value = self.max_depth_limit
        # out of task time - bank the finale points with whatever we have
        if self.state not in FINALE_STATES and time.time() - self.task_start_time > self.task_time_budget:
            self._abort_to_finale("task time budget spent")
            return
        # navigating without DVL is drift - hold, then give up and go finale
        if self.state not in FINALE_STATES and hasattr(self.shared_memory_object, "dvl_velocity_valid"):
            if not self.shared_memory_object.dvl_velocity_valid.value:
                if self.dvl_invalid_since is None:
                    self.dvl_invalid_since = time.time()
                    stop_vehicle_motion(self.shared_memory_object)
                elif time.time() - self.dvl_invalid_since > self.dvl_grace:
                    self._abort_to_finale("DVL invalid too long")
                    return
            else:
                self.dvl_invalid_since = None

        assumed_table_world = (self.x1, self.y1)
        basket = self.baskets.get(self.pending_bin) if self.pending_bin is not None else None
        assumed_basket_world = (basket["x"], basket["y"]) if basket else None

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
                if not self.remaining_items:
                    self._abort_to_finale("no items remaining")
                    return
                detections = self.helper.get_target_detections(classes=list(self.remaining_items))
                target = self.helper.choose_item_target(detections, self.remaining_items, self.item_order)

                if target is not None:
                    self.current_target = target
                    self.next_state(States.VERIFY_ITEM_TARGET)
                elif time.time() - self.wait_time > self.timeout:
                    if not self.search_lifted:
                        # rise once for a wider view of the table before giving up
                        self.search_lifted = True
                        self.shared_memory_object.target_z.value = max(self.surface_z, self.shared_memory_object.target_z.value - self.search_lift)
                        self.wait_time = time.time()
                        self.logger.warning(f"{self.name} item search timed out - lifting {self.search_lift}m for a wider view")
                    else:
                        self._abort_to_finale(f"no items visible ({self.remaining_items} remain)")

                time.sleep(self.t_loop)

            case States.VERIFY_ITEM_TARGET: # transition: VERIFY_ITEM_TARGET -> ALIGN_TO_ITEM
                detections = self.helper.get_target_detections(classes=list(self.remaining_items))
                target = self.helper.choose_item_target(detections, self.remaining_items, self.item_order)

                if target is not None:
                    self.current_target = target
                    if self.helper.check_target_stable(target):
                        self.next_state(States.ALIGN_TO_ITEM)
                elif time.time() - self.wait_time > self.timeout:
                    self.align_cycles += 1
                    if self.align_cycles > self.search_cycles:
                        self._skip_current_item("target never stabilized")
                    else:
                        self.next_state(States.SEARCH_FOR_ITEM)

                time.sleep(self.t_loop)

            case States.ALIGN_TO_ITEM: # transition: ALIGN_TO_ITEM -> VERIFY_GRAB_POSITION
                result = self.helper.align_step(
                    lambda detections: self.helper.choose_item_target(detections, self.remaining_items, self.item_order),
                    self.item_target_depth, self.desired_height, self.x_lineup_tolerance, self.y_lineup_tolerance,
                    assumed_table_world, self.max_object_yaml_error, classes=list(self.remaining_items)
                )
                self.current_target = result["target"]

                if result["lost"] or result["rejected"]:
                    self.align_cycles += 1
                    if self.align_cycles > self.search_cycles:
                        self._skip_current_item("alignment kept losing/rejecting the target")
                    else:
                        self.next_state(States.SEARCH_FOR_ITEM)
                elif result["centered"] and result["dwell_ok"]:
                    self.next_state(States.VERIFY_GRAB_POSITION)
                elif time.time() - self.wait_time > self.timeout:
                    self.align_cycles += 1
                    if self.align_cycles > self.search_cycles:
                        self._skip_current_item("alignment timed out")
                    else:
                        self.next_state(States.SEARCH_FOR_ITEM)

                time.sleep(self.t_loop)

            case States.VERIFY_GRAB_POSITION: # transition: VERIFY_GRAB_POSITION -> GRAB_ITEM
                result = self.helper.align_step(
                    lambda detections: self.helper.choose_item_target(detections, self.remaining_items, self.item_order),
                    self.item_target_depth, self.desired_height, self.x_lineup_tolerance, self.y_lineup_tolerance,
                    assumed_table_world, self.max_object_yaml_error, classes=list(self.remaining_items)
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
                    self.align_cycles += 1
                    if self.align_cycles > self.search_cycles:
                        self._skip_current_item("grab-position verify timed out")
                    else:
                        self.next_state(States.SEARCH_FOR_ITEM)

                time.sleep(self.t_loop)

            case States.GRAB_ITEM: # transition: GRAB_ITEM -> LIFT_AND_VERIFY
                self.next_state(States.LIFT_AND_VERIFY)

            case States.LIFT_AND_VERIFY: # transition: verified -> SURFACE_WITH_ITEM, failed -> retry/skip
                if self.pending_class is None:
                    self._skip_current_item("grabbed with no known class")
                    return
                failed = self.helper.verify_grab_step(self.pending_class, self.carry_max_width, self.carry_ignore_region)
                if failed:
                    # item is demonstrably still on the table - the claw closed on water
                    self.helper.open_claw()
                    self.retries_left[self.pending_class] = self.retries_left.get(self.pending_class, 0) - 1
                    label = CLASS_LABELS.get(self.pending_class, self.pending_class)
                    if self.retries_left[self.pending_class] >= 0:
                        self.logger.warning(f"{self.name} grab FAILED for {label} - retrying ({self.retries_left[self.pending_class]} retries left)")
                        self.pending_class = self.pending_bin = None
                        self.next_state(States.SEARCH_FOR_ITEM)
                    else:
                        self._skip_current_item("grab retries exhausted")
                elif time.time() - self.wait_time > self.verify_deadline:
                    if self.helper.verify_sightings > 0 and not self.verify_extended:
                        # intermittent single-frame sightings - extend the window once before trusting the grab
                        self.verify_extended = True
                        self.verify_deadline += self.verify_extend
                    else:
                        # table looks clear of the item's class - the grab is real
                        if self.pending_class in self.remaining_items:
                            self.remaining_items.remove(self.pending_class)
                        self.logger.info(f"{self.name} grab VERIFIED for {CLASS_LABELS.get(self.pending_class, self.pending_class)}")
                        self.next_state(States.SURFACE_WITH_ITEM)

                time.sleep(self.t_loop)

            case States.SURFACE_WITH_ITEM: # transition: SURFACE_WITH_ITEM -> DESCEND_TO_BINS
                if self._carry_monitor_tick():
                    return
                if self.shared_memory_object.dvl_z.value <= self.z_buffer:
                    if self.at_surface_since is None:
                        self.at_surface_since = time.time()
                    elif time.time() - self.at_surface_since >= self.surface_pause:
                        self.next_state(States.DESCEND_TO_BINS)
                elif time.time() - self.wait_time > self.timeout:
                    if not self.surface_nudged:
                        # possibly stuck under octagon structure - one nudge toward the center, retry
                        self.surface_nudged = True
                        self.shared_memory_object.target_x.value = self.x1
                        self.shared_memory_object.target_y.value = self.y1
                        self.wait_time = time.time()
                        self.logger.warning(f"{self.name} surfacing stalled - nudging toward octagon center")
                    else:
                        self.logger.warning(f"{self.name} could not surface - continuing at depth (forfeiting this item's surface points)")
                        self.next_state(States.DESCEND_TO_BINS)

                time.sleep(self.t_loop)

            case States.DESCEND_TO_BINS: # transition: DESCEND_TO_BINS -> MOVE_TO_BASKET
                if self._carry_monitor_tick():
                    return
                if abs(self.shared_memory_object.dvl_z.value - self.depth) <= self.z_buffer:
                    self.next_state(States.MOVE_TO_BASKET)
                elif time.time() - self.wait_time > self.timeout:
                    self.next_state(States.MOVE_TO_BASKET)

                time.sleep(self.t_loop)

            case States.MOVE_TO_BASKET: # transition: MOVE_TO_BASKET -> SEARCH_FOR_BASKET
                if self._carry_monitor_tick():
                    return
                basket = self.baskets.get(self.pending_bin, {"x": 0.0, "y": 0.0})
                if self.reached_xyz(basket["x"], basket["y"], self.depth):
                    self.next_state(States.SEARCH_FOR_BASKET)
                elif time.time() - self.wait_time > self.timeout:
                    self.next_state(States.SEARCH_FOR_BASKET)

                time.sleep(self.t_loop)

            case States.SEARCH_FOR_BASKET: # transition: SEARCH_FOR_BASKET -> VERIFY_BASKET_TARGET
                bin_ids = self._bin_filter_ids()
                detections = self.helper.get_target_detections(classes=bin_ids + [self.pending_class])
                if self._carry_monitor_tick(detections):
                    return
                target = self.helper.choose_basket_target(detections, bin_ids)

                if target is not None:
                    self.current_target = target
                    self.next_state(States.VERIFY_BASKET_TARGET)
                elif time.time() - self.wait_time > self.timeout:
                    if self.allow_wrong_bin and not self.basket_widened:
                        # any basket still scores - widen to both markers, correct one stays preferred
                        self.basket_widened = True
                        self.wait_time = time.time()
                        self.logger.warning(f"{self.name} basket {self.pending_bin} not found - widening search to both baskets")
                    elif self.blind_release:
                        # nothing visible at all: dead-reckoned release beats carrying it forever
                        self.blind_pending = True
                        self.next_state(States.RELEASE_ITEM)
                    else:
                        self.logger.warning(f"{self.name} no basket found and blind_release disabled - dropping {CLASS_LABELS.get(self.pending_class, self.pending_class)} uncounted")
                        self.helper.release_object()
                        self.helper.open_claw()
                        self.count_uncertain = True
                        self._after_release()

                time.sleep(self.t_loop)

            case States.VERIFY_BASKET_TARGET: # transition: VERIFY_BASKET_TARGET -> ALIGN_TO_BASKET
                bin_ids = self._bin_filter_ids()
                detections = self.helper.get_target_detections(classes=bin_ids + [self.pending_class])
                if self._carry_monitor_tick(detections):
                    return
                target = self.helper.choose_basket_target(detections, bin_ids)

                if target is not None:
                    self.current_target = target
                    if self.helper.check_target_stable(target):
                        self.next_state(States.ALIGN_TO_BASKET)
                elif time.time() - self.wait_time > self.timeout:
                    self.align_cycles += 1
                    if self.align_cycles > self.search_cycles:
                        self.blind_pending = self.blind_release
                        if self.blind_pending:
                            self.next_state(States.RELEASE_ITEM)
                        else:
                            self.next_state(States.SEARCH_FOR_BASKET)
                    else:
                        self.next_state(States.SEARCH_FOR_BASKET)

                time.sleep(self.t_loop)

            case States.ALIGN_TO_BASKET: # transition: ALIGN_TO_BASKET -> VERIFY_RELEASE_POSITION
                bin_ids = self._bin_filter_ids()
                result = self.helper.align_step(
                    lambda detections: self.helper.choose_basket_target(detections, bin_ids),
                    self.basket_target_depth, self.desired_height, self.x_lineup_tolerance, self.y_lineup_tolerance,
                    assumed_basket_world, self.max_object_yaml_error,
                    classes=bin_ids + [self.pending_class], target_offset_body=self._placement_offset_body()
                )
                if self._carry_monitor_tick(result["detections"]):
                    return
                self.current_target = result["target"]

                if result["lost"] or result["rejected"]:
                    self.align_cycles += 1
                    if self.align_cycles > self.search_cycles:
                        self.blind_pending = self.blind_release
                        self.next_state(States.RELEASE_ITEM if self.blind_pending else States.SEARCH_FOR_BASKET)
                    else:
                        self.next_state(States.SEARCH_FOR_BASKET)
                elif result["centered"] and result["dwell_ok"]:
                    self.next_state(States.VERIFY_RELEASE_POSITION)
                elif time.time() - self.wait_time > self.timeout:
                    self.align_cycles += 1
                    if self.align_cycles > self.search_cycles:
                        self.blind_pending = self.blind_release
                        self.next_state(States.RELEASE_ITEM if self.blind_pending else States.SEARCH_FOR_BASKET)
                    else:
                        self.next_state(States.SEARCH_FOR_BASKET)

                time.sleep(self.t_loop)

            case States.VERIFY_RELEASE_POSITION: # transition: VERIFY_RELEASE_POSITION -> RELEASE_ITEM
                bin_ids = self._bin_filter_ids()
                result = self.helper.align_step(
                    lambda detections: self.helper.choose_basket_target(detections, bin_ids),
                    self.basket_target_depth, self.desired_height, self.x_lineup_tolerance, self.y_lineup_tolerance,
                    assumed_basket_world, self.max_object_yaml_error,
                    classes=bin_ids + [self.pending_class], target_offset_body=self._placement_offset_body()
                )
                if self._carry_monitor_tick(result["detections"]):
                    return
                self.current_target = result["target"]

                if result["lost"] or result["rejected"]:
                    self.next_state(States.SEARCH_FOR_BASKET)
                elif result["centered"] and result["dwell_ok"]:
                    settled = time.time() - self.verify_entered_time >= self.final_settle_time
                    verified = result["target"] is not None and self.helper.check_target_verified(result["target"])
                    if settled and verified:
                        self.next_state(States.RELEASE_ITEM)
                elif time.time() - self.wait_time > self.timeout:
                    self.align_cycles += 1
                    if self.align_cycles > self.search_cycles:
                        self.blind_pending = self.blind_release
                        self.next_state(States.RELEASE_ITEM if self.blind_pending else States.SEARCH_FOR_BASKET)
                    else:
                        self.next_state(States.SEARCH_FOR_BASKET)

                time.sleep(self.t_loop)

            case States.RELEASE_ITEM: # transition: RELEASE_ITEM -> POST_RELEASE_CHECK or onward
                if self.post_release_check and not self.blind_pending:
                    self.next_state(States.POST_RELEASE_CHECK)
                else:
                    self._after_release()

            case States.POST_RELEASE_CHECK: # transition: POST_RELEASE_CHECK -> next item / finale
                # look for the released class near the basket - seen means the count is trustworthy
                seen = self.helper.verify_grab_step(self.pending_class, self.carry_max_width, self.carry_ignore_region)
                if seen or self.helper.verify_sightings > 0:
                    self.logger.info(f"{self.name} release CONFIRMED for {CLASS_LABELS.get(self.pending_class, self.pending_class)}")
                    self._after_release()
                elif time.time() - self.wait_time > self.post_release_time:
                    self.logger.warning(f"{self.name} could not confirm the release visually - placement count marked UNSURE")
                    self.count_uncertain = True
                    self._after_release()

                time.sleep(self.t_loop)

            case States.SURFACE_IN_OCTAGON: # transition: -> first finale phase after surfacing
                if self.shared_memory_object.dvl_z.value <= self.z_buffer or time.time() - self.wait_time > self.timeout:
                    self.next_state(self._finale_next(States.SURFACE_IN_OCTAGON))

                time.sleep(self.t_loop)

            case States.FACE_TARGET_ICON: # transition: centered/fallback -> next finale phase
                icon_ids = self.helper.get_target_icon_ids(self._effective_items())
                status = self.helper.face_icon_scan_step(icon_ids, self.icon_scan_step, deg_per_image=self.icon_deg_per_image, yaw_sign=self.icon_yaw_sign)
                if status == "centered":
                    self.logger.info(f"{self.name} facing icon (vision) - ids {icon_ids}")
                    self.next_state(self._finale_next(States.FACE_TARGET_ICON))
                elif status in ("exhausted", "no_camera") or time.time() - self.face_started > self.icon_timeout:
                    self.logger.warning(f"{self.name} icon scan {status} - falling back to heading table")
                    self.helper.face_target_icon(icon_ids)
                    self.next_state(self._finale_next(States.FACE_TARGET_ICON))

                time.sleep(self.t_loop)

            case States.ROTATE_FOR_BONUS: # transition: all turns done -> next finale phase
                if self.helper.advance_rotation_step(step_timeout=self.rotation_step_timeout):
                    self.next_state(self._finale_next(States.ROTATE_FOR_BONUS))

                time.sleep(self.t_loop)

            case States.COMPLETE:
                return

            case States.FAIL:
                return

            case _: # do nothing if invalid state
                self.logger.error(f"{self.name} INVALID STATE {self.state}")
