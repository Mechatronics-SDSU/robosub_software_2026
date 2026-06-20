"""
Torpedo vision-to-coordinate translation math.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

try:
    from modules.vision.torpedo_config import TorpedoConfig, load_torpedo_config
except ModuleNotFoundError:  # Allows local testing outside the full repo layout.
    from torpedo_config import TorpedoConfig, load_torpedo_config


@dataclass(frozen=True)
class LineupOffset:
    """
    Meters to move from the position where the detection was measured.
    """

    x_m: float
    y_m: float
    z_m: float


@dataclass(frozen=True)
class LineupTarget:
    """
    Absolute PID target after applying a LineupOffset to a base position.
    """

    x: float
    y: float
    z: float
    offset: LineupOffset


class TorpedoLineup:
    """
    Converts normalized vision detections into meter offsets.

    x_norm and y_norm are normalized camera coordinates:
        x_norm: 0 = far-left, 1 = far-right
        y_norm: 0 = bottom, 1 = top

    depth_m is treated as forward camera Z distance because the uploaded
    vision main.py reads point_cloud Z at the detection center. With forward Z,
    lateral offset is z * tan(angle). If the vision module is later changed to
    return Euclidean range instead, switch tan() to sin().
    """

    def __init__(
        self,
        shared_memory_object=None,
        config: TorpedoConfig | None = None,
    ):
        self.shared_memory = shared_memory_object
        self.config = config or load_torpedo_config()

    def vision_to_offset_m(
        self,
        vision_coordinate: float,
        vision_distance_m: float,
        fov_deg: float,
    ) -> float:
        """
        Convert one normalized camera coordinate into a meter offset.
        """

        angle_deg = (vision_coordinate - 0.5) * fov_deg
        return vision_distance_m * math.tan(math.radians(angle_deg))

    def depth_vision_lineup(
        self,
        vision_distance_m: float,
        desired_distance_m: float,
    ) -> float:
        """
        Positive means the target is farther than desired.
        """

        return vision_distance_m - desired_distance_m

    def detection_to_offset(
        self,
        target: dict,
        desired_distance_m: float,
    ) -> LineupOffset:
        """
        Convert an averaged vision target into movement offsets in meters.
        """

        x_offset = self.vision_to_offset_m(
            target["x"],
            target["z"],
            self.config.camera_fov_x_deg,
        )
        y_offset = self.vision_to_offset_m(
            target["y"],
            target["z"],
            self.config.camera_fov_y_deg,
        )
        z_offset = self.depth_vision_lineup(target["z"], desired_distance_m)

        return LineupOffset(
            x_m=x_offset * self.config.x_gain * self.config.x_sign,
            y_m=y_offset * self.config.y_gain * self.config.y_sign,
            z_m=z_offset * self.config.z_gain * self.config.z_sign,
        )

    def detection_to_target(
        self,
        base_x: float,
        base_y: float,
        base_z: float,
        target: dict,
        desired_distance_m: float,
    ) -> LineupTarget:
        """
        Convert an averaged vision target into an absolute PID target.
        """

        offset = self.detection_to_offset(target, desired_distance_m)

        return LineupTarget(
            x=base_x + offset.x_m,
            y=base_y + offset.y_m,
            z=base_z + offset.z_m,
            offset=offset,
        )

    def target_is_aligned(
        self,
        target: dict,
        desired_distance_m: float,
        x_buffer: float,
        y_buffer: float,
        z_buffer_m: float,
    ) -> bool:
        """
        True when the detection itself is centered and at shooting distance.
        """

        return (
            abs(target["x"] - 0.5) <= x_buffer
            and abs(target["y"] - 0.5) <= y_buffer
            and abs(target["z"] - desired_distance_m) <= z_buffer_m
        )


