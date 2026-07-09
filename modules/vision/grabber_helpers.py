from modules.vision.target_box_helpers import (
    REQUIRED_STABLE_FRAMES,
    is_stable_target,
    get_box_center,
)

"""
    Helper functions for the grabber FSM (fsm/grabber_fsm.py).
    Handles item/basket target selection, target verification, role item
    labels, and placeholder claw/surfacing actuation. Keep repeated grabber
    logic here instead of inside the FSM.
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


class GrabberHelpers:
    """
    Helper functions for grabber item/basket selection, lineup, and placeholder actuation.
    """
    def __init__(self, shared_memory_object):
        self.shared_memory = shared_memory_object
        self.detection_history = []

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
        Placeholder for the real vision call.

        MISSING: a real function that grabs a frame and runs the model,
        returning a list of detections in this format:
            [class_label, class_id, conf, x_norm, y_norm, depth_m, width, height]
        Replace this function's body with that call once it exists.
        """
        return []

    def find_label_detections(self, detections: list, label: str) -> list:
        """
        Filters the detection list down to ones matching the given label.
        """
        return [detection for detection in detections if detection[0] == label]

    def choose_item_target(self, detections: list, remaining_items: list):
        """
        Picks the first detection matching any label still in remaining_items,
        or None if not found.
        """
        for label in remaining_items:
            matches = self.find_label_detections(detections, label)
            if matches:
                return matches[0]
        return None

    def choose_basket_target(self, detections: list, basket_label: str):
        """
        Picks the first detection matching basket_label, or None if not found.
        """
        matches = self.find_label_detections(detections, basket_label)
        if not matches:
            return None
        return matches[0]

    def reset_detection_history(self) -> None:
        """
        Clears the rolling detection history. Call this when starting to
        search for a new item or basket, so old frames don't count toward stability.
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
        Checks if the item/basket is close enough to the center of the frame (0.5, 0.5).
        """
        x_norm, y_norm = get_box_center(detection)
        return abs(x_norm - 0.5) <= x_tolerance and abs(y_norm - 0.5) <= y_tolerance

    def open_claw(self) -> None:
        """
        Placeholder for opening the claw.
        MISSING: real hardware/motor function, none exists in the project yet.
        """
        print("GRABBER OPEN CLAW PLACEHOLDER")

    def close_claw(self) -> None:
        """
        Placeholder for closing the claw.
        MISSING: real hardware/motor function, none exists in the project yet.
        """
        print("GRABBER CLOSE CLAW PLACEHOLDER")

    def grab_object(self) -> None:
        """
        Placeholder for grabbing the currently aligned item.
        MISSING: real hardware/motor function, none exists in the project yet.
        """
        print("GRABBER GRAB OBJECT PLACEHOLDER")

    def release_object(self) -> None:
        """
        Placeholder for releasing the currently held item into the basket.
        MISSING: real hardware/motor function, none exists in the project yet.
        """
        print("GRABBER RELEASE OBJECT PLACEHOLDER")

    def surface_in_octagon(self) -> None:
        """
        Placeholder for surfacing while staying inside the octagon.
        MISSING: real hardware/movement function, none exists in the project yet.
        """
        print("GRABBER SURFACE IN OCTAGON PLACEHOLDER")

    def face_target_icon(self, icon_label: str) -> None:
        """
        Placeholder for turning to face the given icon.
        MISSING: real heading/movement function, none exists in the project yet.
        """
        print(f"GRABBER FACE TARGET ICON PLACEHOLDER: {icon_label}")
