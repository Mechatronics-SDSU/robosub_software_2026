import time

from modules.vision.vision_model_main import camera, yolo
from modules.vision.target_box_helpers import (
    VERIFY_FRAME_COUNT,
    VERIFY_IOU_MIN,
    MAX_OBJECT_YAML_ERROR_M,
    is_stable_target,
    filter_detections_by_label,
    get_target_detection,
    average_target_center,
    get_target_error_meters,
    is_target_centered_metric,
    nudge_xy_toward_target,
    set_hover_depth,
    stop_vehicle_motion,
    has_required_center_time,
    target_lost_too_long,
    convert_vision_runtime_detections,
    body_offset_to_world_offset,
    distance_2d,
)

"""
    Helper functions for the grabber FSM (fsm/grabber_fsm.py).
    Handles item/basket target selection, target verification, role item
    labels, downward-camera alignment, world-position estimation/sanity-
    checking, and claw/rotation/icon actuation. Keep repeated grabber logic
    here instead of inside the FSM.
"""

# ROLE ITEM/BASKET/ICON LABELS----------------------------------------------------------------------------------------------------
# FIXME: bolt, plug, medicine, bandage, compass, hammer, life_ring, sos, warning,
# and helmet are NOT trained vision classes yet (the model only has firetruck,
# fire, ambulance, blood). These are placeholder label strings from the task
# description, update them once the model is retrained with real grabber classes.
SURVEY_AND_REPAIR_ITEMS = ["bolt", "plug"]
SEARCH_AND_RESCUE_ITEMS = ["medicine", "bandage"]

SURVEY_AND_REPAIR_BASKET = "warning"
SEARCH_AND_RESCUE_BASKET = "helmet"

# icon to face based on role and how many items are currently in the basket
ONE_ITEM_ICON = {"survey_and_repair": "compass", "search_and_rescue": "life_ring"}
TWO_ITEM_ICON = {"survey_and_repair": "hammer",  "search_and_rescue": "sos"}

# FIXME: these are placeholder headings (degrees), update with real measured
# headings for each icon inside the octagon once known
ICON_HEADINGS = {
    "compass":   0,
    "life_ring": 0,
    "hammer":    0,
    "sos":       0,
}

# ROTATION BONUS (section 3.2.6: rotate once per item placed in the basket)------------------------------------------------------
# Stepped in quarter-turns rather than one large target_yaw jump, because
# target_yaw is compared directly against a wrapped 0-360 degree dvl_yaw with
# no multi-revolution unwrapping - a single +720 degree setpoint would never
# resolve as "reached".
ROTATION_STEP_DEGREES = 90
ROTATION_STEPS_PER_TURN = 360 // ROTATION_STEP_DEGREES
ROTATION_STEP_TOLERANCE_DEG = 5.0


class GrabberHelpers:
    """
    Helper functions for grabber item/basket selection, downward-camera
    lineup, world-position estimation, claw actuation, and the rotation bonus.
    """
    def __init__(self, shared_memory_object, signal_wrapper=None, weights_path: str = "models/best.pt",
                 claw_offset_body: tuple = (0.0, 0.0)):
        self.shared_memory = shared_memory_object
        self.signal_wrapper = signal_wrapper # real SignalWrapper (modules/signals/SignalWrapper.py), or None for safe print placeholders

        # vision, opened lazily so importing this file doesn't require camera/YOLO hardware to be present
        # FIXME: confirm this weights file actually exists on the sub and is trained on the grabber item/basket/icon classes
        self.weights_path = weights_path
        self._camera = None
        self._model = None

        # FIXME: claw_offset_body (body frame, meters) is unmeasured, 0.0 means no correction applied.
        # Separate tape-measure job from the dropper's offset - the claw is a different physical location.
        self.claw_offset_body = claw_offset_body

        self.detection_history = []
        self.last_valid_detection = None
        self.last_detection_time = 0.0
        self.centered_since = None # time.time() of when the target first became centered, None if not centered

        self.target_world = None # last estimated item/basket world position, set by align_step

        # debug info, updated every align_step() call, read by the test controller
        self.debug = {
            "x_error": 0.0, "y_error": 0.0, "stable": False,
            "centered": False, "dwell_ok": False, "lost": False, "rejected": False,
        }

        # rotation bonus state (see start_rotation/advance_rotation_step)
        self.rotation_turns_remaining = 0
        self.rotation_steps_done = 0
        self.rotation_target_yaw = None

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
        Runs the live downward-camera vision pipeline
        (modules/vision/vision_model_main.py) and returns one frame of
        detections in this format:
            [class_label, class_id, conf, x_norm, y_norm, depth_m, width, height]

        Camera + model are opened lazily on first call (not in __init__), so
        importing/constructing this class doesn't require the camera/YOLO
        dependencies to be present (e.g. FAKE_INPUT testing).
        """
        if self._camera is None:
            self._camera = camera("downfacing")
        if self._model is None:
            self._model = yolo(self.weights_path)

        detections = self._model.infer(self._camera, headless=True, verbose=False)
        return convert_vision_runtime_detections(detections)

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
        self.target_world = None

    def record_detection(self, detection) -> None:
        """
        Records a detection into the rolling history (used for both the
        stability check and center-position smoothing) and marks it as the
        last known good detection.
        """
        self.detection_history.append(detection)
        if len(self.detection_history) > VERIFY_FRAME_COUNT:
            self.detection_history.pop(0)
        self.last_valid_detection = detection
        self.last_detection_time = time.time()

    def check_target_stable(self, detection) -> bool:
        """
        Records a detection into the rolling history and checks if the last
        REQUIRED_STABLE_FRAMES detections form a stable target.
        """
        self.record_detection(detection)
        stable = is_stable_target(self.detection_history)
        self.debug["stable"] = stable
        return stable

    def check_target_verified(self, detection) -> bool:
        """
        Records a detection and checks the stricter final-verify pass:
        VERIFY_FRAME_COUNT consecutive frames at VERIFY_IOU_MIN.
        """
        self.record_detection(detection)
        verified = is_stable_target(self.detection_history, required_frames=VERIFY_FRAME_COUNT, iou_min=VERIFY_IOU_MIN)
        self.debug["stable"] = verified
        return verified

    def is_target_lost(self) -> bool:
        """
        Checks if the item/basket hasn't been seen recently enough to keep tracking it.
        """
        return target_lost_too_long(self.last_detection_time)

    def estimate_target_world_position(self, x_error_body: float, y_error_body: float) -> tuple:
        """
        Converts a body-frame vision error into a world-frame item/basket
        position estimate: sub_world_position + rotate(vision_offset_body, yaw).
        """
        sub_world = (self.shared_memory.dvl_x.value, self.shared_memory.dvl_y.value)
        yaw_deg = self.shared_memory.dvl_yaw.value
        x_offset_world, y_offset_world = body_offset_to_world_offset(x_error_body, y_error_body, yaw_deg)
        return sub_world[0] + x_offset_world, sub_world[1] + y_offset_world

    def validate_against_assumed(self, target_world: tuple, assumed_world: tuple, max_error: float = MAX_OBJECT_YAML_ERROR_M) -> bool:
        """
        Sanity-checks a vision-derived item/basket world position against the
        objects.yaml assumed location, so a bad detection doesn't get treated
        as ground truth.
        """
        return distance_2d(target_world, assumed_world) <= max_error

    def compute_claw_alignment_target(self, target_world: tuple) -> tuple:
        """
        Returns the world-frame sub position that puts the claw (not the
        downward camera) over the item/basket center:
            desired_sub_world = target_world - rotate(claw_offset_body, yaw)
        """
        yaw_deg = self.shared_memory.dvl_yaw.value
        claw_offset_world = body_offset_to_world_offset(self.claw_offset_body[0], self.claw_offset_body[1], yaw_deg)
        return target_world[0] - claw_offset_world[0], target_world[1] - claw_offset_world[1]

    def align_step(self, choose_target_fn, target_depth: float, desired_height: float, x_tolerance: float, y_tolerance: float,
                    assumed_world: tuple = None, max_object_yaml_error: float = MAX_OBJECT_YAML_ERROR_M) -> dict:
        """
        Runs one tick of downward-camera alignment toward whatever
        choose_target_fn(detections) picks out (an item or a basket), using
        the camera + pressure sensor depth (no ZED/stereo depth here):
            1. fetch fresh detections and pick a target with choose_target_fn
            2. if briefly lost, hold position and wait for it to reappear
            3. if lost too long, report lost so the FSM can go back to searching
            4. otherwise smooth the box center over recent frames, back-project
               it to a metric body-frame x/y error using target_depth
            5. estimate the target's world position (DVL + yaw rotation) and
               sanity-check it against the objects.yaml assumed location;
               reject if it fails the check
            6. compute the claw (not camera) alignment target and nudge
               toward it; target_z is set directly from target_depth/
               desired_height (heave doesn't come from the image at all here)
            7. track how long the target has stayed centered (dwell time)

        Returns a dict of results/debug info:
            target, target_world, centered, dwell_ok, lost, rejected
        """
        detections = self.get_target_detections()
        detection = choose_target_fn(detections)

        if detection is not None:
            self.record_detection(detection)
        elif self.is_target_lost():
            self.debug["lost"] = True
            return {"target": None, "target_world": None, "centered": False, "dwell_ok": False, "lost": True, "rejected": False}
        else:
            # briefly lost, hold position, keep using the last known target
            stop_vehicle_motion(self.shared_memory)
            self.debug["lost"] = False
            return {"target": self.last_valid_detection, "target_world": self.target_world, "centered": False, "dwell_ok": False, "lost": False, "rejected": False}

        self.debug["lost"] = False

        # smooth the center position over recent frames to reduce single-frame noise
        smoothed_center = average_target_center(self.detection_history)
        sub_depth = self.shared_memory.depth.value # real pressure sensor reading

        x_error_m, y_error_m = get_target_error_meters(smoothed_center[0], smoothed_center[1], sub_depth, target_depth)
        self.debug["x_error"], self.debug["y_error"] = x_error_m, y_error_m

        target_world = self.estimate_target_world_position(x_error_m, y_error_m)
        self.target_world = target_world

        if assumed_world is not None and not self.validate_against_assumed(target_world, assumed_world, max_object_yaml_error):
            self.debug["rejected"] = True
            self.centered_since = None
            return {"target": detection, "target_world": target_world, "centered": False, "dwell_ok": False, "lost": False, "rejected": True}

        self.debug["rejected"] = False

        claw_target_world = self.compute_claw_alignment_target(target_world)
        sub_world = (self.shared_memory.dvl_x.value, self.shared_memory.dvl_y.value)
        claw_x_error = claw_target_world[0] - sub_world[0]
        claw_y_error = claw_target_world[1] - sub_world[1]

        nudge_xy_toward_target(self.shared_memory, claw_x_error, claw_y_error)
        set_hover_depth(self.shared_memory, target_depth, desired_height)

        centered_now = is_target_centered_metric(claw_x_error, claw_y_error, x_tolerance, y_tolerance)
        if centered_now:
            if self.centered_since is None:
                self.centered_since = time.time()
        else:
            self.centered_since = None

        self.debug["centered"] = centered_now
        self.debug["dwell_ok"] = has_required_center_time(self.centered_since)

        return {
            "target": detection,
            "target_world": target_world,
            "centered": centered_now,
            "dwell_ok": self.debug["dwell_ok"],
            "lost": False,
            "rejected": False,
        }

    def open_claw(self) -> None:
        """
        Opens the claw fingers (releases a held item) via the SignalWrapper.
        FIXME: claw signal sequence/pulse widths not verified yet, see SignalWrapper.py
        """
        if self.signal_wrapper is not None:
            self.signal_wrapper.release_claw()
        else:
            print("GRABBER OPEN CLAW PLACEHOLDER (no SignalWrapper attached)")

    def close_claw(self) -> None:
        """
        Closes the claw fingers on the currently aligned item via the SignalWrapper.
        FIXME: claw signal sequence/pulse widths not verified yet, see SignalWrapper.py
        """
        if self.signal_wrapper is not None:
            self.signal_wrapper.grab_claw()
        else:
            print("GRABBER CLOSE CLAW PLACEHOLDER (no SignalWrapper attached)")

    def grab_object(self) -> None:
        """
        Lifts the grabbed item by raising the claw arm via the SignalWrapper.
        Called right after close_claw(), so the fingers are already closed.
        FIXME: claw signal sequence/pulse widths not verified yet, see SignalWrapper.py
        """
        if self.signal_wrapper is not None:
            self.signal_wrapper.raise_claw()
        else:
            print("GRABBER GRAB OBJECT PLACEHOLDER (no SignalWrapper attached)")

    def release_object(self) -> None:
        """
        Lowers the claw arm toward the basket via the SignalWrapper. Called
        right before open_claw(), which actually releases the item.
        FIXME: claw signal sequence/pulse widths not verified yet, see SignalWrapper.py
        """
        if self.signal_wrapper is not None:
            self.signal_wrapper.lower_claw()
        else:
            print("GRABBER RELEASE OBJECT PLACEHOLDER (no SignalWrapper attached)")

    def surface_in_octagon(self) -> None:
        """
        Surfaces by setting target_z to 0. Assumes the sub is still
        positioned inside the octagon (see MOVE_TO_OCTAGON) when this is called.
        """
        self.shared_memory.target_z.value = 0

    def face_target_icon(self, icon_label: str) -> None:
        """
        Turns to face the given icon by setting target_yaw to its known heading.

        FIXME: real measured headings for each icon, see ICON_HEADINGS above,
        all currently placeholder 0 values.
        """
        self.shared_memory.target_yaw.value = ICON_HEADINGS.get(icon_label, 0)

    def start_rotation(self, turns: int) -> None:
        """
        Begins the rotation bonus (section 3.2.6): spin in place one full
        360 degree turn per item successfully placed in the basket. Steps in
        ROTATION_STEP_DEGREES increments (see module docstring for why),
        commanding the first step immediately from the sub's current heading.
        turns=0 leaves rotation_turns_remaining at 0, so advance_rotation_step()
        returns True right away (no-op skip when nothing was placed).
        """
        self.rotation_turns_remaining = max(0, turns)
        self.rotation_steps_done = 0
        self.rotation_target_yaw = None
        if self.rotation_turns_remaining > 0:
            self._advance_rotation_target()

    def _advance_rotation_target(self) -> None:
        """
        Commands the next ROTATION_STEP_DEGREES step relative to the sub's
        current heading and sends it as the new target_yaw.
        """
        current_yaw = self.shared_memory.dvl_yaw.value
        self.rotation_target_yaw = (current_yaw + ROTATION_STEP_DEGREES) % 360
        self.shared_memory.target_yaw.value = self.rotation_target_yaw

    def advance_rotation_step(self) -> bool:
        """
        Polled every loop tick while rotating. Checks if the sub has reached
        the current quarter-turn step (wraparound-safe angular difference);
        if so, either commands the next step or, once ROTATION_STEPS_PER_TURN
        steps complete a full turn, moves on to the next turn.

        Returns True once rotation_turns_remaining reaches 0 (all requested
        full turns complete), False otherwise.
        """
        if self.rotation_turns_remaining <= 0:
            return True

        if self.rotation_target_yaw is None:
            self._advance_rotation_target()
            return False

        current_yaw = self.shared_memory.dvl_yaw.value
        raw_delta = current_yaw - self.rotation_target_yaw
        angular_diff = min(abs(raw_delta), 360 - abs(raw_delta))

        if angular_diff > ROTATION_STEP_TOLERANCE_DEG:
            return False # still turning toward the current step

        self.rotation_steps_done += 1
        if self.rotation_steps_done >= ROTATION_STEPS_PER_TURN:
            self.rotation_turns_remaining -= 1
            self.rotation_steps_done = 0

        if self.rotation_turns_remaining <= 0:
            return True

        self._advance_rotation_target()
        return False
