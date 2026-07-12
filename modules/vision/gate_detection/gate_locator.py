"""Turns per-frame pillar candidates into a smoothed gate estimate plus a
direction hint for the pillar that is not in view.

Direction logic exploits the asymmetric color pattern: seeing just the
left pillar (black over red) means the gate opening -- and the right
pillar -- is to the RIGHT, and vice versa. If a pillar's colors can't be
classified but the center divider is visible, geometry relative to the
divider resolves it instead.
"""

from collections import deque
from dataclasses import dataclass

import numpy as np

try:
    from .pillar_detector import LEFT, RIGHT, DIVIDER, UNKNOWN
except ImportError:  # running as a plain script from inside the package dir
    from pillar_detector import LEFT, RIGHT, DIVIDER, UNKNOWN


@dataclass
class GateObservation:
    left: dict | None            # {position, depth_m, confidence} or None
    right: dict | None
    divider: dict | None
    gate_midpoint: list | None   # [x, y, z] m in camera frame
    direction_hint: str          # left / right / none_needed / unknown
    candidates: list             # raw per-frame candidates (for debugging)

    def to_dict(self):
        return {
            "left": self.left,
            "right": self.right,
            "divider": self.divider,
            "gate_midpoint": self.gate_midpoint,
            "direction_hint": self.direction_hint,
            "candidates": [c.to_dict() for c in self.candidates],
        }


class GateLocator:
    def __init__(self, cfg):
        self.min_votes = int(cfg["tracking"]["min_votes"])
        self.expected_width = float(cfg["gate"]["expected_width_m"])
        self._history = deque(maxlen=int(cfg["tracking"]["smooth_window"]))

    def update(self, candidates):
        """Feed one frame's candidates; returns the smoothed observation."""
        frame = {}
        for ident in (LEFT, RIGHT, DIVIDER):
            located = [c for c in candidates
                       if c.identity == ident and c.position is not None]
            if located:
                frame[ident] = max(located, key=lambda c: c.confidence)
        self._history.append(frame)

        left = self._smoothed(LEFT)
        right = self._smoothed(RIGHT)
        divider = self._smoothed(DIVIDER)

        midpoint = None
        if left and right:
            midpoint = [round((a + b) / 2.0, 3)
                        for a, b in zip(left["position"], right["position"])]
            hint = "none_needed"
        elif left:
            hint = "right"
        elif right:
            hint = "left"
        else:
            hint = self._hint_from_divider(divider, candidates)

        return GateObservation(left=left, right=right, divider=divider,
                               gate_midpoint=midpoint, direction_hint=hint,
                               candidates=candidates)

    def _smoothed(self, ident):
        """Report an identity only if it persists across recent frames;
        position is the average over that window."""
        hits = [f[ident] for f in self._history if ident in f]
        if len(hits) < min(self.min_votes, self._history.maxlen):
            return None
        pos = np.mean([c.position for c in hits], axis=0)
        return {
            "position": [round(float(v), 3) for v in pos],
            "depth_m": round(float(np.mean([c.depth_m for c in hits])), 3),
            "confidence": round(float(np.mean([c.confidence for c in hits])), 3),
        }

    @staticmethod
    def _hint_from_divider(divider, candidates):
        """No gate pillar identified by color. If the red center divider is
        tracked and an unclassified pillar is in view, its side relative to
        the divider tells us which gate pillar it must be."""
        if divider is None:
            return "unknown"
        unknowns = [c for c in candidates
                    if c.identity == UNKNOWN and c.position is not None]
        if not unknowns:
            return "unknown"
        pillar = max(unknowns, key=lambda c: c.confidence * c.phys_height_m)
        # left of divider -> it's the left pillar -> the rest of the gate
        # (and the right pillar) lies to the right
        return "right" if pillar.position[0] < divider["position"][0] else "left"
