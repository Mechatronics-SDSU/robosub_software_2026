import time

from modules.vision.target_box_helpers import (
    REQUIRED_STABLE_FRAMES,
    is_stable_target,
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
)

"""
    Helper functions for the dropper FSM (fsm/dropper_fsm.py).
    Handles bin target selection, target verification, role bin labels,
    downward-camera alignment, and dropper actuation. Keep repeated dropper
    logic here instead of inside the FSM.
"""

# ROLE BIN LABELS, these already exist as trained vision classes-----------------------------------------------------------------
SURVEY_AND_REPAIR_LABEL = "fire"
SEARCH_AND_RESCUE_LABEL = "blood"

# DROPPER ACTUATION TIMING, hardware timing is not finalized yet, tune these---------------------------------------------------
DROPPER_OPEN_TIME_SEC = 1.0    # how long to hold the dropper open before closing it again
DROPPER_CLOSE_TIME_SEC = 0.5   # how long to wait after closing before continuing (let servo settle)
DROPPER_USE_TIMED_PULSE = True # if False, release_marker() opens and leaves it open, no auto re-close


class DropperHelpers:
    """
    Helper functions for dropper bin selection, downward-camera lineup, and
    dropper actuation.
    """
    def __init__(self, shared_memory_object, dropper_wrapper=None):
        self.shared_memory = shared_memory_object
        self.dropper_wrapper = dropper_wrapper # real DropperWrapper (modules/dropper/DropperWrapper.py), or None for safe print placeholders
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

    def get_bin_label(self, role: str) -> str:
        """
        Returns the vision class label for the bin matching the given role.
        """
        if role == "search_and_rescue":
            return SEARCH_AND_RESCUE_LABEL
        return SURVEY_AND_REPAIR_LABEL # default to survey_and_repair

    def get_target_detections(self) -> list:
        """
        Runs the live vision pipeline (modules/vision/main.py) and returns
        one frame of detections in this format:
            [class_label, class_id, conf, x_norm, y_norm, depth_m, width, height]

        Imported lazily so importing this file (and testing with fake
        detections) doesn't require the vision dependencies (cv2, ultralytics)
        to be installed.
        """
        from modules.vision.main import get_detections
        return convert_vision_runtime_detections(get_detections())

    def choose_bin_target(self, detections: list, bin_label: str):
        """
        Picks the first detection matching bin_label, or None if not found.
        """
        return get_target_detection(detections, bin_label)

    def reset_tracking(self) -> None:
        """
        Clears all rolling tracking state. Call this when starting to search
        for a new bin, so old frames/timers don't carry over.
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
        Checks if the bin hasn't been seen recently enough to keep tracking it.
        """
        return target_lost_too_long(self.last_detection_time)

    def align_step(self, bin_label: str, target_depth: float, desired_height: float, x_tolerance: float, y_tolerance: float) -> dict:
        """
        Runs one tick of downward-camera alignment toward the bin, using the
        camera + pressure sensor depth (this camera has no depth sensing of
        its own, no ZED/stereo):
            1. fetch a fresh detection matching bin_label
            2. if briefly lost, hold position and wait for it to reappear
            3. if lost too long, report lost so the FSM can go back to searching
            4. otherwise smooth the box center over recent frames, back-project
               it to a metric x/y error using target_depth, and nudge target_x/y
               toward the bin; target_z is set directly from target_depth/
               desired_height (heave doesn't come from the image at all here)
            5. track how long the bin has stayed centered (dwell time)

        MISSING: waiting on the route plan to know which of the dropper's
        bin heights applies to a given detection, see fsm/dropper_fsm.py.
        target_depth is currently whatever single placeholder value the FSM
        passes in.

        Returns a dict of results/debug info:
            target, centered, dwell_ok, lost
        """
        detections = self.get_target_detections()
        detection = get_target_detection(detections, bin_label)

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
        sub_depth = self.shared_memory.depth.value # real pressure sensor reading

        x_error_m, y_error_m = get_target_error_meters(smoothed_center[0], smoothed_center[1], sub_depth, target_depth)

        self.last_x_error, self.last_y_error, self.last_depth_error = x_error_m, y_error_m, 0.0
        strafe_cmd, forward_cmd = nudge_xy_toward_target(self.shared_memory, x_error_m, y_error_m)
        self.last_motion_cmd = (strafe_cmd, forward_cmd, 0.0) # heave is a direct setpoint below, not a proportional command
        set_hover_depth(self.shared_memory, target_depth, desired_height)

        centered_now = is_target_centered_metric(x_error_m, y_error_m, x_tolerance, y_tolerance)
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

    def release_marker(self) -> None:
        """
        Releases one marker: opens the dropper, holds it open for
        DROPPER_OPEN_TIME_SEC, then closes it again if DROPPER_USE_TIMED_PULSE
        is True. Uses the real DropperWrapper if one was passed in, otherwise
        prints a safe placeholder (no hardware attached, e.g. test mode).

        MISSING: exact hardware timing is not finalized yet (may end up being
        a motor pulse instead of a servo state change), DROPPER_OPEN_TIME_SEC/
        DROPPER_CLOSE_TIME_SEC/DROPPER_USE_TIMED_PULSE are starting placeholders.
        """
        if self.dropper_wrapper is not None:
            self.dropper_wrapper.open()
        else:
            print("DROPPER OPEN PLACEHOLDER (no DropperWrapper attached)")

        if not DROPPER_USE_TIMED_PULSE:
            return

        time.sleep(DROPPER_OPEN_TIME_SEC)

        if self.dropper_wrapper is not None:
            self.dropper_wrapper.close()
        else:
            print("DROPPER CLOSE PLACEHOLDER (no DropperWrapper attached)")

        time.sleep(DROPPER_CLOSE_TIME_SEC)
