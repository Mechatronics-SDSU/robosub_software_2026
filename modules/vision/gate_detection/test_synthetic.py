#!/usr/bin/env python3
"""Sanity-check the detector/locator on synthetic frames -- no camera needed.

Builds fake image + depth + point cloud scenes that mimic the gate
(open water = invalid depth, pillars = near depth, correct color halves)
and asserts the pipeline reports the right identities and direction hints.
Covers camera roll, partially-out-of-frame pillars, and long range.

Run: python3 test_synthetic.py
"""

import math

import cv2
import numpy as np
import yaml

try:
    from .gate_locator import GateLocator
    from .pillar_detector import PillarDetector, LEFT, RIGHT, DIVIDER
except ImportError:  # running as a plain script from inside the package dir
    from gate_locator import GateLocator
    from pillar_detector import PillarDetector, LEFT, RIGHT, DIVIDER

W, H = 1280, 720
FX = FY = 700.0            # ~ZED Mini HD720 (90 deg horizontal FOV)
CX, CY = W / 2, H / 2
Z = 2.0                    # default pillar distance, m
DIAM = 0.051               # 2 in pipe

RED_DARK = (20, 25, 90)    # attenuated underwater red (BGR)
BLACK = (25, 28, 30)
WATER = (90, 70, 20)       # murky blue-green


def add_pillar(img, depth, x_top, y_top, top_bgr, bottom_bgr,
               top_len_m=0.61, bot_len_m=0.61, diameter_m=DIAM, z=Z,
               tilt_deg=0.0):
    """Draw a two-segment pillar. y_top may be negative (cropped by frame);
    tilt_deg simulates camera roll."""
    px_per_m = FY / z
    thick = max(2, int(round(diameter_m * FX / z)))
    dx = math.tan(math.radians(tilt_deg))

    def pt(dist_m):  # image point at dist_m along the pillar from its top
        return (int(round(x_top + dx * dist_m * px_per_m)),
                int(round(y_top + dist_m * px_per_m)))

    mask = np.zeros(img.shape[:2], np.uint8)
    segs = [(0.0, top_len_m, top_bgr),
            (top_len_m, top_len_m + bot_len_m, bottom_bgr)]
    for d0, d1, color in segs:
        if d1 > d0:
            cv2.line(img, pt(d0), pt(d1), color, thick)
            cv2.line(mask, pt(d0), pt(d1), 255, thick)
    depth[mask > 0] = z


def add_top_bar(img, depth, x0, x1, y=50, thick_px=6, z=Z, tilt_deg=0.0):
    dy = int(round((x1 - x0) * math.tan(math.radians(tilt_deg))))
    mask = np.zeros(img.shape[:2], np.uint8)
    cv2.line(img, (x0, y), (x1, y + dy), (200, 200, 200), thick_px)
    cv2.line(mask, (x0, y), (x1, y + dy), 255, thick_px)
    depth[mask > 0] = z


def make_point_cloud(depth):
    v, u = np.mgrid[0:H, 0:W].astype(np.float32)
    x = (u - CX) / FX * depth
    y = (v - CY) / FY * depth
    return np.stack([x, y, depth], axis=-1)


def empty_scene():
    img = np.full((H, W, 3), WATER, dtype=np.uint8)
    depth = np.full((H, W), np.nan, dtype=np.float32)  # open water: no depth
    return img, depth


def run_pipeline(scene_fn, n_frames=6):
    import pathlib
    with open(pathlib.Path(__file__).resolve().parent / "config.yaml") as f:
        cfg = yaml.safe_load(f)
    detector = PillarDetector(cfg, FX, FY)
    locator = GateLocator(cfg)
    obs = None
    for _ in range(n_frames):  # repeat frames to satisfy temporal voting
        img, depth = scene_fn()
        obs = locator.update(detector.detect(img, depth, make_point_cloud(depth)))
    return obs


# ---------------------------------------------------------------- scenes

def scene_full_gate():
    img, depth = empty_scene()
    add_pillar(img, depth, 260, 60, BLACK, RED_DARK)             # left
    add_pillar(img, depth, 1020, 60, RED_DARK, BLACK)            # right
    add_pillar(img, depth, 640, 60, RED_DARK, RED_DARK,          # divider
               top_len_m=0.3, bot_len_m=0.3)
    add_top_bar(img, depth, 230, 1050)
    return img, depth


def scene_full_gate_rolled():
    """Camera rolled 15 deg: pillars and bar tilted in the image."""
    img, depth = empty_scene()
    add_pillar(img, depth, 220, 40, BLACK, RED_DARK, tilt_deg=15)
    add_pillar(img, depth, 950, 40, RED_DARK, BLACK, tilt_deg=15)
    add_pillar(img, depth, 590, 40, RED_DARK, RED_DARK,
               top_len_m=0.3, bot_len_m=0.3, tilt_deg=15)
    add_top_bar(img, depth, 200, 990, y=30, tilt_deg=15)
    return img, depth


def scene_full_gate_far():
    """Gate at 5.5 m: 2-inch pipe is only ~6 px wide."""
    img, depth = empty_scene()
    add_pillar(img, depth, 495, 200, BLACK, RED_DARK, z=5.5)
    add_pillar(img, depth, 785, 200, RED_DARK, BLACK, z=5.5)
    return img, depth


def scene_left_only():
    img, depth = empty_scene()
    add_pillar(img, depth, 640, 60, BLACK, RED_DARK)
    return img, depth


def scene_right_only():
    img, depth = empty_scene()
    add_pillar(img, depth, 640, 60, RED_DARK, BLACK)
    return img, depth


def scene_left_cropped():
    """Only the lower ~3/4 of the left pillar in frame: 0.35 m of black plus
    all the red. The color boundary is at ~36% of the blob, not the middle."""
    img, depth = empty_scene()
    y_top = -int(0.26 * FY / Z)  # top 0.26 m of black is above the frame
    add_pillar(img, depth, 640, y_top, BLACK, RED_DARK)
    return img, depth


def scene_single_segment_cropped():
    """Only one red segment visible, cut off by the frame top. Must NOT be
    mistaken for the (also all-red) center divider."""
    img, depth = empty_scene()
    add_pillar(img, depth, 640, -10, RED_DARK, RED_DARK,
               top_len_m=0.3, bot_len_m=0.31)
    return img, depth


def scene_empty():
    return empty_scene()


# ----------------------------------------------------------------- tests

def main():
    obs = run_pipeline(scene_full_gate)
    assert obs.left and obs.right and obs.divider, obs.to_dict()
    assert obs.direction_hint == "none_needed", obs.direction_hint
    assert obs.left["position"][0] < obs.right["position"][0]
    assert abs(obs.left["depth_m"] - Z) < 0.15, obs.left
    assert all(c.identity in (LEFT, RIGHT, DIVIDER) for c in obs.candidates), \
        [c.to_dict() for c in obs.candidates]  # top bar must not survive
    sep = obs.right["position"][0] - obs.left["position"][0]
    print(f"PASS full gate: both pillars + divider, separation {sep:.2f} m, "
          f"midpoint {obs.gate_midpoint}")

    obs = run_pipeline(scene_full_gate_rolled)
    assert obs.left and obs.right, obs.to_dict()
    assert obs.direction_hint == "none_needed", obs.direction_hint
    print("PASS 15 deg camera roll: both pillars still identified")

    obs = run_pipeline(scene_full_gate_far)
    assert obs.left and obs.right, obs.to_dict()
    assert abs(obs.left["depth_m"] - 5.5) < 0.2, obs.left
    print("PASS gate at 5.5 m (2-inch pipe ~6 px wide): both pillars found")

    obs = run_pipeline(scene_left_only)
    assert obs.left and not obs.right, obs.to_dict()
    assert obs.direction_hint == "right", obs.direction_hint
    print("PASS left pillar only -> direction hint 'right'")

    obs = run_pipeline(scene_right_only)
    assert obs.right and not obs.left, obs.to_dict()
    assert obs.direction_hint == "left", obs.direction_hint
    print("PASS right pillar only -> direction hint 'left'")

    obs = run_pipeline(scene_left_cropped)
    assert obs.left and not obs.right, obs.to_dict()
    assert obs.direction_hint == "right", obs.direction_hint
    print("PASS cropped left pillar (color boundary off-center) -> 'right'")

    obs = run_pipeline(scene_single_segment_cropped)
    assert obs.divider is None, obs.to_dict()
    assert not obs.left and not obs.right, obs.to_dict()
    assert obs.direction_hint == "unknown", obs.direction_hint
    print("PASS cropped single-color segment: not mistaken for divider")

    obs = run_pipeline(scene_empty)
    assert not obs.left and not obs.right, obs.to_dict()
    assert obs.direction_hint == "unknown", obs.direction_hint
    print("PASS empty water -> direction hint 'unknown'")

    print("\nAll synthetic tests passed.")


if __name__ == "__main__":
    main()
