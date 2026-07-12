"""Async gate detector for the ZED Mini.

    from modules.vision.gate_detection import GateDetector

    detector = GateDetector()                # config.yaml next to this file
    gate = await detector.get_gate()         # one frame -> gate dict
    dets = await detector.get_detections()   # same frame format as the YOLO API
    await detector.close()

or as a context manager:

    async with GateDetector() as detector:
        gate = await detector.get_gate()

The ZED SDK is blocking and single-threaded per camera handle, so every
SDK call (open / grab / close) is funneled through one dedicated worker
thread; the awaiting event loop is never blocked and concurrent calls are
serialized automatically.

get_gate() returns (positions in meters, camera frame: +x right, +y down,
+z forward):

    {
      "left":  {"position": [x, y, z], "depth_m": 2.31, "confidence": 0.87},
      "right":  ... or None when that pillar is not currently tracked,
      "divider": ... or None (the 24" red center pipe -- ignored for nav),
      "gate_midpoint": [x, y, z] or None (only when both pillars tracked),
      "direction_hint": "left" | "right" | "none_needed" | "unknown",
      "candidates": [ {"identity", "confidence", "bbox", "position",
                       "depth_m"}, ... ]   # raw per-frame, for debugging
    }

direction_hint says which way to yaw to find the missing pillar: seeing
only the left pillar (black over red) means the rest of the gate is to
the RIGHT, and vice versa. "none_needed" = both pillars in view.
"""

import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

try:
    from .zed_mini_camera import ZedMiniCamera
    from .gate_locator import GateLocator
    from .pillar_detector import PillarDetector
except ImportError:  # running as a plain script from inside the package dir
    from zed_mini_camera import ZedMiniCamera
    from gate_locator import GateLocator
    from pillar_detector import PillarDetector

CLASS_IDS = {"left": 0, "right": 1, "divider": 2, "unknown": 3}


class GateDetector:
    """Camera + detector + locator behind an async API.

    The camera opens lazily on the first call (or via open()), always on
    the internal worker thread. After close() the instance is done --
    create a new GateDetector to restart.
    """

    def __init__(self, config_path=None, svo_path=None, record_path=None):
        self.config_path = str(config_path or _HERE / "config.yaml")
        self.svo_path = svo_path
        self.record_path = record_path
        self.cam = None
        self._detector = None
        self._locator = None
        self._executor = ThreadPoolExecutor(max_workers=1,
                                            thread_name_prefix="gate-zed")

    async def open(self):
        await self._run(self._open_sync)
        return self

    async def get_gate(self) -> dict | None:
        """Grab and process one frame; return the gate observation dict
        (see module docstring). None only when an SVO replay is exhausted."""
        obs = await self._run(self._step_sync)
        return None if obs is None else obs.to_dict()

    async def get_detections(self) -> dict:
        """Grab and process one frame; return the codebase-standard dict
        {'obj1': [label, class_id, conf, x_norm, y_norm(0=bottom), w, h,
        depth_m]}. Labels: gate_left / gate_right / gate_divider /
        gate_unknown. Empty dict when nothing is in view."""
        obs = await self._run(self._step_sync)
        if obs is None:
            return {}
        w_img, h_img = self.cam.width, self.cam.height
        detections = {}
        for idx, c in enumerate(obs.candidates, start=1):
            x, y, w, h = c.bbox
            detections[f"obj{idx}"] = [
                f"gate_{c.identity}",
                CLASS_IDS[c.identity],
                round(float(c.confidence), 2),
                round((x + w / 2) / w_img, 3),         # x_norm: 0 left, 1 right
                round(1.0 - (y + h / 2) / h_img, 3),   # y_norm: 0 bottom, 1 top
                round(w / w_img, 3),
                round(h / h_img, 3),
                round(float(c.depth_m), 2),
            ]
        return detections

    async def close(self):
        await self._run(self._close_sync)
        self._executor.shutdown(wait=False)

    async def __aenter__(self):
        return await self.open()

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    # -- everything below runs on the worker thread ----------------------

    def _run(self, fn):
        return asyncio.get_running_loop().run_in_executor(self._executor, fn)

    def _open_sync(self):
        if self.cam is not None:
            return
        with open(self.config_path) as f:
            cfg = yaml.safe_load(f)
        self.cam = ZedMiniCamera(cfg["camera"], svo_path=self.svo_path,
                                 record_path=self.record_path)
        self._detector = PillarDetector(cfg, self.cam.fx, self.cam.fy)
        self._locator = GateLocator(cfg)

    def _step_sync(self):
        self._open_sync()
        frame = self.cam.get_frame()
        if frame is None:
            return None
        bgr, depth, pc = frame
        return self._locator.update(self._detector.detect(bgr, depth, pc))

    def _close_sync(self):
        if self.cam is not None:
            self.cam.close()
            self.cam = None
