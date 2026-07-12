import time

from modules.vision.target_box_helpers import (
    REQUIRED_STABLE_FRAMES,
    is_stable_target,
    is_target_centered,
    is_at_correct_height,
    filter_detections_by_label,
    get_target_detection,
    average_target_center,
    estimate_distance_to_target,
    calculate_depth_error,
    move_using_target_error,
    stop_vehicle_motion,
    has_required_center_time,
    target_lost_too_long,
    convert_vision_runtime_detections,
)

"""
    Helper functions for the grabber FSM (fsm/grabber_fsm.py).
    Handles item/basket target selection, target verification, role item
    labels, downward-camera alignment, and placeholder claw/surfacing
    actuation. Keep repeated grabber logic here instead of inside the FSM.
"""

# ROLE ITEM/BASKET/ICON LABELS----------------------------------------------------------------------------------------------------
# NOTE: bolt, plug, medicine, bandage, compass, hammer, life_ring, sos, warning,
# and helmet are NOT trained vision classes yet (the model only has firetruck,
# fire, ambulance, blood, see modules/vision/config.yaml). These are placeholder
# label strings from the task description, update them once the model is
# retrained with real grabber classes.
SURVEY_AND_REPAIR_ITEMS = ["bolt", "plug"]
SEARCH_AND_RESCUE_ITEMS = ["medicine", "bandage"]

SURVEY_AND_REPAIR_BASKET = "warning"
SEARCH_AND_RESCUE_BASKET = "helmet"

# icon to face based on role and how many items are currently in the basket
ONE_ITEM_ICON  = {"survey_and_repair": "compass", "search_and_rescue": "life_ring"}
TWO_ITEM_ICON  = {"survey_and_repair": "hammer",  "search_and_rescue": "sos"}

# MISSING: these are placeholder headings (degrees), update with real measured
# headings for each icon inside the octagon once known
ICON_HEADINGS = {
    "compass":   0,
    "life_ring": 0,
    "hammer":    0,
    "sos":       0,
}


class GrabberHelpers:
    """
    Helper functions for grabber item/basket selection, downward-camera
    lineup, and placeholder actuation.
    """
    def __init__(self, shared_memory_object, signal_wrapper=None):
        self.shared_memory = shared_memory_object
        self.signal_wrapper = signal_wrapper # real SignalWrapper (modules/signals/SignalWrapper.py), or None for safe print placeholders
        self.detection_history = []
        self.last_valid_detection = None
        self.last_detection_time = 0.0
        self.centered_since = None # time.time() of when the target first became centered, None if not centered

        # debug info, updated every align_step() call, read by the test controller
        self.last_x_error = 0.0
        self.last_y_error = 0.0
        self.last_depth_error = 0.0
        self.last_motion_cmd = (0.0, 0.0, 0.0) # (strafe_cmd, forward_cmd, vertical_cmd)
        self.last_stable = False
        self.last_centered = False
        self.last_dwell_ok = False
        self.last_lost = False

    def get_role_items(self, role: str) -> list:
        """
        Returns the two vision class labels for items matching the given role.
        """
        if role == "search_and_rescue":
            return list(SEARCH_AND_RESCUE_ITEMS)
        return list(SURVEY_AND_REPAIR_ITEMS) # default to survey_and_repair

    def get_basket_label(self, role: str) -> str:
        """
        Returns the vision class label for the basket matching the given role.
        """
        if role == "search_and_rescue":
            return SEARCH_AND_RESCUE_BASKET
        return SURVEY_AND_REPAIR_BASKET # default to survey_and_repair

    def get_target_icon(self, role: str, items_placed: int) -> str:
        """
        Returns which icon to face based on role and how many items are in the basket.
        """
        if items_placed >= 2:
            return TWO_ITEM_ICON.get(role, TWO_ITEM_ICON["survey_and_repair"])
        return ONE_ITEM_ICON.get(role, ONE_ITEM_ICON["survey_and_repair"])

    def get_target_detections(self) -> list:
        """
        Runs the live vision pipeline (modules/vision/main.py) and returns
        one frame of detections in this format:
            [class_label, class_id, conf, x_norm, y_norm, depth_m, width, height]

        Imported lazily so importing this file (and testing with fake
        detections) doesn't require the vision dependencies (cv2, ultralytics)
        to be installed.

        NOTE: bolt/plug/medicine/bandage/compass/hammer/life_ring/sos/warning/
        helmet are not trained vision classes yet (see the NOTE above), so
        real detections will never match those labels until the model is
        retrained.
        """
        from modules.vision.main import get_detections
        return convert_vision_runtime_detections(get_detections())

    def choose_item_target(self, detections: list, remaining_items: list):
        """
        Picks the first detection matching any label still in remaining_items,
        or None if not found.
        """
        for label in remaining_items:
            matches = filter_detections_by_label(detections, label)
            if matches:
                return matches[0]
        return None

    def choose_basket_target(self, detections: list, basket_label: str):
        """
        Picks the first detection matching basket_label, or None if not found.
        """
        return get_target_detection(detections, basket_label)

    def reset_tracking(self) -> None:
        """
        Clears all rolling tracking state. Call this when starting to search
        for a new item or basket, so old frames/timers don't carry over.
        """
        self.detection_history = []
        self.last_valid_detection = None
        self.last_detection_time = 0.0
        self.centered_since = None

    def record_detection(self, detection) -> None:
        """
        Records a detection into the rolling history (used for both the
        stability check and center-position smoothing) and marks it as the
        last known good detection.
        """
        self.detection_history.append(detection)
        if len(self.detection_history) > REQUIRED_STABLE_FRAMES:
            self.detection_history.pop(0)
        self.last_valid_detection = detection
        self.last_detection_time = time.time()

    def check_target_stable(self, detection) -> bool:
        """
        Records a detection into the rolling history and checks if the last
        REQUIRED_STABLE_FRAMES detections form a stable target.
        """
        self.record_detection(detection)
        self.last_stable = is_stable_target(self.detection_history)
        return self.last_stable

    def is_target_lost(self) -> bool:
        """
        Checks if the item/basket hasn't been seen recently enough to keep tracking it.
        """
        return target_lost_too_long(self.last_detection_time)

    def align_step(self, choose_target_fn, desired_height: float, x_tolerance: float, y_tolerance: float) -> dict:
        """
        Runs one tick of downward-camera alignment toward whatever
        choose_target_fn(detections) picks out (an item or a basket):
            1. fetch fresh detections and pick a target with choose_target_fn
            2. if briefly lost, hold position and wait for it to reappear
            3. if lost too long, report lost so the FSM can go back to searching
            4. otherwise smooth the box center over recent frames, compute
               x/y/depth error, and nudge target_x/y/z toward the target
            5. track how long the target has stayed centered (dwell time)

        Returns a dict of results/debug info:
            target, centered, dwell_ok, lost
        """
        detections = self.get_target_detections()
        detection = choose_target_fn(detections)

        if detection is not None:
            self.record_detection(detection)
        elif self.is_target_lost():
            self.last_lost = True
            return {"target": None, "centered": False, "dwell_ok": False, "lost": True}
        else:
            # briefly lost, hold position, keep using the last known target
            stop_vehicle_motion(self.shared_memory)
            self.last_lost = False
            return {"target": self.last_valid_detection, "centered": False, "dwell_ok": False, "lost": False}

        self.last_lost = False

        # smooth the center position over recent frames to reduce single-frame noise
        smoothed_center = average_target_center(self.detection_history)
        x_error = smoothed_center[0] - 0.5
        y_error = smoothed_center[1] - 0.5

        distance = estimate_distance_to_target(self.last_valid_detection)
        depth_error = calculate_depth_error(distance, desired_height) if distance > 0 else 0.0

        self.last_x_error, self.last_y_error, self.last_depth_error = x_error, y_error, depth_error
        self.last_motion_cmd = move_using_target_error(self.shared_memory, x_error, y_error, depth_error)

        centered_now = (
            is_target_centered(self.last_valid_detection, x_tolerance, y_tolerance)
            and is_at_correct_height(distance, desired_height)
        )
        if centered_now:
            if self.centered_since is None:
                self.centered_since = time.time()
        else:
            self.centered_since = None

        self.last_centered = centered_now
        self.last_dwell_ok = has_required_center_time(self.centered_since)

        return {
            "target": self.last_valid_detection,
            "centered": centered_now,
            "dwell_ok": self.last_dwell_ok,
            "lost": False,
        }

    def open_claw(self) -> None:
        """
        Opens the claw fingers (releases a held item) via the SignalWrapper.
        NOTE: grabber hardware behavior is not fully verified yet, these
        calls are wired but the servo values/sequence may need tuning.
        """
        if self.signal_wrapper is not None:
            self.signal_wrapper.release_claw()
        else:
            print("GRABBER OPEN CLAW PLACEHOLDER (no SignalWrapper attached)")

    def close_claw(self) -> None:
        """
        Closes the claw fingers on the currently aligned item via the SignalWrapper.
        NOTE: grabber hardware behavior is not fully verified yet, these
        calls are wired but the servo values/sequence may need tuning.
        """
        if self.signal_wrapper is not None:
            self.signal_wrapper.grab_claw()
        else:
            print("GRABBER CLOSE CLAW PLACEHOLDER (no SignalWrapper attached)")

    def grab_object(self) -> None:
        """
        Lifts the grabbed item by raising the claw arm via the SignalWrapper.
        Called right after close_claw(), so the fingers are already closed.
        NOTE: grabber hardware behavior is not fully verified yet, these
        calls are wired but the servo values/sequence may need tuning.
        """
        if self.signal_wrapper is not None:
            self.signal_wrapper.raise_claw()
        else:
            print("GRABBER GRAB OBJECT PLACEHOLDER (no SignalWrapper attached)")

    def release_object(self) -> None:
        """
        Lowers the claw arm toward the basket via the SignalWrapper. Called
        right before open_claw(), which actually releases the item.
        NOTE: grabber hardware behavior is not fully verified yet, these
        calls are wired but the servo values/sequence may need tuning.
        """
        if self.signal_wrapper is not None:
            self.signal_wrapper.lower_claw()
        else:
            print("GRABBER RELEASE OBJECT PLACEHOLDER (no SignalWrapper attached)")

    def surface_in_octagon(self) -> None:
        """
        Surfaces by setting target_z to 0, the same pattern return_fsm.py's
        RISE_END state uses to surface. Assumes the sub is still positioned
        inside the octagon (see MOVE_TO_OCTAGON) when this is called.
        """
        self.shared_memory.target_z.value = 0

    def face_target_icon(self, icon_label: str) -> None:
        """
        Turns to face the given icon by setting target_yaw to its known
        heading, the same pattern coinflip_fsm.py uses for target_yaw.

        MISSING: real measured headings for each icon, see ICON_HEADINGS
        above, all currently placeholder 0 values.
        """
        self.shared_memory.target_yaw.value = ICON_HEADINGS.get(icon_label, 0)
