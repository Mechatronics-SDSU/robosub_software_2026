import time

from modules.vision.vision_model_main import camera, yolo
from modules.vision.target_box_helpers import (
    CLASS_ID,
    CONF,
    X_NORM,
    Y_NORM,
    WIDTH,
    CAMERA_FX_NORM,
    VERIFY_FRAME_COUNT,
    VERIFY_IOU_MIN,
    REQUIRED_STABLE_FRAMES,
    IOU_MIN,
    MAX_OBJECT_YAML_ERROR_M,
    is_confident_detection,
    is_stable_target,
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
    Handles item/basket target selection BY CLASS ID, target verification,
    downward-camera alignment (with an optional lateral placement offset),
    the carry monitor (did the item silently slip out of the claw?), the
    lift-and-look grab verification, world-position estimation/sanity-
    checking, claw actuation, the rotation bonus, and icon facing (vision
    scan with a heading fallback). Keep repeated grabber logic here instead
    of inside the FSM.
"""

# CLASS IDS (2026 15-class weights)-----------------------------------------------------------------------------------------------
# FIXME: modules/vision/models/best.pt is still the OLD 4-class model
# (firetruck, fire, ambulance, blood) - these ids only exist once the new
# 15-class weights from Mechatronics_Vision_2026 land on the sub. The FSM
# calls verify_model_classes() at start and logs loudly until then.
CLASS_LABELS = {
    4: "bandaid", 5: "electric", 6: "nutbolt", 7: "pill",
    8: "redcross", 9: "repair", 10: "rescue", 11: "search",
    12: "survey", 13: "warning",
}

DEFAULT_ITEM_IDS   = [5, 6, 4, 7]              # electric, nutbolt, bandaid, pill (center table)
DEFAULT_ITEM_TO_BIN = {5: 13, 6: 13, 4: 8, 7: 8} # warning basket takes 5/6, redcross basket takes 4/7

# icons hanging from the octagon edge, by how many items ended up in baskets
# (handbook 3.2.6: 1 item -> point at survey/rescue, 2+ -> repair/search;
# either role's icon counts, so the vision scan looks for both ids at once)
ONE_ITEM_ICON_IDS = [12, 10]  # survey, rescue
TWO_ITEM_ICON_IDS = [9, 11]   # repair, search

# FIXME: placeholder headings (degrees) per icon class id, update with real
# measured headings inside the octagon once known - only used as the fallback
# when the vision icon scan can't find anything
ICON_HEADINGS = {9: 0, 10: 0, 11: 0, 12: 0}

# ROTATION BONUS (section 3.2.6: rotate once per item placed in the basket)------------------------------------------------------
# Stepped in quarter-turns rather than one large target_yaw jump, because
# target_yaw is compared directly against a wrapped 0-360 degree dvl_yaw with
# no multi-revolution unwrapping - a single +720 degree setpoint would never
# resolve as "reached".
ROTATION_STEP_DEGREES = 90
ROTATION_STEP_TOLERANCE_DEG = 5.0


def filter_detections_by_class_id(detections: list, class_id: int) -> list:
    """
    Filters the detection list down to ones matching the given class id.
    Id-based on purpose - label strings drift between weights files, ids are
    what objects.yaml configures.
    """
    return [detection for detection in detections if detection[CLASS_ID] == class_id]


class GrabberHelpers:
    """
    Helper functions for grabber item/basket selection, downward-camera
    lineup, world-position estimation, claw actuation, carry/grab
    verification, the rotation bonus, and icon facing.
    """
    def __init__(self, shared_memory_object, signal_wrapper=None, weights_path: str = "models/best.pt",
                 claw_offset_body: tuple = (0.0, 0.0), camera_rotate_180: bool = False,
                 stable_frames: int = REQUIRED_STABLE_FRAMES, stable_iou: float = IOU_MIN, class_swap_wait: float = 0.2):
        self.shared_memory = shared_memory_object
        self.signal_wrapper = signal_wrapper # real SignalWrapper (modules/signals/SignalWrapper.py), or None for safe print placeholders

        # stability contract: a target/sighting only counts after stable_frames consecutive
        # frames of the same class at stable_iou positional overlap (default 4 frames @ 60%).
        # Used EVERYWHERE a detection gates an action: item/basket targeting, the carry
        # monitor, and the lift-and-look grab verification.
        self.stable_frames = max(1, int(stable_frames))
        self.stable_iou = stable_iou
        # swapping the YOLO classes filter lags the first inference after the swap - settle
        # briefly on a swap (and only on a swap, so steady-state stays snappy)
        self.class_swap_wait = class_swap_wait
        self._last_classes = {} # camera role ("down"/"front") -> last classes list used

        # vision, opened lazily so importing this file doesn't require camera/YOLO hardware to be present
        self.weights_path = weights_path
        self.camera_rotate_180 = camera_rotate_180 # objects.yaml camera_rotate_180 (down camera remounted upside down)
        self._camera = None
        self._model = None
        self._front_camera = None      # forward ZED, only opened if the icon vision scan runs
        self._front_unavailable = False

        # FIXME: claw_offset_body (body frame, meters) is unmeasured, 0.0 means no correction applied.
        # Separate tape-measure job from the dropper's offset - the claw is a different physical location.
        self.claw_offset_body = claw_offset_body

        self.detection_history = []
        self.last_valid_detection = None
        self.last_detection_time = 0.0
        self.centered_since = None # time.time() of when the target first became centered, None if not centered

        self.target_world = None # last estimated item/basket world position, set by align_step

        # carry monitor / grab-verify rolling state (separate histories from the align tracking
        # above so a mid-carry sighting can't pollute basket alignment stability and vice versa)
        self._carry_history = []
        self._verify_history = []
        self.verify_sightings = 0 # single-frame sightings during the current verify window (for the "intermittent" rule)

        # icon vision scan state
        self._scan_total_deg = 0.0
        self._scan_last_step_time = 0.0

        # debug info, updated every align_step() call, read by the test controller
        self.debug = {
            "x_error": 0.0, "y_error": 0.0, "stable": False,
            "centered": False, "dwell_ok": False, "lost": False, "rejected": False,
        }

        # rotation bonus state (see start_rotation/advance_rotation_step)
        self.rotation_turns_remaining = 0
        self.rotation_steps_done = 0
        self.rotation_steps_per_turn = 360 // ROTATION_STEP_DEGREES
        self.rotation_target_yaw = None
        self.rotation_step_started = 0.0

    # VISION PIPELINE----------------------------------------------------------------------------------------------------------------
    def _ensure_vision(self) -> None:
        if self._camera is None:
            self._camera = camera("downfacing", rotate_180=self.camera_rotate_180)
        if self._model is None:
            self._model = yolo(self.weights_path)

    def verify_model_classes(self, required_ids: list) -> list:
        """
        Loads the model (not the camera) and returns whichever configured
        class ids the weights file does NOT know about. The FSM logs the
        result loudly at start - an id the model can't produce means that
        item/basket/icon is invisible for the whole run.
        """
        if self._model is None:
            self._model = yolo(self.weights_path)
        names = self._model._model.names or {}
        return sorted(set(required_ids) - set(int(k) for k in names))

    def _settle_on_class_swap(self, camera_role: str, classes: list) -> None:
        """
        Sleeps class_swap_wait once whenever the YOLO classes filter changes
        for a camera (the first inference after a swap lags) - steady-state
        calls with an unchanged filter never wait, so the loop stays snappy.
        """
        key = tuple(sorted(classes)) if classes else None
        if self._last_classes.get(camera_role, "unset") != key:
            self._last_classes[camera_role] = key
            if self.class_swap_wait > 0:
                time.sleep(self.class_swap_wait)

    def get_target_detections(self, classes: list = None) -> list:
        """
        Runs the live downward-camera vision pipeline
        (modules/vision/vision_model_main.py) and returns one frame of
        detections in this format:
            [class_label, class_id, conf, x_norm, y_norm, depth_m, width, height]

        classes: optional list of class ids handed to YOLO itself, so
        anything else never becomes a detection (the runtime class filter).
        Changing the filter between calls settles class_swap_wait once.

        Camera + model are opened lazily on first call (not in __init__), so
        importing/constructing this class doesn't require the camera/YOLO
        dependencies to be present (e.g. FAKE_INPUT testing).
        """
        self._ensure_vision()
        self._settle_on_class_swap("down", classes)
        detections = self._model.infer(self._camera, headless=True, verbose=False, classes=classes)
        return convert_vision_runtime_detections(detections)

    # TARGET SELECTION (by class id)-------------------------------------------------------------------------------------------------
    def choose_item_target(self, detections: list, remaining_ids: list, preferred_order: list = None):
        """
        Picks a detection for the next item to grab: walks preferred_order
        (falling back to remaining_ids order) and returns the first detection
        whose class id is still in remaining_ids, or None.
        """
        order = [i for i in (preferred_order or remaining_ids) if i in remaining_ids]
        order += [i for i in remaining_ids if i not in order]
        for class_id in order:
            matches = filter_detections_by_class_id(detections, class_id)
            if matches:
                return matches[0]
        return None

    def choose_basket_target(self, detections: list, bin_ids) -> list:
        """
        Picks the first detection matching bin_ids (an int, or a list ordered
        by preference - the correct bin first, the wrong-bin fallback after),
        or None if not found.
        """
        if isinstance(bin_ids, int):
            bin_ids = [bin_ids]
        for bin_id in bin_ids:
            matches = filter_detections_by_class_id(detections, bin_id)
            if matches:
                return matches[0]
        return None

    # TRACKING-----------------------------------------------------------------------------------------------------------------------
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
        if len(self.detection_history) > max(VERIFY_FRAME_COUNT, self.stable_frames):
            self.detection_history.pop(0)
        self.last_valid_detection = detection
        self.last_detection_time = time.time()

    def check_target_stable(self, detection) -> bool:
        """
        Records a detection into the rolling history and checks if the last
        REQUIRED_STABLE_FRAMES detections form a stable target.
        """
        self.record_detection(detection)
        stable = is_stable_target(self.detection_history, required_frames=self.stable_frames, iou_min=self.stable_iou)
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

    # WORLD-POSITION ESTIMATION------------------------------------------------------------------------------------------------------
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

    def detection_width_m(self, detection, target_depth: float) -> float:
        """
        Back-projects a detection's normalized box width into meters at the
        target plane (used to size the first-item lateral placement offset
        past the bin marker's edge). Returns 0.0 when the geometry can't be
        trusted (target not below the sub).
        """
        vertical_distance = target_depth - self.shared_memory.depth.value
        if vertical_distance <= 0:
            return 0.0
        return vertical_distance * detection[WIDTH] / CAMERA_FX_NORM

    # ALIGNMENT----------------------------------------------------------------------------------------------------------------------
    def align_step(self, choose_target_fn, target_depth: float, desired_height: float, x_tolerance: float, y_tolerance: float,
                    assumed_world: tuple = None, max_object_yaml_error: float = MAX_OBJECT_YAML_ERROR_M,
                    classes: list = None, target_offset_body: tuple = (0.0, 0.0)) -> dict:
        """
        Runs one tick of downward-camera alignment toward whatever
        choose_target_fn(detections) picks out (an item or a basket), using
        the camera + pressure sensor depth (no ZED/stereo depth here):
            1. fetch fresh detections (optionally class-filtered at the model
               via classes=[...]) and pick a target with choose_target_fn
            2. if briefly lost, hold position and wait for it to reappear
            3. if lost too long, report lost so the FSM can go back to searching
            4. otherwise smooth the box center over recent frames, back-project
               it to a metric body-frame x/y error using target_depth
            5. estimate the target's world position (DVL + yaw rotation) and
               sanity-check it against the objects.yaml assumed location;
               reject if it fails the check
            6. apply target_offset_body (body frame, meters - e.g. the
               first-item lateral placement offset so a released item lands
               BESIDE the bin marker instead of covering it), compute the claw
               (not camera) alignment target, and nudge toward it; target_z is
               set directly from target_depth/desired_height (heave doesn't
               come from the image at all here)
            7. track how long the target has stayed centered (dwell time)

        Returns a dict of results/debug info:
            target, target_world, centered, dwell_ok, lost, rejected, detections
        (detections = the full frame's detections, so the FSM can also feed
        the carry monitor from the same inference instead of running two.)
        """
        detections = self.get_target_detections(classes=classes)
        detection = choose_target_fn(detections)

        if detection is not None:
            self.record_detection(detection)
        elif self.is_target_lost():
            self.debug["lost"] = True
            return {"target": None, "target_world": None, "centered": False, "dwell_ok": False, "lost": True, "rejected": False, "detections": detections}
        else:
            # briefly lost, hold position, keep using the last known target
            stop_vehicle_motion(self.shared_memory)
            self.debug["lost"] = False
            return {"target": self.last_valid_detection, "target_world": self.target_world, "centered": False, "dwell_ok": False, "lost": False, "rejected": False, "detections": detections}

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
            return {"target": detection, "target_world": target_world, "centered": False, "dwell_ok": False, "lost": False, "rejected": True, "detections": detections}

        self.debug["rejected"] = False

        # optional placement offset: shift the goal point away from the detection center
        # (rotated into world frame the same way the vision error itself is)
        if target_offset_body != (0.0, 0.0):
            yaw_deg = self.shared_memory.dvl_yaw.value
            offset_world = body_offset_to_world_offset(target_offset_body[0], target_offset_body[1], yaw_deg)
            target_world = (target_world[0] + offset_world[0], target_world[1] + offset_world[1])

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
            "target_world": self.target_world,
            "centered": centered_now,
            "dwell_ok": self.debug["dwell_ok"],
            "lost": False,
            "rejected": False,
            "detections": detections,
        }

    # CARRY MONITOR / GRAB VERIFICATION----------------------------------------------------------------------------------------------
    def _filtered_sighting(self, detections: list, class_id: int, max_width_norm: float, ignore_region: list = None):
        """
        Picks the first detection of class_id that plausibly sits on a
        surface BELOW the sub (not the item held in the claw itself):
            - confidence at least MIN_CONFIDENCE (is_confident_detection)
            - normalized width at most max_width_norm (an in-claw item is far
              closer to the lens, so it back-projects much larger)
            - box center outside ignore_region ([x0, y0, x1, y1] normalized,
              where the claw dangles into frame), if one is configured
        """
        for detection in filter_detections_by_class_id(detections, class_id):
            if not is_confident_detection(detection):
                continue
            if detection[WIDTH] > max_width_norm:
                continue
            if ignore_region is not None:
                x0, y0, x1, y1 = ignore_region
                if x0 <= detection[X_NORM] <= x1 and y0 <= detection[Y_NORM] <= y1:
                    continue
            return detection
        return None

    def carry_monitor_reset(self) -> None:
        """
        Clears the carry monitor history. Call when a new carry begins
        (right after a verified grab).
        """
        self._carry_history = []

    def carry_monitor_ingest(self, detections: list, class_id: int, table_world: tuple, item_target_depth: float,
                              max_width_norm: float = 0.35, ignore_region: list = None,
                              max_table_dist: float = MAX_OBJECT_YAML_ERROR_M):
        """
        Feeds one frame of detections into the carry monitor (use this from
        states that already ran an inference; carry_monitor_step runs its own).

        A detection of the supposedly-held class that stays stable for
        stable_frames consecutive frames at stable_iou (the same
        stability bar as targeting) means the item is sitting on a surface
        below us - the grab silently failed or it slipped out.

        Returns None (still holding as far as we know), "dropped_near_table"
        (back-projected world position within max_table_dist of table_world -
        worth going back for), or "dropped_elsewhere" (write it off).
        """
        sighting = self._filtered_sighting(detections, class_id, max_width_norm, ignore_region)
        if sighting is None:
            # stability requires consecutive frames - any clean frame resets the streak
            self._carry_history = []
            return None

        self._carry_history.append(sighting)
        if len(self._carry_history) > self.stable_frames:
            self._carry_history.pop(0)
        if not is_stable_target(self._carry_history, required_frames=self.stable_frames, iou_min=self.stable_iou):
            return None

        # stable sighting - locate it. Back-projection uses the table depth (if it actually
        # fell to the pool floor the xy direction is still roughly right, and the verdict
        # only gates on a coarse near-the-table distance anyway).
        center = average_target_center(self._carry_history)
        x_error_m, y_error_m = get_target_error_meters(center[0], center[1], self.shared_memory.depth.value, item_target_depth)
        world = self.estimate_target_world_position(x_error_m, y_error_m)
        if table_world is not None and distance_2d(world, table_world) <= max_table_dist:
            return "dropped_near_table"
        return "dropped_elsewhere"

    def carry_monitor_step(self, class_id: int, table_world: tuple, item_target_depth: float,
                            max_width_norm: float = 0.35, ignore_region: list = None,
                            max_table_dist: float = MAX_OBJECT_YAML_ERROR_M):
        """
        Carry monitor for transit states (surfacing/descending/moving) where
        no other inference is running: does one class-filtered inference and
        ingests it. Same return values as carry_monitor_ingest.
        """
        detections = self.get_target_detections(classes=[class_id])
        return self.carry_monitor_ingest(detections, class_id, table_world, item_target_depth, max_width_norm, ignore_region, max_table_dist)

    def verify_grab_reset(self) -> None:
        """
        Clears the lift-and-look grab verification window. Call on entering
        LIFT_AND_VERIFY.
        """
        self._verify_history = []
        self.verify_sightings = 0

    def verify_grab_step(self, class_id: int, max_width_norm: float = 0.35, ignore_region: list = None) -> bool:
        """
        One tick of the lift-and-look check over the table: returns True the
        moment the supposedly-grabbed class is seen STABLE on the table
        (stable_frames at stable_iou) - i.e. the grab FAILED. Counts
        single-frame sightings in self.verify_sightings so the FSM can extend
        the window when detections are intermittent instead of calling a
        too-early success.
        """
        detections = self.get_target_detections(classes=[class_id])
        sighting = self._filtered_sighting(detections, class_id, max_width_norm, ignore_region)
        if sighting is None:
            self._verify_history = []
            return False

        self.verify_sightings += 1
        self._verify_history.append(sighting)
        if len(self._verify_history) > self.stable_frames:
            self._verify_history.pop(0)
        return is_stable_target(self._verify_history, required_frames=self.stable_frames, iou_min=self.stable_iou)

    # CLAW---------------------------------------------------------------------------------------------------------------------------
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

    # SURFACING----------------------------------------------------------------------------------------------------------------------
    def surface_in_octagon(self, surface_z: float = 0.0) -> None:
        """
        Surfaces by setting target_z to surface_z (default 0). Assumes the
        sub is positioned inside the octagon when this is called.
        """
        self.shared_memory.target_z.value = surface_z

    # ICON FACING--------------------------------------------------------------------------------------------------------------------
    def get_target_icon_ids(self, items_placed: int) -> list:
        """
        Returns the icon class ids worth facing for the given item count
        (either role's icon scores, so both ids are candidates).
        """
        if items_placed >= 2:
            return list(TWO_ITEM_ICON_IDS)
        return list(ONE_ITEM_ICON_IDS)

    def start_icon_scan(self) -> None:
        """
        Resets the vision icon scan (see face_icon_scan_step).
        """
        self._scan_total_deg = 0.0
        self._scan_last_step_time = 0.0

    def face_icon_scan_step(self, icon_ids: list, scan_step_deg: float = 15.0, dwell_s: float = 1.0,
                             center_tol_norm: float = 0.06, deg_per_image: float = 90.0, yaw_sign: float = 1.0) -> str:
        """
        One tick of the surface icon scan with the FORWARD camera: rotate in
        scan_step_deg increments (dwell_s apart, so YOLO gets settled frames)
        until one of icon_ids is seen, then proportionally yaw it toward the
        image center.

        Returns "centered" (icon within center_tol_norm of image center),
        "scanning" (keep polling), "exhausted" (a full 360+ scanned with no
        icon - use the heading fallback), or "no_camera" (forward camera
        unavailable - use the heading fallback immediately).

        deg_per_image is the forward camera's horizontal FOV (degrees), used
        as the proportional gain from normalized image error to yaw degrees.
        FIXME: yaw_sign (+1/-1, whether x_norm > 0.5 means "yaw positive")
        depends on the yaw convention - verify in the pool, flip in
        objects.yaml if the sub turns away from icons instead of toward them.
        """
        if self._front_unavailable:
            return "no_camera"
        if self._front_camera is None:
            try:
                self._front_camera = camera("zed")
            except Exception as error:
                print(f"GRABBER ICON SCAN: forward camera unavailable ({error}), falling back to headings")
                self._front_unavailable = True
                return "no_camera"
        if self._model is None:
            self._model = yolo(self.weights_path)

        self._settle_on_class_swap("front", list(icon_ids))
        detections = convert_vision_runtime_detections(
            self._model.infer(self._front_camera, headless=True, verbose=False, classes=list(icon_ids))
        )
        best = None
        for icon_id in icon_ids:
            matches = [d for d in filter_detections_by_class_id(detections, icon_id) if is_confident_detection(d)]
            if matches:
                best = max(matches, key=lambda d: d[CONF])
                break

        if best is not None:
            x_error_norm = best[X_NORM] - 0.5
            if abs(x_error_norm) <= center_tol_norm:
                return "centered"
            current_yaw = self.shared_memory.dvl_yaw.value
            self.shared_memory.target_yaw.value = (current_yaw + yaw_sign * x_error_norm * deg_per_image) % 360
            return "scanning"

        # nothing seen - advance the scan one step at most every dwell_s
        now = time.time()
        if now - self._scan_last_step_time >= dwell_s:
            self._scan_last_step_time = now
            self._scan_total_deg += scan_step_deg
            current_yaw = self.shared_memory.dvl_yaw.value
            self.shared_memory.target_yaw.value = (current_yaw + yaw_sign * scan_step_deg) % 360
        if self._scan_total_deg > 360.0 + scan_step_deg:
            return "exhausted"
        return "scanning"

    def face_target_icon(self, icon_ids: list) -> None:
        """
        Heading fallback: turns to face the first of icon_ids by its known
        heading from ICON_HEADINGS.

        FIXME: real measured headings for each icon, see ICON_HEADINGS above,
        all currently placeholder 0 values.
        """
        first = icon_ids[0] if icon_ids else None
        self.shared_memory.target_yaw.value = ICON_HEADINGS.get(first, 0)

    # ROTATION BONUS-----------------------------------------------------------------------------------------------------------------
    def start_rotation(self, turns: int, turn_degrees: float = 360.0) -> None:
        """
        Begins the rotation bonus (section 3.2.6): spin in place `turns`
        times, each turn covering turn_degrees (360 by default - set 180 in
        objects.yaml if that's the ruling on what counts as a "rotation").
        Steps in ROTATION_STEP_DEGREES increments (see module docstring for
        why), commanding the first step immediately from the sub's current
        heading. turns=0 leaves rotation_turns_remaining at 0, so
        advance_rotation_step() returns True right away (no-op skip).
        """
        self.rotation_turns_remaining = max(0, turns)
        self.rotation_steps_per_turn = max(1, int(round(turn_degrees / ROTATION_STEP_DEGREES)))
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
        self.rotation_step_started = time.time()

    def advance_rotation_step(self, step_timeout: float = None) -> bool:
        """
        Polled every loop tick while rotating. Checks if the sub has reached
        the current quarter-turn step (wraparound-safe angular difference);
        if so, either commands the next step or, once rotation_steps_per_turn
        steps complete a turn, moves on to the next turn.

        step_timeout: optional seconds after which a non-converging step is
        force-counted and the next one commanded anyway, so a sticky yaw PID
        can never park the FSM here (the spins must always finish - they're
        the very last scored action of the run).

        Returns True once rotation_turns_remaining reaches 0 (all requested
        turns complete), False otherwise.
        """
        if self.rotation_turns_remaining <= 0:
            return True

        if self.rotation_target_yaw is None:
            self._advance_rotation_target()
            return False

        current_yaw = self.shared_memory.dvl_yaw.value
        raw_delta = current_yaw - self.rotation_target_yaw
        angular_diff = min(abs(raw_delta), 360 - abs(raw_delta))

        step_stuck = step_timeout is not None and time.time() - self.rotation_step_started > step_timeout
        if angular_diff > ROTATION_STEP_TOLERANCE_DEG and not step_stuck:
            return False # still turning toward the current step

        self.rotation_steps_done += 1
        if self.rotation_steps_done >= self.rotation_steps_per_turn:
            self.rotation_turns_remaining -= 1
            self.rotation_steps_done = 0

        if self.rotation_turns_remaining <= 0:
            return True

        self._advance_rotation_target()
        return False
