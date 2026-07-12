"""RoboSub 2026 gate detection on the ZED Mini (depth + color, no ML).

    from modules.vision.gate_detection import GateDetector

See gate_detector.py for the async API and the returned data format.
"""

from .gate_detector import GateDetector

__all__ = ["GateDetector"]
