import math
import time

from modules.vision.vision_model_main import camera, yolo
from modules.vision.target_box_helpers import (
    VERIFY_FRAME_COUNT,
    VERIFY_IOU_MIN,
    X_NORM, Y_NORM,
    is_stable_target,
    filter_detections_by_label,
    average_target_center,
    has_required_center_time,
    target_lost_too_long,
    convert_vision_runtime_detections,
    clamp_motion_command,
    stop_vehicle_motion,
    is_target_centered_metric,
)

"""
    Helper functions for the torpedo FSM (fsm/torpedo_fsm.py).
    Handles board/hole detection, ZED-depth-based alignment, hole association
    (matching a hole to the closest board image), and torpedo actuation.

    The torpedo task uses a forward-facing ZED camera, unlike the dropper/grabber
    tasks which use the downfacing camera. Key differences:
      - ZED stereo depth gives the distance to the board directly (no pressure-sensor trick).
      - Image x_norm error → sub strafe (y), image y_norm error → sub heave (z).
      - FOV-based trig converts normalized pixel error to metric error in meters.
    Keep this file free of FSM state logic — that belongs in torpedo_fsm.py.
"""

# VISION CLASS LABELS (FIXME: confirm these match the trained model's class names) ---------------
# The torpedo board is always search_and_rescue. Each image label is spatially
# associated with a specific hole size on the board:
#   blood     → next to the large hole  (torpedo 1)
#   ambulance → next to the small hole  (torpedo 2)
LARGE_HOLE_IMAGE_LABEL = "blood"       # FIXME: confirm with trained model
SMALL_HOLE_IMAGE_LABEL = "ambulance"   # FIXME: confirm with trained model
LARGE_HOLE_LABEL       = "large_hole"  # FIXME: confirm with trained model
SMALL_HOLE_LABEL       = "small_hole"  # FIXME: confirm with trained model

# STANDOFF DISTANCE MODES (competition scoring: farther = more points) ---------------------------
DISTANCE_MODES = {
    "close":  0.25,  # no bonus
    "medium": 0.30,  # ~1 ft, far bonus
    "far":    0.46,  # ~1.5 ft, farther bonus (extra points)
}
DEFAULT_DISTANCE_MODE = "medium"

# FORWARD-CAMERA MOTION CONTROL ------------------------------------------------------------------
# All gains/clamps apply to forward ZED camera (x=forward, y=strafe, z=heave).
FWD_GAIN     = 0.4   # forward/back proportional gain to reach standoff distance
STRAFE_GAIN  = 0.4   # left/right gain to center the hole horizontally
HEAVE_GAIN   = 0.4   # up/down gain to center the hole vertically

MAX_FWD_CMD    = 0.3  # meters per tick, clamped forward/back command
MAX_STRAFE_CMD = 0.3  # meters per tick, clamped strafe command
MAX_HEAVE_CMD  = 0.2  # meters per tick, clamped heave command

DIST_TOLERANCE_M = 0.10  # how close to standoff distance before counting as "at range"


class TorpedoHelpers:
    """
    Helper functions for torpedo board detection, hole association,
    forward-camera alignment, and torpedo actuation.
    """
    def __init__(self, shared_memory_object, signal_wrapper=None,
                 weights_path: str = "models/best.pt",
                 tube_offset_body: tuple = (0.0, 0.0),
                 camera_id: int | None = None,
                 fov_x_deg: float = 90.0,
                 fov_y_deg: float = 60.0,
                 distance_mode: str = DEFAULT_DISTANCE_MODE):
        self.shared_memory = shared_memory_object
        self.signal_wrapper = signal_wrapper  # SignalWrapper or None for safe print placeholders

        # vision, opened lazily so importing/constructing this class doesn't
        # require camera/YOLO hardware to be present (e.g. FAKE_INPUT testing)
        # FIXME: confirm weights file exists and is trained on the torpedo classes above
        self.weights_path = weights_path
        self.camera_id = camera_id
        self._camera = None
        self._model = None

        # FIXME: tube_offset_body (body frame, meters) is unmeasured. Tape-measure, sub level:
        # forward/aft (x) and left/right (y) distance between the forward ZED camera's
        # optical center and the torpedo tube exit point. 0.0 means no correction.
        self.tube_offset_body = tube_offset_body

        # FOV for metric error computation (see compute_alignment_error)
        self.fov_x_rad = math.radians(fov_x_deg)
        self.fov_y_rad = math.radians(fov_y_deg)

        # standoff distance (meters) the sub should maintain from the board
        self.standoff_m = DISTANCE_MODES.get(distance_mode, DISTANCE_MODES[DEFAULT_DISTANCE_MODE])

        # rolling tracking state
        self.detection_history = []
        self.last_valid_detection = None
        self.last_detection_time = 0.0
        self.centered_since = None  # time.time() when the hole first became centered, None if not

        # debug info, updated every align_step() call, read by the test controller
        self.debug = {
            "x_error": 0.0, "y_error": 0.0, "dist_error": 0.0,
            "stable": False, "centered": False, "dwell_ok": False,
            "lost": False, "current_hole": LARGE_HOLE_LABEL,
        }

    def get_target_detections(self) -> list:
        """
        Runs the live forward ZED camera vision pipeline and returns one frame
        of detections in this format:
            [class_label, class_id, conf, x_norm, y_norm, depth_m, width, height]

        Camera + model opened lazily on first call so the constructor is safe
        to call even without camera hardware present.
        """
        if self._camera is None:
            self._camera = camera("zed", camera_id=self.camera_id)
        if self._model is None:
            self._model = yolo(self.weights_path)

        detections = self._model.infer(self._camera, headless=True, verbose=False)
        return convert_vision_runtime_detections(detections)

    def get_image_label_for_torpedo(self, torpedo_num: int) -> str:
        """
        Returns which board image label anchors the target hole for the given torpedo:
            torpedo 1 → LARGE_HOLE_IMAGE_LABEL (blood)
            torpedo 2 → SMALL_HOLE_IMAGE_LABEL (ambulance)
        """
        return LARGE_HOLE_IMAGE_LABEL if torpedo_num == 1 else SMALL_HOLE_IMAGE_LABEL

    def find_board_image(self, detections: list, image_label: str):
        """
        Returns the highest-confidence detection matching image_label, or None.
        Used to anchor hole association — we find which hole is spatially
        closest to the given board image marking.
        """
        matches = filter_detections_by_label(detections, image_label)
        if not matches:
            return None
        return max(matches, key=lambda d: d[2])  # highest confidence

    def find_closest_hole(self, detections: list, hole_label: str, reference):
        """
        Among all hole_label detections, returns the one spatially closest
        (in normalized image space) to reference's center (x_norm, y_norm).
        Returns None if no matching holes are found or reference is None.

        This is how the FSM selects which large/small hole belongs to the
        board image on the current side, instead of just picking the first
        detection arbitrarily.
        """
        if reference is None:
            return None
        matches = filter_detections_by_label(detections, hole_label)
        if not matches:
            return None
        ref_x, ref_y = reference[X_NORM], reference[Y_NORM]
        return min(matches, key=lambda d: (d[X_NORM] - ref_x) ** 2 + (d[Y_NORM] - ref_y) ** 2)

    def reset_tracking(self) -> None:
        """
        Clears all rolling tracking state. Call this when switching to a new
        hole target so old frames/timers don't carry over.
        """
        self.detection_history = []
        self.last_valid_detection = None
        self.last_detection_time = 0.0
        self.centered_since = None

    def record_detection(self, detection) -> None:
        """
        Appends a detection to the rolling history for stability checking and
        center smoothing, capped at VERIFY_FRAME_COUNT frames.
        """
        self.detection_history.append(detection)
        if len(self.detection_history) > VERIFY_FRAME_COUNT:
            self.detection_history.pop(0)
        self.last_valid_detection = detection
        self.last_detection_time = time.time()

    def check_target_stable(self, detection) -> bool:
        """
        Records a detection and checks if recent history forms a stable target
        (REQUIRED_STABLE_FRAMES frames at IOU_MIN). Same pattern as dropper/grabber.
        """
        self.record_detection(detection)
        stable = is_stable_target(self.detection_history)
        self.debug["stable"] = stable
        return stable

    def check_target_verified(self, detection) -> bool:
        """
        Stricter final-verify pass: VERIFY_FRAME_COUNT frames at VERIFY_IOU_MIN.
        """
        self.record_detection(detection)
        verified = is_stable_target(self.detection_history, required_frames=VERIFY_FRAME_COUNT, iou_min=VERIFY_IOU_MIN)
        self.debug["stable"] = verified
        return verified

    def is_target_lost(self) -> bool:
        """
        True if the hole hasn't been seen for longer than TARGET_LOST_TIMEOUT.
        """
        return target_lost_too_long(self.last_detection_time)

    def compute_alignment_error(self, hole_detection) -> tuple:
        """
        Returns (x_err_m, y_err_m, dist_err_m): how far the sub needs to
        move to center the torpedo tube on the hole at the standoff distance.

        Unlike the downfacing camera (which uses pressure-sensor depth + pinhole
        back-projection), the forward ZED provides stereo depth directly at any
        pixel, so we read depth_m from the SDK and use FOV-based trig:
            x_err_m: positive → hole is to the right of the tube, sub strafes right
            y_err_m: positive → hole is above the tube, sub heaves up (decreases depth)
            dist_err_m: positive → sub is too far from board, sub moves forward

        Tube offset correction: the torpedo exits from tube_offset_body, not from the
        camera optical center. Correcting for it here shifts the target pixel
        position by the angular equivalent of the physical tube offset at the
        current standoff distance.
        """
        x_norm = hole_detection[X_NORM]
        y_norm = hole_detection[Y_NORM]

        # read ZED stereo depth at the hole center; fall back to standoff if invalid
        depth_m = self._camera.depth(x_norm, y_norm) if self._camera is not None else self.standoff_m
        if depth_m <= 0 or not math.isfinite(depth_m):
            depth_m = self.standoff_m

        # FOV-based metric error from image center to hole center
        # (x_norm=0.5 → straight ahead, y_norm=0.5 → center height)
        raw_x_err = depth_m * (x_norm - 0.5) * 2.0 * math.tan(self.fov_x_rad / 2.0)
        raw_y_err = depth_m * (y_norm - 0.5) * 2.0 * math.tan(self.fov_y_rad / 2.0)

        # apply tube offset (body frame, meters → same units as raw error)
        # tube_offset_body[0] = forward offset (x): doesn't affect strafe/heave centering
        # tube_offset_body[1] = lateral offset (y): shifts where the tube points left/right
        x_err_m = raw_x_err - self.tube_offset_body[1]
        y_err_m = raw_y_err  # vertical offset between camera/tube not measured, FIXME if needed

        dist_err_m = depth_m - self.standoff_m

        return x_err_m, y_err_m, dist_err_m

    def apply_motion_commands(self, x_err_m: float, y_err_m: float, dist_err_m: float) -> None:
        """
        Converts metric alignment errors (from compute_alignment_error) into
        sub motion commands for the forward-facing camera case:
            dist_err_m → forward/back   (target_x nudge)
            x_err_m    → strafe         (target_y nudge)
            y_err_m    → heave          (target_z nudge, sign: positive y_err = hole above = go up = lower depth)

        All commands are clamped to avoid aggressive motion.
        """
        fwd_cmd    = clamp_motion_command(FWD_GAIN    * dist_err_m, MAX_FWD_CMD)
        strafe_cmd = clamp_motion_command(STRAFE_GAIN * x_err_m,    MAX_STRAFE_CMD)
        heave_cmd  = clamp_motion_command(HEAVE_GAIN  * y_err_m,    MAX_HEAVE_CMD)

        sm = self.shared_memory
        sm.target_x.value = sm.dvl_x.value + fwd_cmd
        sm.target_y.value = sm.dvl_y.value + strafe_cmd
        # depth convention: higher depth value = deeper. y_err positive means
        # hole is above center → sub needs to go up → subtract from target_z
        sm.target_z.value = sm.dvl_z.value - heave_cmd

    def align_step(self, hole_label: str, image_label: str, x_tolerance: float, y_tolerance: float) -> dict:
        """
        Runs one tick of forward-camera alignment toward the target hole:
            1. fetch a fresh frame of detections
            2. find the board image; use it to associate the closest hole of hole_label
            3. if briefly lost, hold position and wait for reappearance
            4. if lost too long, report lost so the FSM can go back to searching
            5. smooth the hole center over recent frames to reduce noise
            6. compute metric errors (strafe, heave, forward/back) via ZED depth + FOV trig
            7. apply motion commands (nudge target_x/y/z)
            8. track centered dwell time

        Returns: {target, centered, at_range, dwell_ok, lost}
            target   — the raw hole detection (or None if lost)
            centered — True when x/y errors are within tolerance
            at_range — True when the sub is within DIST_TOLERANCE_M of standoff
            dwell_ok — True when centered+at_range have both held for REQUIRED_CENTER_TIME
            lost     — True when the hole hasn't been seen for TARGET_LOST_TIMEOUT seconds
        """
        detections = self.get_target_detections()
        board_image = self.find_board_image(detections, image_label)
        detection = self.find_closest_hole(detections, hole_label, board_image)

        if detection is not None:
            self.record_detection(detection)
        elif self.is_target_lost():
            self.debug["lost"] = True
            return {"target": None, "centered": False, "at_range": False, "dwell_ok": False, "lost": True}
        else:
            # briefly lost — hold position, keep using last known state
            stop_vehicle_motion(self.shared_memory)
            self.debug["lost"] = False
            return {"target": self.last_valid_detection, "centered": False, "at_range": False, "dwell_ok": False, "lost": False}

        self.debug["lost"] = False

        smoothed_center = average_target_center(self.detection_history)
        smoothed_detection = list(detection)
        smoothed_detection[X_NORM] = smoothed_center[0]
        smoothed_detection[Y_NORM] = smoothed_center[1]

        x_err_m, y_err_m, dist_err_m = self.compute_alignment_error(smoothed_detection)
        self.debug["x_error"]    = x_err_m
        self.debug["y_error"]    = y_err_m
        self.debug["dist_error"] = dist_err_m

        self.apply_motion_commands(x_err_m, y_err_m, dist_err_m)

        centered_now = is_target_centered_metric(x_err_m, y_err_m, x_tolerance, y_tolerance)
        at_range_now = abs(dist_err_m) <= DIST_TOLERANCE_M
        fully_aligned = centered_now and at_range_now

        if fully_aligned:
            if self.centered_since is None:
                self.centered_since = time.time()
        else:
            self.centered_since = None

        dwell_ok = has_required_center_time(self.centered_since)

        self.debug["centered"] = centered_now
        self.debug["dwell_ok"] = dwell_ok

        return {
            "target":   detection,
            "centered": centered_now,
            "at_range": at_range_now,
            "dwell_ok": dwell_ok,
            "lost":     False,
        }

    def fire_torpedo(self, torpedo_num: int) -> None:
        """
        Fires torpedo torpedo_num (1 or 2) via the SignalWrapper. Prints a safe
        placeholder if no SignalWrapper was passed in (e.g. test mode).
        FIXME: confirm signal_wrapper.fire_torpedo() accepts a torpedo number
        and that the SignalWrapper's actuation sequence matches hardware.
        """
        if self.signal_wrapper is not None:
            self.signal_wrapper.fire_torpedo(torpedo_num)
        else:
            print(f"TORPEDO FIRE PLACEHOLDER — torpedo_num={torpedo_num} (no SignalWrapper attached)")

    def get_hole_label_for_torpedo(self, torpedo_num: int) -> str:
        """
        Returns which hole label to target for the given torpedo number.
        Torpedo 1 → large hole (max-points sequence: large first).
        Torpedo 2 → small hole.
        """
        if torpedo_num == 1:
            return LARGE_HOLE_LABEL
        return SMALL_HOLE_LABEL
