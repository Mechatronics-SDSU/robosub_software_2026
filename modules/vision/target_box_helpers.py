import time

from scipy.spatial.transform import Rotation

"""
    Shared vision target box helpers used by the dropper FSM.
    Handles box math, the multi-frame target stability check (via IoU), and
    downward-camera motion control (dropper uses a downward-facing camera,
    unlike torpedo's forward-facing camera in torpedo_helpers.py, so it needs
    this separate, simpler proportional control instead of torpedo's FOV/
    distance trig math).
    Keep this file free of task-specific logic (bin labels, roles, etc.),
    that belongs in dropper_helpers.py.

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
MIN_CONFIDENCE         = 0.70
IOU_MIN                = 0.60   # required IoU between consecutive frames to count as the same stable target
VERIFY_IOU_MIN         = 0.65   # stricter IoU threshold used during the final pre-drop verify pass
REQUIRED_STABLE_FRAMES = 3
VERIFY_FRAME_COUNT     = 5      # consecutive good frames required during the final verify pass

# DOWNWARD CAMERA MOTION CONTROL, adjust these as needed------------------------------------------------------------------------
X_GAIN = 0.4
Y_GAIN = 0.4

MAX_STRAFE_CMD   = 0.3
MAX_FORWARD_CMD  = 0.3

REQUIRED_CENTER_TIME = 1.0 # seconds the target must stay centered before actuating
TARGET_LOST_TIMEOUT  = 2.0 # seconds a target can be briefly lost before giving up on it
FINAL_SETTLE_TIME_S  = 0.75 # seconds to hold/station-keep before the final verify pass

# BIN SANITY-CHECK / MEMORY THRESHOLDS-------------------------------------------------------------------------------------------
SAME_BIN_RADIUS_M       = 0.5  # reject a candidate bin within this radius (world frame) of an already-completed bin
MAX_OBJECT_YAML_ERROR_M = 1.0  # reject a vision bin-world estimate this far from the objects.yaml assumed location

# METRIC BACK-PROJECTION (downward camera + pressure sensor depth)---------------------------------------------------------------
# This camera has no depth sensing of its own (no ZED/stereo). Instead of
# reading depth_m off a detection, the vertical distance to a target is
# computed as target_depth - sub_depth (pressure sensor), then used with the
# camera intrinsics to back-project x_norm/y_norm into a metric (x, y) offset.
#
# This math assumes an already-undistorted, correctly-oriented image (the
# downward camera is a fisheye lens mounted backwards on the hull - both the
# fisheye undistortion and the y-axis mount-flip correction happen upstream
# in modules/vision/vision_model_main.py's DownfacingCamera.grab(), not here,
# so by the time a detection's x_norm/y_norm reaches this file it should
# already behave like an ideal pinhole image matching CAMERA_FX/FY/CX/CY below.
#
# FIXME: calibration_output.yaml was solved with the camera in air. A flat
# port refracts light differently underwater (water's refractive index is
# ~1.33 vs air's 1.0), which changes the effective focal length, worst
# toward the edges of the frame. Recalibrate fully submerged before trusting
# these numbers for real alignment.
CALIBRATION_MODEL = "fisheye_equidistant"
CAMERA_FX = 1365.2319737707428
CAMERA_FY = 1367.6414088719202
CAMERA_CX = 1490.5695516851383
CAMERA_CY = 742.6264306112528
CAMERA_CALIB_WIDTH  = 2894
CAMERA_CALIB_HEIGHT = 1630
# fisheye distortion coefficients, only used by DownfacingCamera's undistortion
# step in vision_model_main.py - not used by any math in this file
DISTORTION_COEFFS = [-0.20075077070941028, 1.0392093221841716, -3.3863424378528664, 3.7850850441479715]

# normalized intrinsics, so back-projection works directly on x_norm/y_norm
# regardless of the vision pipeline's actual runtime resolution (as long as
# its aspect ratio matches the calibration frame)
CAMERA_FX_NORM = CAMERA_FX / CAMERA_CALIB_WIDTH
CAMERA_FY_NORM = CAMERA_FY / CAMERA_CALIB_HEIGHT
CAMERA_CX_NORM = CAMERA_CX / CAMERA_CALIB_WIDTH
CAMERA_CY_NORM = CAMERA_CY / CAMERA_CALIB_HEIGHT

# FIXME: physically verify the downward camera isn't twisted relative to the
# hull before trusting back_project_to_body_frame()'s no-extra-rotation
# assumption. Tool offset (dropper vs. claw, each a different physical
# location) is NOT applied here — each FSM owns its own *_offset_body config
# and applies it with yaw rotation at the alignment-target step (see
# DropperHelpers.compute_dropper_alignment_target / GrabberHelpers.compute_claw_alignment_target).
# It used to also be subtracted here (unrotated), which double-applied the
# same physical offset once correctly (rotated) and once incorrectly
# (unrotated) - removed to avoid that.

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


def compute_iou(detection_1, detection_2) -> float:
    """
    Returns the intersection-over-union of two detections' boxes, 0.0 if
    they don't overlap at all or either box is degenerate.
    """
    x1_min, x1_max, y1_min, y1_max = get_box_edges(detection_1)
    x2_min, x2_max, y2_min, y2_max = get_box_edges(detection_2)

    inter_x_min = max(x1_min, x2_min)
    inter_x_max = min(x1_max, x2_max)
    inter_y_min = max(y1_min, y2_min)
    inter_y_max = min(y1_max, y2_max)

    inter_width  = max(0.0, inter_x_max - inter_x_min)
    inter_height = max(0.0, inter_y_max - inter_y_min)
    intersection = inter_width * inter_height

    area_1 = max(0.0, x1_max - x1_min) * max(0.0, y1_max - y1_min)
    area_2 = max(0.0, x2_max - x2_min) * max(0.0, y2_max - y2_min)
    union = area_1 + area_2 - intersection

    if union <= 0:
        return 0.0
    return intersection / union


def is_stable_target(recent_detections: list, required_frames: int = REQUIRED_STABLE_FRAMES, iou_min: float = IOU_MIN) -> bool:
    """
    Checks if the last required_frames detections all look like the same,
    confident, steady target:
        1. same class label as the first frame
        2. confidence at least MIN_CONFIDENCE
        3. IoU against the previous frame at least iou_min
    """
    if len(recent_detections) < required_frames:
        return False

    window = recent_detections[-required_frames:]

    for detection in window:
        if not is_confident_detection(detection):
            return False

    first = window[0]
    previous = first
    for detection in window[1:]:
        if not is_same_class(first, detection):
            return False
        if compute_iou(previous, detection) < iou_min:
            return False
        previous = detection

    return True


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


def clamp_motion_command(value: float, max_value: float) -> float:
    """
    Clamps a movement command to +/- max_value so the sub never moves too aggressively.
    """
    return max(-max_value, min(max_value, value))


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
    Converts the live vision detection dict format:
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


def body_offset_to_image_norm(x_offset_body: float, y_offset_body: float, vertical_distance: float) -> tuple:
    """
    Inverse of back_project_to_body_frame(): given a metric body-frame offset
    (e.g. a tool's fixed camera-to-dropper/claw offset) and a known vertical
    distance, returns the normalized image position (x_norm, y_norm) that
    would back-project to that offset - i.e. where in the image the tool
    "points" at that depth. Used to draw an alignment reticle, see
    fsm/lineup_test_fsm.py. Falls back to the image center if vertical_distance
    isn't usable (mirrors get_target_error_meters' own "don't trust this" case).
    """
    if vertical_distance <= 0:
        return 0.5, 0.5

    u_norm = CAMERA_CX_NORM + (x_offset_body / vertical_distance) * CAMERA_FX_NORM
    v_norm = CAMERA_CY_NORM + (y_offset_body / vertical_distance) * CAMERA_FY_NORM
    y_norm = 1.0 - v_norm # convert back to this file's 0=bottom,1=top convention
    return u_norm, y_norm


def get_target_error_meters(x_norm: float, y_norm: float, sub_depth: float, target_depth: float) -> tuple:
    """
    Returns (x_error_m, y_error_m): how far the camera needs to move (meters,
    body frame) to be over the target, using the downward camera + pressure
    sensor depth instead of stereo depth (this camera has no depth sensing
    of its own). This is a pure camera-frame back-projection with no tool
    (dropper/claw) offset baked in - each FSM applies its own tool offset
    separately, with yaw rotation, at the alignment-target step.
    """
    vertical_distance = target_depth - sub_depth
    if vertical_distance <= 0:
        return 0.0, 0.0 # target isn't below the sub, don't trust this

    return back_project_to_body_frame(x_norm, y_norm, vertical_distance)


def is_target_centered_metric(x_error_m: float, y_error_m: float, x_tolerance: float = X_TOLERANCE_M, y_tolerance: float = Y_TOLERANCE_M) -> bool:
    """
    Checks if a metric alignment error (see get_target_error_meters) is
    close enough to zero to act.
    """
    return abs(x_error_m) <= x_tolerance and abs(y_error_m) <= y_tolerance


def nudge_xy_toward_target(shared_memory_object, x_error_m: float, y_error_m: float) -> tuple:
    """
    Nudges target_x/target_y by a small clamped step toward the target,
    but leaves target_z alone (heave is set directly from the pressure
    sensor instead, see set_hover_depth()) since heave doesn't come from
    the image at all here.

    x_error_m/y_error_m are already a world-frame delta (alignment target
    minus current sub position, see DropperHelpers/GrabberHelpers align_step)
    by the time they reach this function, so no camera-orientation sign
    correction belongs here - that's handled upstream at the camera/image
    stage (see DownfacingCamera in vision_model_main.py).
    """
    strafe_cmd = clamp_motion_command(X_GAIN * x_error_m, MAX_STRAFE_CMD)
    forward_cmd = clamp_motion_command(Y_GAIN * y_error_m, MAX_FORWARD_CMD)

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


def body_offset_to_world_offset(x_error_body: float, y_error_body: float, yaw_deg: float) -> tuple:
    """
    Rotates a body-frame (x=forward, y=left) offset into world-frame by the
    sub's current yaw, matching the rotation convention already used in
    modules/pid/pid_interface.py (scipy Rotation, degrees, applied about z).
    """
    rotation = Rotation.from_euler('z', yaw_deg, degrees=True)
    x_world, y_world, _ = rotation.apply([x_error_body, y_error_body, 0.0])
    return x_world, y_world


def distance_2d(point_a: tuple, point_b: tuple) -> float:
    """
    Returns the 2D Euclidean distance between two (x, y) world points.
    """
    return ((point_a[0] - point_b[0]) ** 2 + (point_a[1] - point_b[1]) ** 2) ** 0.5
