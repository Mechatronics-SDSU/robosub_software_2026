from modules.vision.target_box_helpers import (
    REQUIRED_STABLE_FRAMES,
    is_stable_target,
    get_box_center,
)

"""
    Helper functions for the dropper FSM (fsm/dropper_fsm.py).
    Handles bin target selection, target verification, role bin labels,
    and placeholder dropper actuation. Keep repeated dropper logic here
    instead of inside the FSM.
"""

# ROLE BIN LABELS, these already exist as trained vision classes-----------------------------------------------------------------
SURVEY_AND_REPAIR_LABEL = "fire"
SEARCH_AND_RESCUE_LABEL = "blood"


class DropperHelpers:
    """
    Helper functions for dropper bin selection, lineup, and placeholder actuation.
    """
    def __init__(self, shared_memory_object):
        self.shared_memory = shared_memory_object
        self.detection_history = []

    def get_bin_label(self, role: str) -> str:
        """
        Returns the vision class label for the bin matching the given role.
        """
        if role == "search_and_rescue":
            return SEARCH_AND_RESCUE_LABEL
        return SURVEY_AND_REPAIR_LABEL # default to survey_and_repair

    def get_target_detections(self) -> list:
        """
        Placeholder for the real vision call.

        MISSING: a real function that grabs a frame and runs the model,
        returning a list of detections in this format:
            [class_label, class_id, conf, x_norm, y_norm, depth_m, width, height]
        Replace this function's body with that call once it exists.
        """
        return []

    def find_bin_detections(self, detections: list, bin_label: str) -> list:
        """
        Filters the detection list down to ones matching the given bin label.
        """
        return [detection for detection in detections if detection[0] == bin_label]

    def choose_bin_target(self, detections: list, bin_label: str):
        """
        Picks the first detection matching bin_label, or None if not found.
        """
        matches = self.find_bin_detections(detections, bin_label)
        if not matches:
            return None
        return matches[0]

    def reset_detection_history(self) -> None:
        """
        Clears the rolling detection history. Call this when starting to
        search for a new bin, so old frames don't count toward stability.
        """
        self.detection_history = []

    def check_target_stable(self, detection) -> bool:
        """
        Records a detection into the rolling history and checks if the last
        REQUIRED_STABLE_FRAMES detections form a stable target.
        """
        self.detection_history.append(detection)
        if len(self.detection_history) > REQUIRED_STABLE_FRAMES:
            self.detection_history.pop(0)
        return is_stable_target(self.detection_history)

    def is_target_centered(self, detection, x_tolerance: float, y_tolerance: float) -> bool:
        """
        Checks if the bin is close enough to the center of the frame (0.5, 0.5).
        """
        x_norm, y_norm = get_box_center(detection)
        return abs(x_norm - 0.5) <= x_tolerance and abs(y_norm - 0.5) <= y_tolerance

    def activate_dropper(self) -> None:
        """
        Placeholder for arming/activating the dropper mechanism.
        MISSING: real hardware/motor function, none exists in the project yet.
        """
        print("DROPPER ACTIVATE PLACEHOLDER")

    def drop_marker(self) -> None:
        """
        Placeholder for releasing one marker.
        MISSING: real hardware/motor function, none exists in the project yet.
        """
        print("DROPPER MARKER DROP PLACEHOLDER")

    def interact_with_magnetic_detector(self) -> None:
        """
        Placeholder for interacting with the magnetic detector near a bin.
        MISSING: real hardware function, none exists in the project yet.
        """
        print("DROPPER MAGNETIC DETECTOR INTERACTION PLACEHOLDER")
