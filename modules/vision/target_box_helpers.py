"""
    Shared vision target box helpers used by the dropper and grabber FSMs.
    Handles box math and the 3-frame target stability check.
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

# THRESHOLDS, adjust these as needed--------------------------------------------------------------------------------------------
MIN_CONFIDENCE        = 0.70
CENTER_TOLERANCE      = 0.08
SIZE_TOLERANCE        = 0.30
AREA_MATCH_THRESHOLD  = 0.70
REQUIRED_STABLE_FRAMES = 3


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
    Placeholder for real distance estimation.

    MISSING: depth_m from the vision pipeline is only reliable with a ZED
    camera at close range. To get a real forward distance for a downfacing
    (non-depth) camera, or when depth_m is unreliable, this needs one of:
        - a known real-world object size compared to the apparent box size
        - camera calibration (focal length, sensor size)
        - another range estimate (e.g. an acoustic pinger for grabber)
    For now this just returns depth_m if the vision pipeline provided one.
    """
    depth_m = detection[DEPTH_M]
    if depth_m is not None:
        return depth_m
    return 0.0 # unknown, caller should not trust this


def convert_target_to_movement(detection, current_x: float, current_y: float, current_z: float) -> tuple:
    """
    Placeholder for real vision-to-movement conversion.

    MISSING: a real conversion from x_norm/y_norm/depth into a movement offset,
    the same way torpedo_helpers.py does it with vision_to_coordinates() and a
    known desired_distance/camera FOV. Once camera FOV and a trusted distance
    are available for this camera, replace this with that math.
    For now this does not move the sub, it just returns the current position.
    """
    return current_x, current_y, current_z
