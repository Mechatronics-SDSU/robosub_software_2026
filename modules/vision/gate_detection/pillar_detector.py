"""Finds pillar-shaped foreground objects in the depth map and classifies
them by their two-tone color pattern.

Pipeline (camera-agnostic; needs only image, depth, point cloud, focal length):
  1. Depth segmentation: pillars are the only near, valid-depth objects
     against open water (which returns far or invalid depth).
  2. Shape filter: keep tall, thin blobs whose *physical* width (median
     row width x depth / fx) matches the pipe diameter. Row width, not
     bounding-box width, so a rolled camera (pillar tilted in the image)
     barely changes the measurement.
  3. Color classification: find the row split that best separates the blob
     into a redder half and a darker half (the boundary can sit anywhere
     when the pillar is partially out of frame), using red dominance
     R/(G+B) -- relative, because red fades to dark brown underwater.
       black over red -> LEFT gate pillar
       red over black -> RIGHT gate pillar
       uniform + short + fully in frame -> center divider (ignored)
"""

from dataclasses import dataclass

import cv2
import numpy as np

LEFT = "left"
RIGHT = "right"
DIVIDER = "divider"
UNKNOWN = "unknown"


@dataclass
class PillarCandidate:
    identity: str                  # left / right / divider / unknown
    confidence: float              # 0..1, from color separation margin
    bbox: tuple                    # (x, y, w, h) in pixels
    position: np.ndarray | None    # (x, y, z) m in camera frame, or None
    depth_m: float
    phys_width_m: float
    phys_height_m: float
    touches_border: bool = False   # blob cut off by frame top/bottom
    redness_top: float = 0.0
    redness_bottom: float = 0.0

    def to_dict(self):
        return {
            "identity": self.identity,
            "confidence": round(float(self.confidence), 3),
            "bbox": [int(v) for v in self.bbox],
            "position": None if self.position is None
            else [round(float(v), 3) for v in self.position],
            "depth_m": round(float(self.depth_m), 3),
        }


class PillarDetector:
    def __init__(self, cfg, fx, fy):
        self.det = cfg["detection"]
        self.col = cfg["color"]
        self.depth_scale = float(cfg["camera"]["depth_scale"])
        self.fx = fx
        self.fy = fy
        close = int(self.det["close_px"])
        vopen = int(self.det["vertical_open_px"])
        self._close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (close, close))
        self._vopen_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, vopen))

    def detect(self, bgr, depth, point_cloud):
        """Return a list of PillarCandidate found in this frame."""
        mask = self._foreground_mask(depth)
        img_h = mask.shape[0]
        margin = int(self.det["border_margin_px"])
        candidates = []
        n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        for i in range(1, n_labels):
            x, y, w, h, area = stats[i]
            if area < self.det["min_area_px"]:
                continue

            comp = labels[y:y + h, x:x + w] == i
            # median width of the component's rows: unlike the bounding box,
            # this stays ~one pipe diameter when the camera rolls (15 deg of
            # roll widens each row by only 1/cos(15) ~ 3.5%)
            row_w = comp.sum(axis=1)
            width_px = float(np.median(row_w[row_w > 0]))
            if h / width_px < self.det["min_aspect"]:
                continue

            z = float(np.nanmedian(depth[y:y + h, x:x + w][comp])) * self.depth_scale
            phys_w = width_px * z / self.fx
            phys_h = h * z / self.fy
            if not (self.det["pillar_width_min_m"] <= phys_w <= self.det["pillar_width_max_m"]):
                continue
            if phys_h < self.det["pillar_min_height_m"]:
                continue

            touches = y <= margin or (y + h) >= img_h - margin
            identity, conf, r_top, r_bot = self._classify_color(
                bgr[y:y + h, x:x + w], comp, phys_h, touches)
            position = self._blob_position(point_cloud[y:y + h, x:x + w], comp)
            candidates.append(PillarCandidate(
                identity=identity, confidence=conf, bbox=(x, y, w, h),
                position=position, depth_m=z,
                phys_width_m=phys_w, phys_height_m=phys_h,
                touches_border=touches,
                redness_top=r_top, redness_bottom=r_bot))
        return candidates

    def _foreground_mask(self, depth):
        near = np.isfinite(depth) \
            & (depth * self.depth_scale > self.det["range_min_m"]) \
            & (depth * self.depth_scale < self.det["range_max_m"])
        mask = near.astype(np.uint8) * 255
        # fill small holes, then remove structures with little vertical
        # extent (the floating top bar, surface speckle)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self._close_kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self._vopen_kernel)
        return mask

    def _classify_color(self, bgr_roi, comp_mask, phys_height_m, touches_border):
        """Search for the row split that best separates the blob into a red
        part and a black part, then classify by which side is redder."""
        profile = self._row_redness(bgr_roi, comp_mask)
        p = profile[np.isfinite(profile)]
        n = len(p)
        if n == 0:
            return UNKNOWN, 0.0, float("nan"), float("nan")

        eps = 1e-6
        r_top = r_bot = float(np.mean(p))
        min_side = max(1, int(n * self.col["split_min_frac"]))
        if n - 2 * min_side >= 1:
            csum = np.cumsum(p)
            ks = np.arange(min_side, n - min_side)      # candidate split rows
            top = csum[ks - 1] / ks                     # mean redness above split
            bot = (csum[-1] - csum[ks - 1]) / (n - ks)  # mean redness below
            ratios = np.maximum(top, bot) / (np.minimum(top, bot) + eps)
            j = int(np.argmax(ratios))
            ratio, r_top, r_bot = float(ratios[j]), float(top[j]), float(bot[j])
            lo, hi = self.col["half_ratio_min"], self.col["half_ratio_saturate"]
            if ratio >= lo:
                conf = min(1.0, 0.5 + (ratio - lo) / max(hi - lo, eps))
                identity = RIGHT if r_top > r_bot else LEFT  # red-top = right
                return identity, conf, r_top, r_bot

        # Uniform color. Only call it the (all-red, 24") center divider when
        # the whole blob is inside the frame -- a gate pillar cropped down to
        # a single color segment would otherwise masquerade as the divider.
        if not touches_border and phys_height_m <= self.det["divider_max_height_m"]:
            return DIVIDER, 0.5, r_top, r_bot
        return UNKNOWN, 0.0, r_top, r_bot

    @staticmethod
    def _row_redness(bgr_roi, mask):
        """Per-row mean of R/(G+B) over the blob's own pixels; NaN where the
        blob has no pixels in that row."""
        f = bgr_roi.astype(np.float32)
        redness = f[..., 2] / (f[..., 0] + f[..., 1] + 1.0)
        count = mask.sum(axis=1)
        total = np.where(mask, redness, 0.0).sum(axis=1)
        out = np.full(len(count), np.nan, dtype=np.float32)
        rows = count > 0
        out[rows] = total[rows] / count[rows]
        return out

    def _blob_position(self, pc_roi, comp_mask):
        pts = pc_roi[comp_mask]
        pts = pts[np.isfinite(pts).all(axis=1)]
        if len(pts) < 10:
            return None
        # median per axis resists background pixels bleeding into the blob;
        # uniform scale is correct because X,Y are proportional to Z
        return np.median(pts, axis=0) * self.depth_scale
