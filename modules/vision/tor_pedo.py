import math

class TorpedoLineup:
    def __init__(self):
        pass

    def vision_to_coordinates(
        self,
        vision_coordinate: float,
        vision_distance: float,
        fov_deg: float
    ) -> float:
         return vision_distance * math.sin(
            math.radians((vision_coordinate - 0.5) * fov_deg)
        )

    def dist_from_target(
        self,
        vision_distance: float,
        desired_distance: float
    ) -> float:
        
        return vision_distance - desired_distance


if __name__ == "__main__":
    lineup = TorpedoLineup(None)

    x_err = lineup.vision_to_coordinates(
        vision_coordinate=0.6,
        vision_distance=5.0,
        fov_deg=90.0
    )

    y_err = lineup.vision_to_coordinates(
        vision_coordinate=0.4,
        vision_distance=5.0,
        fov_deg=60.0
    )

    z_err = lineup.dist_from_target(
        vision_distance=5.0,
        desired_distance=3.0
    )

    print(
        f"X Error (m): {x_err:.2f}, "
        f"Y Error (m): {y_err:.2f}, "
        f"Z Error (m): {z_err:.2f}"
    )