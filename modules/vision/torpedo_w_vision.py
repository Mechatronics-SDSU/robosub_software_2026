import math


class TorpedoDetection:
    """
    Small class for storing one vision detection.
    The parser below fills this in from the vision dictionary.
    """
    def __init__(self):
        self.found = False
        self.confidence = 0.0
        self.x = 0.5
        self.y = 0.5
        self.distance = 0.0
        self.bbox = None


class TorpedoLineup:
    """
    Helper functions for torpedo lineup math and checks.
    Keep this file as the support file for the torpedo FSM.
    """
    def __init__(self, shared_memory_object):
        self.shared_memory = shared_memory_object
        self.bbox_area_history = []

    def call_vision_pipeline(self):
        """
        Placeholder for the real vision pipeline call.

        Replace this with the actual function that opens the ZED camera,
        runs YOLO, and returns the detection dictionary.
        """
        return {}

    def parse_detection(self, vision_dict: dict) -> TorpedoDetection:
        """
        Reads the returned vision dictionary and puts the useful values
        into a TorpedoDetection object.

        Expected dictionary keys for now:
            found or detected
            confidence
            x
            y
            distance
            bbox
        """
        detection = TorpedoDetection()

        if vision_dict is None:
            return detection

        detection.found = bool(
            vision_dict.get("found", vision_dict.get("detected", False))
        )
        detection.confidence = float(vision_dict.get("confidence", 0.0))
        detection.x = float(vision_dict.get("x", 0.5))
        detection.y = float(vision_dict.get("y", 0.5))
        detection.distance = float(vision_dict.get("distance", 0.0))
        detection.bbox = vision_dict.get("bbox", None)

        return detection

    def confidence_passed(self, detection: TorpedoDetection, min_confidence: float) -> bool:
        """
        Checks if the model confidence is high enough.
        """
        if not detection.found:
            return False
        return detection.confidence >= min_confidence

    def get_bbox_area(self, bbox) -> float:
        """
        Placeholder for bounding box area checking.

        Expected bbox format for now:
            [x1, y1, x2, y2]

        If the real vision pipeline uses another format, update this one
        function instead of changing the FSM.
        """
        if bbox is None:
            return 0.0

        if len(bbox) < 4:
            return 0.0

        width = abs(float(bbox[2]) - float(bbox[0]))
        height = abs(float(bbox[3]) - float(bbox[1]))
        return width * height

    def bbox_area_passed(self, bbox) -> bool:
        """
        Basic check that the bounding box has a valid area.
        This can be expanded later if needed.
        """
        return self.get_bbox_area(bbox) > 0.0

    def bbox_stability_passed(self, bbox, history_size: int, tolerance: float) -> bool:
        """
        Checks whether the bounding box area is staying similar across
        recent frames.

        tolerance should be a decimal value:
            0.20 means 20 percent difference is allowed.
        """
        area = self.get_bbox_area(bbox)

        # If boxes are not implemented yet, this should fail safely.
        if area <= 0.0:
            return False

        self.bbox_area_history.append(area)

        if len(self.bbox_area_history) > history_size:
            self.bbox_area_history.pop(0)

        if len(self.bbox_area_history) < history_size:
            return False

        average_area = sum(self.bbox_area_history) / len(self.bbox_area_history)
        if average_area <= 0.0:
            return False

        for old_area in self.bbox_area_history:
            percent_error = abs(old_area - average_area) / average_area
            if percent_error > tolerance:
                return False

        return True

    def target_check_passed(
        self,
        detection: TorpedoDetection,
        min_confidence: float,
        history_size: int,
        bbox_tolerance: float
    ) -> bool:
        """
        Runs the two main target confirmation checks:
            1. confidence check
            2. bounding box stability check
        """
        if not self.confidence_passed(detection, min_confidence):
            return False

        if not self.bbox_stability_passed(detection.bbox, history_size, bbox_tolerance):
            return False

        return True

    def select_target_distance(self, distance_mode: str) -> float:
        """
        Selects the target distance in meters.
        """
        if distance_mode == "close":
            return 0.25
        if distance_mode == "far":
            return 0.46
        return 0.30

    def vision_to_coordinates(
        self,
        vision_coordinate: float,
        vision_distance: float,
        fov_deg: float
    ) -> float:
        """
        Converts a normalized vision position into a real movement offset.
        vision_coordinate is expected to be from 0.0 to 1.0.
        """
        return vision_distance * math.sin(
            math.radians((vision_coordinate - 0.5) * fov_deg)
        )

    def depth_vision_lineup(
        self,
        vision_distance: float,
        desired_distance: float
    ) -> float:
        """
        Returns how much the submarine needs to move forward/back
        to reach the desired distance.
        """
        return vision_distance - desired_distance

    def calculate_target_coordinates(
        self,
        current_x: float,
        current_y: float,
        current_z: float,
        detection: TorpedoDetection,
        desired_distance: float,
        x_fov: float,
        y_fov: float
    ) -> tuple:
        """
        Calculates the new coordinate target for PID/navigation.
        All returned values are in meters.
        """
        x_offset = self.vision_to_coordinates(detection.x, detection.distance, x_fov)
        y_offset = self.vision_to_coordinates(detection.y, detection.distance, y_fov)
        z_offset = self.depth_vision_lineup(detection.distance, desired_distance)

        target_x = current_x + x_offset
        target_y = current_y + y_offset
        target_z = current_z + z_offset

        return target_x, target_y, target_z

    def send_movement_command(self, shared_memory_object, target_x: float, target_y: float, target_z: float) -> None:
        """
        Sends the new target coordinates to the PID/navigation system.
        """
        shared_memory_object.target_x.value = target_x
        shared_memory_object.target_y.value = target_y
        shared_memory_object.target_z.value = target_z

    def lineup_passed(
        self,
        detection: TorpedoDetection,
        desired_distance: float,
        x_tolerance: float,
        y_tolerance: float,
        distance_tolerance: float
    ) -> bool:
        """
        Final lineup check before firing.
        Assumes x and y are normalized vision values where 0.5 is center.
        """
        x_error = abs(detection.x - 0.5)
        y_error = abs(detection.y - 0.5)
        distance_error = abs(detection.distance - desired_distance)

        if x_error > x_tolerance:
            return False
        if y_error > y_tolerance:
            return False
        if distance_error > distance_tolerance:
            return False

        return True

    def fire_torpedo(self) -> None:
        """
        Placeholder for the torpedo activation code.
        Replace this with the real hardware function.
        """
        print("TORPEDO FIRE PLACEHOLDER")
