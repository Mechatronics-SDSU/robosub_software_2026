import math
import time

"""
    Helper functions for the torpedo FSM (fsm/torpedo_fsm.py).
    Keep this file as the support file for torpedo target selection,
    alignment math, and firing. The FSM should only handle state order.
"""

# TORPEDO ACTUATION TIMING, hardware pulse timing is not finalized yet, tune these---------------------------------------------
TORPEDO_FIRE_TIME_SEC = 0.5     # how long to hold the fire command before re-arming
TORPEDO_REARM_AFTER_FIRE = True # whether to re-arm (torpedo=0) after firing
TORPEDO_USE_TIMED_PULSE = True  # if False, fire_torpedo() sends fire and returns immediately, no wait/re-arm


class TorpedoLineup:
    """
    Helper functions for torpedo target selection, lineup math, and firing.
    """
    def __init__(self, shared_memory_object, torpedo_wrapper=None):
        self.shared_memory = shared_memory_object
        self.torpedo_wrapper = torpedo_wrapper # real TorpedoWrapper (modules/torpedo/TorpedoWrapper.py), or None for safe print placeholders

    def get_torpedo_circle_data(self) -> dict:
        """
        Placeholder for the real circle-detection vision call.

        MISSING: a real function that runs the vision pipeline and returns
        circles already grouped like this:
            {
                "wheels":      [{"x_norm": .., "y_norm": .., "radius": ..}, ...],
                "small_holes": [{"x_norm": .., "y_norm": .., "radius": ..}, ...],
                "big_holes":   [{"x_norm": .., "y_norm": .., "radius": ..}, ...],
            }
        Replace this function's body with that call once it exists.
        """
        return {"wheels": [], "small_holes": [], "big_holes": []}

    def has_valid_torpedo_data(self, circle_data: dict) -> bool:
        """
        Returns True if there is at least one hole (small or big) to aim at.
        """
        if circle_data is None:
            return False
        return bool(circle_data.get("small_holes")) or bool(circle_data.get("big_holes"))

    def choose_fallback_target(self, circle_data: dict):
        """
        Returns any available hole (big or small), or None if there are none.
        """
        holes = circle_data.get("big_holes", []) + circle_data.get("small_holes", [])
        if not holes:
            return None
        return holes[0]

    def choose_first_torpedo_target(self, circle_data: dict):
        """
        First torpedo prefers a big hole, falls back to any available hole.
        """
        big_holes = circle_data.get("big_holes", [])
        if big_holes:
            return big_holes[0]
        return self.choose_fallback_target(circle_data)

    def choose_second_torpedo_target(self, circle_data: dict):
        """
        Second torpedo prefers a small hole, falls back to any available hole.
        """
        small_holes = circle_data.get("small_holes", [])
        if small_holes:
            return small_holes[0]
        return self.choose_fallback_target(circle_data)

    def is_target_centered(self, target: dict, x_tolerance: float, y_tolerance: float) -> bool:
        """
        Checks if a target hole is close enough to the center of the frame (0.5, 0.5).
        """
        x_error = abs(target["x_norm"] - 0.5)
        y_error = abs(target["y_norm"] - 0.5)
        return x_error <= x_tolerance and y_error <= y_tolerance

    def verify_fire_position(self, target: dict, x_tolerance: float, y_tolerance: float, min_radius: float = 0.0) -> bool:
        """
        Final check before firing: the hole must be centered, and (optionally)
        big enough in frame to trust that we are close enough to the board.
        min_radius = 0 skips the radius check.
        """
        if not self.is_target_centered(target, x_tolerance, y_tolerance):
            return False
        if min_radius > 0.0 and target.get("radius", 0.0) < min_radius:
            return False
        return True

    def select_target_distance(self, distance_mode: str) -> float:
        """
        Selects the target firing distance in meters.
        close = 0.25m, medium = 0.30m (~1ft, standard), far = 0.46m (~1.5ft, extra points)
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

    def move_to_torpedo_target(
        self,
        shared_memory_object,
        current_x: float,
        current_y: float,
        current_z: float,
        target: dict,
        desired_distance: float,
        x_fov: float,
        y_fov: float
    ) -> None:
        """
        Converts a target hole's x_norm/y_norm into a movement offset and sends
        it to the PID/navigation system. Assumes the sub is roughly desired_distance
        away from the board (depth is left alone, since the circle data has no
        distance value to correct it with).
        """
        x_offset = self.vision_to_coordinates(target["x_norm"], desired_distance, x_fov)
        y_offset = self.vision_to_coordinates(target["y_norm"], desired_distance, y_fov)

        target_x = current_x + x_offset
        target_y = current_y + y_offset
        target_z = current_z # depth stays at the approach depth

        self.send_movement_command(shared_memory_object, target_x, target_y, target_z)

    def send_movement_command(self, shared_memory_object, target_x: float, target_y: float, target_z: float) -> None:
        """
        Sends the new target coordinates to the PID/navigation system.
        """
        shared_memory_object.target_x.value = target_x
        shared_memory_object.target_y.value = target_y
        shared_memory_object.target_z.value = target_z

    def fire_torpedo(self) -> None:
        """
        Fires one torpedo: makes sure it is armed first (firmware torpedo=0
        means armed), fires (torpedo=1), then holds and re-arms afterward if
        TORPEDO_USE_TIMED_PULSE/TORPEDO_REARM_AFTER_FIRE say to. Uses the real
        TorpedoWrapper if one was passed in, otherwise prints a safe
        placeholder (no hardware attached, e.g. test mode).

        MISSING: exact torpedo pulse timing is not finalized yet,
        TORPEDO_FIRE_TIME_SEC/TORPEDO_REARM_AFTER_FIRE are starting placeholders.
        """
        if self.torpedo_wrapper is not None:
            self.torpedo_wrapper.arm()
            self.torpedo_wrapper.fire()
        else:
            print("TORPEDO ARM PLACEHOLDER (no TorpedoWrapper attached)")
            print("TORPEDO FIRE PLACEHOLDER (no TorpedoWrapper attached)")

        if not TORPEDO_USE_TIMED_PULSE:
            return

        time.sleep(TORPEDO_FIRE_TIME_SEC)

        if TORPEDO_REARM_AFTER_FIRE:
            if self.torpedo_wrapper is not None:
                self.torpedo_wrapper.arm()
            else:
                print("TORPEDO RE-ARM PLACEHOLDER (no TorpedoWrapper attached)")
