import time

"""
    Shared vision target box helpers used by the dropper and grabber FSMs.
    Handles box math, the 3-frame target stability check, and downward-camera
    motion control (dropper/grabber both use a downward-facing camera, unlike
    torpedo's forward-facing camera in torpedo_helpers.py, so they need this
    separate, simpler proportional control instead of torpedo's FOV/distance
    trig math).
    Keep this file free of task-specific logic (bins, items, baskets, etc.),
    that belongs in dropper_helpers.py / grabber_helpers.py.

    Detection format (one detection):
        [class_label, class_id, conf, x_norm, y_norm, depth_m, width, height]
"""

# INDEXES into a detection list------------------------------------------------------------------------------------------------
CLASS_LABEL = 0
CLASS_ID    = 1
CONF        = 2
X_NORM      = 3
Y_NORM      = 4
DEPTH_M     = 5
WIDTH       = 6
HEIGHT      = 7

# BOX/STABILITY THRESHOLDS, adjust these as needed------------------------------------------------------------------------------
MIN_CONFIDENCE        = 0.70
CENTER_TOLERANCE      = 0.08
SIZE_TOLERANCE        = 0.30
AREA_MATCH_THRESHOLD  = 0.70
REQUIRED_STABLE_FRAMES = 3

# DOWNWARD CAMERA MOTION CONTROL, adjust these as needed------------------------------------------------------------------------
# camera looks straight down at the pool floor: x_norm/y_norm map to
# strafe/forward error, not to a forward-facing FOV angle
CENTER_X = 0.5
CENTER_Y = 0.5

X_TOLERANCE = 0.05
Y_TOLERANCE = 0.05
DEPTH_TOLERANCE_M = 0.10

X_GAIN = 0.4
Y_GAIN = 0.4
Z_GAIN = 0.3

MAX_STRAFE_CMD   = 0.3
MAX_FORWARD_CMD  = 0.3
MAX_VERTICAL_CMD = 0.2

REQUIRED_CENTER_TIME = 1.0 # seconds the target must stay centered before actuating
TARGET_LOST_TIMEOUT  = 2.0 # seconds a target can be briefly lost before giving up on it

# SIGN CONVENTIONS: flip any of these to -1 after pool testing if the sub
# strafes/moves/rises the wrong direction. Simplest way to test: hold a bin/
# item under the camera off to one side and watch which way target_x/y/z move.
X_SIGN = 1
Y_SIGN = 1
Z_SIGN = 1

# METRIC BACK-PROJECTION (downward camera + pressure sensor depth)---------------------------------------------------------------
# This camera has no depth sensing of its own (no ZED/stereo). Instead of
# reading depth_m off a detection, the vertical distance to a target is
# computed as target_depth - sub_depth (pressure sensor), then used with the
# camera intrinsics to back-project x_norm/y_norm into a metric (x, y) offset.
# Used by dropper for now, see fsm/dropper_fsm.py / dropper_helpers.py.
#
# MISSING: calibration_output.yaml was solved with the camera in air. A flat
# port refracts light differently underwater (water's refractive index is
# ~1.33 vs air's 1.0), which changes the effective focal length, worst
# toward the edges of the frame. Recalibrate fully submerged before trusting
# these numbers for real alignment.
CAMERA_FX = 1365.2319737707428
CAMERA_FY = 1367.6414088719202
CAMERA_CX = 1490.5695516851383
CAMERA_CY = 742.6264306112528
CAMERA_CALIB_WIDTH  = 2894
CAMERA_CALIB_HEIGHT = 1630

# normalized intrinsics, so back-projection works directly on x_norm/y_norm
# regardless of the vision pipeline's actual runtime resolution (as long as
# its aspect ratio matches the calibration frame)
CAMERA_FX_NORM = CAMERA_FX / CAMERA_CALIB_WIDTH
CAMERA_FY_NORM = CAMERA_FY / CAMERA_CALIB_HEIGHT
CAMERA_CX_NORM = CAMERA_CX / CAMERA_CALIB_WIDTH
CAMERA_CY_NORM = CAMERA_CY / CAMERA_CALIB_HEIGHT

# MISSING: camera-to-tool offset (body frame, meters) has not been measured
# yet, 0 means no correction is applied. Mount rotation is not needed here
# since the camera is mounted aligned with the sub facing forward.
CAMERA_TO_TOOL_X = 0.0
CAMERA_TO_TOOL_Y = 0.0

X_TOLERANCE_M = 0.05 # meters, how close the back-projected error must be to 0 to count as centered
Y_TOLERANCE_M = 0.05 # meters


def is_confident_detection(detection) -> bool:
    """
    Checks if the model confidence is high enough.
    """
    return detection[CONF] >= MIN_CONFIDENCE


def get_box_edges(detection) -> tuple:
    """
    Estimates the box edges from its center and width/height.
    Returns (x_min, x_max, y_min, y_max).
    """
    x_norm = detection[X_NORM]
    y_norm = detection[Y_NORM]
    width  = detection[WIDTH]
    height = detection[HEIGHT]

    x_min = x_norm - width / 2
    x_max = x_norm + width / 2
    y_min = y_norm - height / 2
    y_max = y_norm + height / 2

    return x_min, x_max, y_min, y_max


def get_box_area(detection) -> float:
    """
    Returns the normalized box area (width * height).
    """
    return detection[WIDTH] * detection[HEIGHT]


def get_box_center(detection) -> tuple:
    """
    Returns (x_norm, y_norm) for the box center.
    """
    return detection[X_NORM], detection[Y_NORM]


def is_same_class(detection_1, detection_2) -> bool:
    """
    Checks if two detections have the same class label.
    """
    return detection_1[CLASS_LABEL] == detection_2[CLASS_LABEL]


def is_similar_box_size(detection_1, detection_2) -> bool:
    """
    Checks if width and height stayed similar between two detections.
    SIZE_TOLERANCE is a decimal value: 0.30 means 30 percent difference is allowed.
    """
    width_1, height_1 = detection_1[WIDTH], detection_1[HEIGHT]
    width_2, height_2 = detection_2[WIDTH], detection_2[HEIGHT]

    if width_1 <= 0 or height_1 <= 0 or width_2 <= 0 or height_2 <= 0:
        return False

    width_error = abs(width_1 - width_2) / max(width_1, width_2)
    height_error = abs(height_1 - height_2) / max(height_1, height_2)

    return width_error <= SIZE_TOLERANCE and height_error <= SIZE_TOLERANCE


def is_similar_box_area(detection_1, detection_2) -> bool:
    """
    Checks if the box area stayed similar between two detections.
    AREA_MATCH_THRESHOLD is a decimal value: 0.70 means the smaller area must be
    at least 70 percent of the larger area.
    """
    area_1 = get_box_area(detection_1)
    area_2 = get_box_area(detection_2)

    if area_1 <= 0 or area_2 <= 0:
        return False

    return min(area_1, area_2) / max(area_1, area_2) >= AREA_MATCH_THRESHOLD


def is_similar_box_center(detection_1, detection_2) -> bool:
    """
    Checks if the box center stayed close enough between two detections.
    """
    x_1, y_1 = get_box_center(detection_1)
    x_2, y_2 = get_box_center(detection_2)

    return abs(x_1 - x_2) <= CENTER_TOLERANCE and abs(y_1 - y_2) <= CENTER_TOLERANCE


def boxes_overlap_or_close(detection_1, detection_2) -> bool:
    """
    Checks if two boxes overlap, or falls back to the center-distance check
    if they don't, to catch small/fast-moving boxes that don't quite overlap.
    """
    x1_min, x1_max, y1_min, y1_max = get_box_edges(detection_1)
    x2_min, x2_max, y2_min, y2_max = get_box_edges(detection_2)

    overlap_x = x1_min <= x2_max and x2_min <= x1_max
    overlap_y = y1_min <= y2_max and y2_min <= y1_max

    if overlap_x and overlap_y:
        return True

    return is_similar_box_center(detection_1, detection_2)


def is_stable_target(last_three_detections: list) -> bool:
    """
    Checks if the last REQUIRED_STABLE_FRAMES detections all look like the same,
    confident, steady target:
        1. same class label
        2. confidence at least MIN_CONFIDENCE
        3. box center stays close enough
        4. box width/height stay similar
        5. box area stays similar
        6. boxes overlap enough or are close enough to likely be the same target
    """
    if len(last_three_detections) < REQUIRED_STABLE_FRAMES:
        return False

    for detection in last_three_detections:
        if not is_confident_detection(detection):
            return False

    first = last_three_detections[0]
    for detection in last_three_detections[1:]:
        if not is_same_class(first, detection):
            return False
        if not is_similar_box_center(first, detection):
            return False
        if not is_similar_box_size(first, detection):
            return False
        if not is_similar_box_area(first, detection):
            return False
        if not boxes_overlap_or_close(first, detection):
            return False

    return True


def estimate_distance_to_target(detection) -> float:
    """
    Returns the distance to a target in meters (camera looks straight down,
    so this is roughly the sub's height above the target).

    depth_m comes from modules/vision/main.py's live detections. It is only
    real when running on a ZED camera (point cloud lookup at the box center);
    the vision pipeline uses -1.0 to mean "unavailable" (webcam source, or an
    invalid ZED point cloud read at that pixel).

    MISSING for the webcam/unavailable case: one of
        - a known real-world object size compared to the apparent box size
        - camera calibration (focal length, sensor size)
        - another range estimate (e.g. an acoustic pinger)
    """
    depth_m = detection[DEPTH_M]
    if depth_m is not None and depth_m > 0:
        return depth_m
    return 0.0 # unavailable, caller should not trust this


def get_detection_center_error(detection) -> tuple:
    """
    Returns (x_error, y_error): how far the target's box center is from the
    image center (CENTER_X, CENTER_Y).
    Positive x_error = target is right of center.
    Positive y_error = target is toward the top of the image.
    """
    x_norm, y_norm = get_box_center(detection)
    return x_norm - CENTER_X, y_norm - CENTER_Y


def average_target_center(recent_detections: list):
    """
    Returns the average (x_norm, y_norm) across recent detections, used to
    smooth out single-frame noise instead of reacting to one noisy box.
    Returns None if recent_detections is empty.
    """
    if not recent_detections:
        return None

    x_values = [detection[X_NORM] for detection in recent_detections]
    y_values = [detection[Y_NORM] for detection in recent_detections]
    return sum(x_values) / len(x_values), sum(y_values) / len(y_values)


def is_target_centered(detection, x_tolerance: float = X_TOLERANCE, y_tolerance: float = Y_TOLERANCE) -> bool:
    """
    Checks if the target's box center is close enough to the image center.
    """
    x_error, y_error = get_detection_center_error(detection)
    return abs(x_error) <= x_tolerance and abs(y_error) <= y_tolerance


def calculate_depth_error(current_distance: float, desired_distance: float) -> float:
    """
    Returns how far off the current height above the target is from the
    desired height. Positive means still too far away.
    """
    return current_distance - desired_distance


def is_at_correct_height(current_distance: float, desired_distance: float, tolerance: float = DEPTH_TOLERANCE_M) -> bool:
    """
    Checks if the sub is at the right height above the target.

    If no trustworthy distance is available yet (see estimate_distance_to_target),
    this returns True so height doesn't permanently block alignment/actuation,
    it just means real vertical correction is skipped until distance data exists.
    """
    if current_distance <= 0:
        return True
    return abs(current_distance - desired_distance) <= tolerance


def clamp_motion_command(value: float, max_value: float) -> float:
    """
    Clamps a movement command to +/- max_value so the sub never moves too aggressively.
    """
    return max(-max_value, min(max_value, value))


def convert_target_error_to_motion(x_error: float, y_error: float, depth_error: float = 0.0) -> tuple:
    """
    Converts image/depth error into clamped, proportional movement commands.
    Returns (strafe_cmd, forward_cmd, vertical_cmd).

    Flip X_SIGN/Y_SIGN/Z_SIGN above after pool testing if any axis moves the
    wrong direction, that's the easiest thing to get backwards on a downward camera.
    """
    strafe_cmd   = clamp_motion_command(X_SIGN * X_GAIN * x_error, MAX_STRAFE_CMD)
    forward_cmd  = clamp_motion_command(Y_SIGN * Y_GAIN * y_error, MAX_FORWARD_CMD)
    vertical_cmd = clamp_motion_command(Z_SIGN * Z_GAIN * depth_error, MAX_VERTICAL_CMD)
    return strafe_cmd, forward_cmd, vertical_cmd


def move_using_target_error(shared_memory_object, x_error: float, y_error: float, depth_error: float = 0.0) -> tuple:
    """
    Nudges target_x/y/z by a small proportional step based on vision error,
    added onto the sub's current dvl position. Call this every loop tick while
    aligning, so movement is smooth and continuous instead of one big jump.

    Axis mapping (matches objects.yaml's convention: "x: forward", "y: left"):
        x_norm error (left/right)   -> strafe_cmd   -> added to target_y
        y_norm error (forward/back) -> forward_cmd  -> added to target_x
        depth error (height)        -> vertical_cmd -> added to target_z

    Returns (strafe_cmd, forward_cmd, vertical_cmd) for debug/logging.
    """
    strafe_cmd, forward_cmd, vertical_cmd = convert_target_error_to_motion(x_error, y_error, depth_error)

    shared_memory_object.target_x.value = shared_memory_object.dvl_x.value + forward_cmd
    shared_memory_object.target_y.value = shared_memory_object.dvl_y.value + strafe_cmd
    shared_memory_object.target_z.value = shared_memory_object.dvl_z.value + vertical_cmd

    return strafe_cmd, forward_cmd, vertical_cmd


def stop_vehicle_motion(shared_memory_object) -> None:
    """
    Holds position by setting target_x/y/z to the sub's current position.
    Call this while a target is temporarily lost so the sub doesn't keep
    drifting on the last command it was given.
    """
    shared_memory_object.target_x.value = shared_memory_object.dvl_x.value
    shared_memory_object.target_y.value = shared_memory_object.dvl_y.value
    shared_memory_object.target_z.value = shared_memory_object.dvl_z.value


def has_required_center_time(centered_since, required_time: float = REQUIRED_CENTER_TIME) -> bool:
    """
    Checks if the target has been centered continuously for required_time
    seconds. centered_since should be None if not currently centered.
    """
    if centered_since is None:
        return False
    return time.time() - centered_since >= required_time


def target_lost_too_long(last_seen_time: float, timeout: float = TARGET_LOST_TIMEOUT) -> bool:
    """
    Checks if too much time has passed since the target was last seen.
    """
    return time.time() - last_seen_time > timeout


def filter_detections_by_label(detections: list, label: str) -> list:
    """
    Filters the detection list down to ones matching the given label.
    """
    return [detection for detection in detections if detection[CLASS_LABEL] == label]


def get_target_detection(detections: list, label: str):
    """
    Picks the first detection matching label, or None if not found.
    """
    matches = filter_detections_by_label(detections, label)
    if not matches:
        return None
    return matches[0]


def convert_vision_runtime_detections(detections_dict: dict) -> list:
    """
    Converts modules/vision/main.py's live detection dict format:
        {'obj1': [class_label, class_id, conf, x_norm, y_norm, width, height, depth_m], ...}
    into the flat list format used in this file:
        [class_label, class_id, conf, x_norm, y_norm, depth_m, width, height]
    """
    detections = []
    for class_label, class_id, conf, x_norm, y_norm, width, height, depth_m in detections_dict.values():
        detections.append([class_label, class_id, conf, x_norm, y_norm, depth_m, width, height])
    return detections


def back_project_to_body_frame(x_norm: float, y_norm: float, vertical_distance: float) -> tuple:
    """
    Back-projects a normalized detection to a metric (x, y) offset in the
    camera/body frame, using a known vertical distance to the target (from
    the pressure sensor + a known target depth) instead of stereo depth.

    Assumes:
        - the sub is level (pitch/roll ~ 0), otherwise this needs the sub's
          attitude to correct for image shear
        - the camera mount is aligned with the sub facing forward (no extra
          rotation needed between camera frame and body frame)
    """
    u_norm = x_norm
    v_norm = 1.0 - y_norm # convert back to standard image-down (0=top) convention

    x_c = vertical_distance * (u_norm - CAMERA_CX_NORM) / CAMERA_FX_NORM
    y_c = vertical_distance * (v_norm - CAMERA_CY_NORM) / CAMERA_FY_NORM
    return x_c, y_c


def get_target_error_meters(x_norm: float, y_norm: float, sub_depth: float, target_depth: float) -> tuple:
    """
    Returns (x_error_m, y_error_m): how far the tool needs to move (meters,
    body frame) to be over the target, using the downward camera + pressure
    sensor depth instead of stereo depth (this camera has no depth sensing
    of its own).

    MISSING: CAMERA_TO_TOOL_X/Y are placeholders (0), waiting on the real
    camera-to-tool offset measurement.
    """
    vertical_distance = target_depth - sub_depth
    if vertical_distance <= 0:
        return 0.0, 0.0 # target isn't below the sub, don't trust this

    x_c, y_c = back_project_to_body_frame(x_norm, y_norm, vertical_distance)
    return x_c - CAMERA_TO_TOOL_X, y_c - CAMERA_TO_TOOL_Y


def is_target_centered_metric(x_error_m: float, y_error_m: float, x_tolerance: float = X_TOLERANCE_M, y_tolerance: float = Y_TOLERANCE_M) -> bool:
    """
    Checks if a metric alignment error (see get_target_error_meters) is
    close enough to zero to act.
    """
    return abs(x_error_m) <= x_tolerance and abs(y_error_m) <= y_tolerance


def nudge_xy_toward_target(shared_memory_object, x_error_m: float, y_error_m: float) -> tuple:
    """
    Nudges target_x/target_y by a small clamped step toward the target,
    same gain/clamp math as move_using_target_error, but leaves target_z
    alone (heave is set directly from the pressure sensor instead, see
    set_hover_depth()) since heave doesn't come from the image at all here.
    """
    strafe_cmd = clamp_motion_command(X_SIGN * X_GAIN * x_error_m, MAX_STRAFE_CMD)
    forward_cmd = clamp_motion_command(Y_SIGN * Y_GAIN * y_error_m, MAX_FORWARD_CMD)

    shared_memory_object.target_x.value = shared_memory_object.dvl_x.value + forward_cmd
    shared_memory_object.target_y.value = shared_memory_object.dvl_y.value + strafe_cmd

    return strafe_cmd, forward_cmd


def set_hover_depth(shared_memory_object, target_depth: float, desired_height: float) -> None:
    """
    Sets target_z directly from the known target depth (pressure sensor
    convention), instead of a proportional vision-based nudge, since the
    camera has no depth sensing of its own. desired_height is how far above
    the target the sub should hover.
    """
    shared_memory_object.target_z.value = target_depth - desired_height
