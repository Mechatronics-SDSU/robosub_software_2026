# Gate detection (ZED Mini)

Detects the two RoboSub 2026 gate pillars using ZED Mini depth + color —
no ML model. Left pillar = black over red, right pillar = red over black;
that asymmetry means seeing *one* pillar tells you which way the other one
is. The all-red 24" center divider is detected and ignored.

## Usage

```python
from modules.vision.gate_detection import GateDetector

detector = GateDetector()            # reads config.yaml next to this file
gate = await detector.get_gate()     # grab + process one frame
await detector.close()

# or:
async with GateDetector() as detector:
    gate = await detector.get_gate()
```

All ZED SDK work runs on a dedicated worker thread, so `await` never
blocks the event loop and concurrent calls serialize safely.
`GateDetector(svo_path=...)` replays a recording; `record_path=...`
records one.

## Data returned by `get_gate()`

Positions are meters in the left-camera frame: +x right, +y down, +z forward.

```python
{
  "left":  {"position": [x, y, z], "depth_m": 2.31, "confidence": 0.87},
  "right":   # same shape, or None if that pillar is not tracked right now
  "divider": # same shape, or None (center pipe — ignore for navigation)
  "gate_midpoint": [x, y, z],  # aim point; only when both pillars tracked
  "direction_hint": "left" | "right" | "none_needed" | "unknown",
  "candidates": [  # raw single-frame detections, for debugging
    {"identity": "left", "confidence": 1.0, "bbox": [x, y, w, h],
     "position": [x, y, z], "depth_m": 2.0}, ...
  ]
}
```

`direction_hint` = which way to yaw to find the missing pillar
(`none_needed` = both in view, `unknown` = nothing identifiable yet).
Identities are smoothed over a 10-frame window (3 votes minimum), so a
pillar takes a few frames to appear and survives brief dropouts.

## Data returned by `get_detections()`

Same format as the YOLO vision API, one entry per raw candidate:

```python
{'obj1': ['gate_left', 0, 1.0, 0.204, 0.622, 0.015, 0.625, 2.0], ...}
#         label, class_id, conf, x_norm, y_norm(0=bottom), w, h, depth_m
```

Labels: `gate_left`(0) / `gate_right`(1) / `gate_divider`(2) /
`gate_unknown`(3).

## Files

- `gate_detector.py` — `GateDetector`, the async API
- `zed_mini_camera.py` — the ONLY file that touches pyzed (lazy import)
- `pillar_detector.py` — depth segmentation + shape/color classification
- `gate_locator.py` — temporal smoothing + direction hint
- `config.yaml` — every tunable, including `camera.depth_scale`
  (in-water depth correction — re-measure for the Mini's housing)
- `test_synthetic.py` — 8 no-camera behavioral tests:
  `python3 test_synthetic.py`
