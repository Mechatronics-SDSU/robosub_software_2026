import math

class TorpedoLineup:
    def __init__(self, shared_memory_object):
        self.shared_memory = shared_memory_object

    def vision_to_coordinates(
        self,
        vision_coordinate: float,
        vision_distance: float,
        fov_deg: float
    ) -> float:
         
         return vision_distance * math.sin(
            math.radians((vision_coordinate - 0.5) * fov_deg)
        )

    def depth_vision_lineup(
        self,
        vision_distance: float,
        desired_distance: float
    ) -> float:
        
        return vision_distance - desired_distance