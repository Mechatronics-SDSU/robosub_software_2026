import os
import time
import yaml

from modules.vision.vision_model_main import camera, yolo
from modules.vision.dropper_flip_vision import FlipAwareYOLO
from modules.vision.target_box_helpers import (
    CLASS_ID,
    CONF,
    VERIFY_FRAME_COUNT,
    VERIFY_IOU_MIN,
    SAME_BIN_RADIUS_M,
    MAX_OBJECT_YAML_ERROR_M,
    REQUIRED_STABLE_FRAMES,
    IOU_MIN,
    MIN_CONFIDENCE,
    FrameGate,
    is_stable_target,
    get_box_edges,
    get_box_center,
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
    Helper functions for the dropper FSM (fsm/dropper_fsm.py).
    Handles bin target selection, target verification, role bin labels,
    downward-camera alignment, world-position estimation/sanity-checking,
    completed-bin memory, and dropper actuation. Keep repeated dropper logic
    here instead of inside the FSM.
"""

# ROLE BIN LABELS, these already exist as trained vision classes-----------------------------------------------------------------
SURVEY_AND_REPAIR_LABEL = "fire"
SEARCH_AND_RESCUE_LABEL = "blood"

# ROLE BIN CLASS IDS (ids are what the mission FSM configures - labels drift between weights files)
FIRE_ID  = 1 # survey_and_repair bin image
BLOOD_ID = 3 # search_and_rescue bin image

# DROPPER ACTUATION TIMING--------------------------------------------------------------------------------------------------
DROPPER_SPIN_TIME_SEC = 0.5 # how long to spin the dropper to release one marker


class ZoomCamera:
    """
    Digital-zoom camera wrapper for the dropper search: center-crops every
    grabbed frame by the current `zoom` factor so small bins occupy more
    pixels at YOLO's fixed input size - NO physical movement involved (the
    sub can't do small movements reliably; this is the "zoom in to see"
    mechanism). No upscale: YOLO letterboxes to imgsz anyway, and upscaling
    adds no information.

    Detections made on a zoomed frame are in CROP coordinates - the caller
    (DropperHelpers.get_target_detections) maps them back to true full-frame
    normalized coordinates, because the fisheye back-projection math in
    target_box_helpers.py only speaks full-frame coords. Safe to hand to
    FlipAwareYOLO: its flip shim mirrors the crop, un-mirrors in crop space,
    then the zoom unmap composes on top - both transforms stay exact.
    """

    def __init__(self, inner):
        self._inner = inner
        self.zoom = 1.0

    def _grab_with_pc(self):
        frame, point_cloud = self._inner._grab_with_pc()
        if frame is None or self.zoom <= 1.0:
            return frame, point_cloud
        h, w = frame.shape[:2]
        cw, ch = max(2, int(w / self.zoom)), max(2, int(h / self.zoom))
        x0, y0 = (w - cw) // 2, (h - ch) // 2
        return frame[y0:y0 + ch, x0:x0 + cw], None # point cloud coords wouldn't match the crop

    def grab(self):
        return self._grab_with_pc()[0]

    def depth(self, x_norm, y_norm):
        return -1.0 # downfacing camera has no depth anyway

    def close(self):
        self._inner.close()


class DropperHelpers:
    """
    Helper functions for dropper bin selection, downward-camera lineup,
    world-position estimation, and dropper actuation.
    """
    def __init__(self, shared_memory_object, signal_wrapper=None, weights_path: str = "models/best.pt",
                 dropper_offset_body: tuple = (0.0, 0.0), same_bin_radius: float = SAME_BIN_RADIUS_M,
                 camera_source: str = "downfacing", conf_min: float = 0.50, imgsz: int = 640,
                 stable_frames: int = REQUIRED_STABLE_FRAMES, stable_iou: float = IOU_MIN,
                 conf_strict: float = MIN_CONFIDENCE, class_swap_wait: float = 0.2, center_outlier_iqr: float = 1.5):
        self.shared_memory = shared_memory_object
        self.signal_wrapper = signal_wrapper # real SignalWrapper (modules/signals/SignalWrapper.py), or None for safe print placeholders

        # FRAME-GATE / STANDARDIZED KNOBS (the mission FSM feeds these from objects.yaml) --------
        # a target only counts after stable_frames consecutive same-class frames, each at
        # conf >= conf_strict, consecutive IoU >= stable_iou, AND a non-empty common
        # intersection of all boxes; aim = median center after the IQR outlier drop
        self.stable_frames = max(1, int(stable_frames))
        self.stable_iou = stable_iou
        self.conf_strict = conf_strict
        self.class_swap_wait = class_swap_wait # settle once when the YOLO classes filter changes (first inference lags)
        self.center_outlier_iqr = center_outlier_iqr # drop centers farther than this x IQR from the median
        self._last_classes = None

        # the standardized multi-frame gate (target_box_helpers.FrameGate) - mission FSM path;
        # the legacy align API below keeps its own tracking state
        self._gate = FrameGate(self.stable_frames, self.stable_iou, self.conf_strict, self.center_outlier_iqr)

        # vision, opened lazily so importing this file doesn't require camera/YOLO hardware to be present
        # FIXME: confirm this weights file actually exists on the sub and is trained on the
        # "fire"/"blood" classes (see SURVEY_AND_REPAIR_LABEL/SEARCH_AND_RESCUE_LABEL below).
        # model_weights and dropper_offset are passed in from Dropper_FSM's constructor,
        # which reads them from config/hardware.yaml (not objects.yaml).
        self.weights_path = weights_path
        self.camera_source = camera_source
        self.conf_min = conf_min
        self.imgsz = imgsz
        self._camera = None
        self._model = None

        # FIXME: dropper_offset_body (body frame, meters) is unmeasured, 0.0 means no correction applied.
        # Measure with a tape measure, sub level: forward/aft distance (x) and left/right
        # distance (y) between the camera's optical center and the dropper's release point.
        # Height (z) doesn't matter here, only the horizontal offset. Set in config/hardware.yaml.
        self.dropper_offset_body = dropper_offset_body
        self.same_bin_radius = same_bin_radius

        self.detection_history = []
        self.last_valid_detection = None
        self.last_detection_time = 0.0
        self.centered_since = None # time.time() of when the target first became centered, None if not centered

        self.bin_world = None # last estimated bin world position (x, y), set by align_step
        self.completed_bins = [] # list of (x, y) world positions already dropped into

        # debug info, updated every align_step() call, read by the test controller
        self.debug = {
            "x_error": 0.0, "y_error": 0.0, "stable": False,
            "centered": False, "dwell_ok": False, "lost": False, "rejected": False,
        }

    def get_bin_label(self, role: str) -> str:
        """
        Returns the vision class label for the bin matching the given role.
        """
        if role == "search_and_rescue":
            return SEARCH_AND_RESCUE_LABEL
        return SURVEY_AND_REPAIR_LABEL # default to survey_and_repair

    def get_bin_ids(self, role: str) -> list:
        """
        Returns BOTH bin class ids ordered by preference for the given role -
        the correct bin first (scores more), the other after (any bin still
        scores). The mission FSM filters YOLO to both and narrows acceptance
        by role_patience.
        """
        if role == "search_and_rescue":
            return [BLOOD_ID, FIRE_ID]
        return [FIRE_ID, BLOOD_ID] # default to survey_and_repair

    def _ensure_vision(self) -> None:
        if self._camera is None:
            self._camera = ZoomCamera(camera(self.camera_source))
        if self._model is None:
            self._model = FlipAwareYOLO(yolo(self.weights_path, conf=self.conf_min, imgsz=self.imgsz))

    def set_zoom(self, zoom: float) -> None:
        """
        Sets the digital zoom factor (1.0 = full frame). Purely a crop before
        inference - the sub does not move. Resets the frame gate, since boxes
        from different zoom levels must never share a stability window.
        """
        self._ensure_vision()
        self._camera.zoom = max(1.0, float(zoom))
        self.gate_reset()

    def _settle_on_class_swap(self, classes: list) -> None:
        """
        Sleeps class_swap_wait once whenever the YOLO classes filter changes -
        the first inference after a swap lags; steady-state stays snappy.
        """
        key = tuple(sorted(classes)) if classes else None
        if self._last_classes != key:
            self._last_classes = key
            if self.class_swap_wait > 0:
                time.sleep(self.class_swap_wait)

    def verify_model_classes(self, required_ids: list) -> list:
        """
        Loads the model (not the camera) and returns whichever required class
        ids the weights file can NOT produce - the FSM logs the result loudly
        at start.
        """
        if self._model is None:
            self._model = FlipAwareYOLO(yolo(self.weights_path, conf=self.conf_min, imgsz=self.imgsz))
        names = self._model._model._model.names or {} # FlipAwareYOLO -> YOLOModel -> ultralytics
        return sorted(set(required_ids) - set(int(k) for k in names))

    def get_target_detections(self, classes: list = None) -> list:
        """
        Runs the live downward-camera vision pipeline
        (modules/vision/vision_model_main.py, through FlipAwareYOLO and the
        digital-zoom crop) and returns one frame of detections in this format:
            [class_label, class_id, conf, x_norm, y_norm, depth_m, width, height]

        classes: optional class-id list handed to YOLO itself (runtime filter).
        Coordinates are ALWAYS true full-frame normalized values - detections
        made on a zoomed crop are mapped back here, so the fisheye
        back-projection math downstream stays valid at any zoom.

        Camera + model are opened lazily on first call (not in __init__), so
        importing/constructing this class doesn't require the camera/YOLO
        dependencies to be present (e.g. FAKE_INPUT testing).
        """
        self._ensure_vision()
        self._settle_on_class_swap(classes)
        detections = self._model.infer(self._camera, headless=True, verbose=False, classes=classes)
        converted = convert_vision_runtime_detections(detections)
        zoom = getattr(self._camera, "zoom", 1.0)
        if zoom > 1.0:
            for det in converted: # crop -> full frame: x_full = 0.5 + (x_crop - 0.5)/z, sizes /= z
                det[3] = round(min(1.0, max(0.0, 0.5 + (det[3] - 0.5) / zoom)), 3) # x_norm
                det[4] = round(min(1.0, max(0.0, 0.5 + (det[4] - 0.5) / zoom)), 3) # y_norm
                det[6] = round(det[6] / zoom, 3) # width
                det[7] = round(det[7] / zoom, 3) # height
        return converted

    # FRAME GATE (mission FSM path) ------------------------------------------------------------------------------------------
    # The gate itself is the shared target_box_helpers.FrameGate (one implementation for every
    # FSM); these thin wrappers keep DropperHelpers' public API stable.

    @property
    def empty_streak(self) -> int:
        return self._gate.empty_streak

    def gate_reset(self) -> None:
        """
        Clears the frame-gate window and the empty-frame streak. Call when a
        search (re)starts, the zoom level changes, or a move completes.
        """
        self._gate.reset()

    def _common_intersection_ok(self, window: list) -> bool:
        return self._gate.common_intersection_ok(window)

    def _robust_center(self, centers: list) -> tuple:
        return self._gate.robust_center(centers)

    def gate_feed(self, detections: list, accept_ids: list) -> dict:
        """
        One frame into the shared gate - see target_box_helpers.FrameGate.feed
        for the verdict contract.
        """
        return self._gate.feed(detections, accept_ids)

    # STEP-MOVE MATH (mission FSM path) --------------------------------------------------------------------------------------
    def _sub_depth(self) -> float:
        """
        Current sub depth (meters, positive down). Reads the DVL's z instead
        of the pressure sensor (shared_memory.depth) because only the DVL is
        working right now - when the switchable depth-source config lands,
        this is the ONLY line to change for the dropper.
        """
        return self.shared_memory.dvl_z.value

    def compute_move_target(self, aim_center: tuple, target_depth: float) -> tuple:
        """
        One absolute world (x, y) that parks the DROPPER (not the camera) over
        the aim point: back-project the normalized aim through the fisheye
        intrinsics at the DVL-measured vertical distance, rotate to world by
        yaw, subtract the rotated dropper offset. The FSM commands this in a
        single move (no nudging - the sub can't do small movements), settles,
        then re-confirms.
        """
        x_error_m, y_error_m = get_target_error_meters(aim_center[0], aim_center[1], self._sub_depth(), target_depth)
        bin_world = self.estimate_bin_world_position(x_error_m, y_error_m)
        self.bin_world = bin_world
        return self.compute_dropper_alignment_target(bin_world)

    def aim_error_m(self, aim_center: tuple, target_depth: float) -> tuple:
        """
        (x, y) meters between the dropper's release point and the aim point
        right now - the CONFIRM state's drop-tolerance check.
        """
        dropper_target = self.compute_move_target(aim_center, target_depth)
        return dropper_target[0] - self.shared_memory.dvl_x.value, dropper_target[1] - self.shared_memory.dvl_y.value

    def release_markers(self, count: int = 2, gap_s: float = 1.0) -> None:
        """
        Releases `count` markers back-to-back (single-bin strategy: both balls
        in the one confirmed bin), one spin_dropper(DROPPER_SPIN_TIME_SEC) per
        ball with gap_s between spins. Safe print placeholder without hardware.
        """
        for ball in range(count):
            if self.signal_wrapper is not None:
                self.signal_wrapper.spin_dropper(DROPPER_SPIN_TIME_SEC)
            else:
                print(f"DROPPER SPIN PLACEHOLDER {ball + 1}/{count} (no SignalWrapper attached)")
            if ball < count - 1:
                time.sleep(gap_s)
        if self.bin_world is not None:
            self.completed_bins.append(self.bin_world)

    # LEGACY CONTINUOUS-SERVO API below - still used by fsm/dropper_test_fsm.py and
    # fsm/lineup_test_fsm.py bench tools. The mission FSM (fsm/dropper_fsm.py) uses the
    # frame-gate + step-move API above instead.

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
        self.bin_world = None

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
        Checks if the bin hasn't been seen recently enough to keep tracking it.
        """
        return target_lost_too_long(self.last_detection_time)

    def is_too_close_to_completed(self, candidate_world: tuple) -> bool:
        """
        Checks if a candidate bin world position is too close to a bin
        that's already been dropped into, so we don't drop both markers in
        the same bin.
        """
        return any(distance_2d(candidate_world, completed) < self.same_bin_radius for completed in self.completed_bins)

    def estimate_bin_world_position(self, x_error_body: float, y_error_body: float) -> tuple:
        """
        Converts a body-frame vision error into a world-frame bin position
        estimate: sub_world_position + rotate(vision_offset_body, yaw).
        """
        sub_world = (self.shared_memory.dvl_x.value, self.shared_memory.dvl_y.value)
        yaw_deg = self.shared_memory.dvl_yaw.value
        x_offset_world, y_offset_world = body_offset_to_world_offset(x_error_body, y_error_body, yaw_deg)
        return sub_world[0] + x_offset_world, sub_world[1] + y_offset_world

    def validate_against_assumed(self, bin_world: tuple, assumed_bin_world: tuple, max_error: float = MAX_OBJECT_YAML_ERROR_M) -> bool:
        """
        Sanity-checks a vision-derived bin world position against the
        objects.yaml assumed location, so a bad detection (wrong bin, noisy
        estimate) doesn't get treated as ground truth.
        """
        return distance_2d(bin_world, assumed_bin_world) <= max_error

    def compute_dropper_alignment_target(self, bin_world: tuple) -> tuple:
        """
        Returns the world-frame sub position that puts the dropper (not the
        downward camera) over the bin center:
            desired_sub_world = bin_world - rotate(dropper_offset_body, yaw)
        """
        yaw_deg = self.shared_memory.dvl_yaw.value
        dropper_offset_world = body_offset_to_world_offset(self.dropper_offset_body[0], self.dropper_offset_body[1], yaw_deg)
        return bin_world[0] - dropper_offset_world[0], bin_world[1] - dropper_offset_world[1]

    def align_step(self, bin_label: str, target_depth: float, desired_height: float, x_tolerance: float, y_tolerance: float,
                    assumed_bin_world: tuple = None, max_object_yaml_error: float = MAX_OBJECT_YAML_ERROR_M) -> dict:
        """
        Runs one tick of downward-camera alignment toward the bin, using the
        camera + pressure sensor depth (no ZED/stereo depth here):
            1. fetch a fresh detection matching bin_label
            2. if briefly lost, hold position and wait for it to reappear
            3. if lost too long, report lost so the FSM can go back to searching
            4. otherwise smooth the box center over recent frames, back-project
               it to a metric body-frame x/y error using target_depth
            5. estimate the bin's world position (DVL + yaw rotation) and
               sanity-check it against the objects.yaml assumed location and
               against already-completed bins; reject if either check fails
            6. compute the dropper (not camera) alignment target and nudge
               toward it; target_z is set directly from target_depth/
               desired_height (heave doesn't come from the image at all here)
            7. track how long the bin has stayed centered (dwell time)

        Returns a dict of results/debug info:
            target, bin_world, centered, dwell_ok, lost, rejected
        """
        detections = self.get_target_detections()
        detection = get_target_detection(detections, bin_label)

        if detection is not None:
            self.record_detection(detection)
        elif self.is_target_lost():
            self.debug["lost"] = True
            return {"target": None, "bin_world": None, "centered": False, "dwell_ok": False, "lost": True, "rejected": False}
        else:
            # briefly lost, hold position, keep using the last known target
            stop_vehicle_motion(self.shared_memory)
            self.debug["lost"] = False
            return {"target": self.last_valid_detection, "bin_world": self.bin_world, "centered": False, "dwell_ok": False, "lost": False, "rejected": False}

        self.debug["lost"] = False

        # smooth the center position over recent frames to reduce single-frame noise
        smoothed_center = average_target_center(self.detection_history)
        sub_depth = self._sub_depth() # DVL z (pressure sensor is down, see _sub_depth)

        x_error_m, y_error_m = get_target_error_meters(smoothed_center[0], smoothed_center[1], sub_depth, target_depth)
        self.debug["x_error"], self.debug["y_error"] = x_error_m, y_error_m

        bin_world = self.estimate_bin_world_position(x_error_m, y_error_m)
        self.bin_world = bin_world

        if assumed_bin_world is not None and not self.validate_against_assumed(bin_world, assumed_bin_world, max_object_yaml_error):
            self.debug["rejected"] = True
            self.centered_since = None
            return {"target": detection, "bin_world": bin_world, "centered": False, "dwell_ok": False, "lost": False, "rejected": True}

        if self.is_too_close_to_completed(bin_world):
            self.debug["rejected"] = True
            self.centered_since = None
            return {"target": detection, "bin_world": bin_world, "centered": False, "dwell_ok": False, "lost": False, "rejected": True}

        self.debug["rejected"] = False

        dropper_target_world = self.compute_dropper_alignment_target(bin_world)
        sub_world = (self.shared_memory.dvl_x.value, self.shared_memory.dvl_y.value)
        dropper_x_error = dropper_target_world[0] - sub_world[0]
        dropper_y_error = dropper_target_world[1] - sub_world[1]

        nudge_xy_toward_target(self.shared_memory, dropper_x_error, dropper_y_error)
        set_hover_depth(self.shared_memory, target_depth, desired_height)

        centered_now = is_target_centered_metric(dropper_x_error, dropper_y_error, x_tolerance, y_tolerance)
        if centered_now:
            if self.centered_since is None:
                self.centered_since = time.time()
        else:
            self.centered_since = None

        self.debug["centered"] = centered_now
        self.debug["dwell_ok"] = has_required_center_time(self.centered_since)

        return {
            "target": detection,
            "bin_world": bin_world,
            "centered": centered_now,
            "dwell_ok": self.debug["dwell_ok"],
            "lost": False,
            "rejected": False,
        }

    def release_marker(self) -> None:
        """
        Releases one marker by spinning the dropper for DROPPER_SPIN_TIME_SEC
        via the SignalWrapper, which handles its own timing and re-closes the
        dropper when the call returns. Prints a safe placeholder if no
        SignalWrapper was passed in (no hardware attached, e.g. test mode).
        Saves the just-dropped bin's world position so the second marker
        search rejects candidates near it.
        """
        if self.signal_wrapper is not None:
            self.signal_wrapper.spin_dropper(DROPPER_SPIN_TIME_SEC)
        else:
            print("DROPPER SPIN PLACEHOLDER (no SignalWrapper attached)")

        if self.bin_world is not None:
            self.completed_bins.append(self.bin_world)
