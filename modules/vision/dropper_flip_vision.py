"""Flip-aware YOLO inference for the dropper task (Option 1 of
HORIZONTAL_FLIP_PLAN.md: cycling-orientation search with confirmed latch).

Why this exists: models/best.pt was trained with 0% horizontal-flip
augmentation, so a bin/prop viewed from the "wrong" side appears mirrored
and may not be recognized. Retraining is not an option, so this module
fixes it at inference time with ~zero fps cost (still exactly one
inference per frame).

Orientation cycle while searching (one orientation per frame):

    frame N   : RAW    - untouched
    frame N+1 : HFLIP  - horizontal mirror (cv2.flip(frame, 1))
    frame N+2 : VFLIP  - vertical mirror   (cv2.flip(frame, 0))
    frame N+3 : RAW    - cycle repeats ...

State machine:

  SEARCHING : cycle RAW -> HFLIP -> VFLIP until some orientation returns a
              detection. Within one full cycle (3 frames) of the object
              entering view, one orientation shows the model a trained view.
  CANDIDATE : an orientation produced a detection -> HOLD that orientation
              and require the detection to persist `confirm_frames`
              consecutive frames (default 4) before trusting it. A miss
              during candidacy falls back to SEARCHING at the next
              orientation in the cycle. Holding one orientation during
              candidacy also feeds the codebase's own target filters a
              consistent view (target_box_helpers.py: is_stable_target
              needs REQUIRED_STABLE_FRAMES=3 consecutive same-box frames,
              and the final pre-drop verify needs VERIFY_FRAME_COUNT=5 -
              both would be starved if the orientation kept changing).
  LATCHED   : detection survived confirm_frames -> stick with this
              orientation every frame. Unlatch back to SEARCHING after
              `unlatch_after_empty` consecutive empty frames, or externally
              via FlipArbiter.unlatch() (e.g. DVL says the sub swung >90
              yaw or crossed the object's plane - HORIZONTAL_FLIP_PLAN.md
              Option 2).

Note the layering: this module's confirm_frames only decides which
ORIENTATION to trust. Detections are still returned to the caller every
frame (including during candidacy) in true camera coordinates - the
FSM-side filters in target_box_helpers.py remain the authority on whether
a target is stable enough to act on. Suppressing frames here would starve
those filters of the history they need.

Safety invariants (see HORIZONTAL_FLIP_PLAN.md):
  1. Detections returned by FlipAwareYOLO.infer() are ALWAYS in true
     camera coordinates - x_norm is mirrored back on HFLIP frames and
     y_norm on VFLIP frames - so the FSM/PID lineup code needs zero
     changes and can never be steered backwards by a flipped frame.
  2. When a frame is flipped either way, the ZED point cloud is suppressed
     for that frame (depth reads -1.0) rather than letting
     _build_detections sample depth at the mirrored (wrong) pixel. The
     dropper uses the downfacing camera, which has no depth anyway.
  3. With no evidence the arbiter starts RAW - frame 0 behaves exactly
     like today's pipeline; this module can only add detections.
  4. Refuses to run on a MirroredCamera (bench-test wrapper) - stacking
     two flips would silently cancel out on real hardware.

Usage - drop-in for the dropper stack (modules/dropper/dropper_helpers.py
opens its model lazily; wrapped there):

    from modules.vision.vision_model_main import camera, yolo
    from modules.vision.dropper_flip_vision import FlipAwareYOLO

    self._camera = camera("downfacing")
    self._model  = FlipAwareYOLO(yolo(self.weights_path))
    # call site is unchanged:
    detections = self._model.infer(self._camera, headless=True, verbose=False)
"""
from __future__ import annotations

import sys

import cv2
import numpy as np

# Detection dict value layout, from vision_model_main._build_detections:
#   [label, class_id, conf, x_norm, y_norm, width, height, depth_m]
_CONF_IDX = 2
_XNORM_IDX = 3
_YNORM_IDX = 4

# Orientations, in search-cycle order. Values are cv2.flip codes
# (None = no flip, 1 = horizontal, 0 = vertical).
RAW = "RAW"
HFLIP = "HFLIP"
VFLIP = "VFLIP"
ORIENTATION_CYCLE = (RAW, HFLIP, VFLIP)
_CV2_FLIP_CODE = {RAW: None, HFLIP: 1, VFLIP: 0}


class FlipArbiter:
    """Pure orientation-decision state machine - no hardware, no cv2 calls,
    fully unit-testable.

    Parameters
    ----------
    confirm_frames     : consecutive detection frames required in one
                         orientation before it's trusted (CANDIDATE ->
                         LATCHED). Default 4 per the mission spec; the
                         FSM-side filters (REQUIRED_STABLE_FRAMES=3,
                         VERIFY_FRAME_COUNT=5 in target_box_helpers.py)
                         still apply on top for target-level stability.
    min_latch_conf     : a frame only counts as "detected" if some
                         detection's confidence is at least this. 0.0 = any
                         detection counts, which is the right default
                         because YOLOModel already applies its own conf
                         threshold before returning anything.
    unlatch_after_empty: consecutive empty frames in LATCHED mode before
                         falling back to SEARCHING. Keep this well above 1 -
                         single-frame dropouts (motion blur, particulates)
                         are routine underwater and must not restart the
                         search cycle mid-lineup.
    """

    SEARCHING = "SEARCHING"
    CANDIDATE = "CANDIDATE"
    LATCHED = "LATCHED"

    def __init__(self, confirm_frames: int = 4, min_latch_conf: float = 0.0,
                 unlatch_after_empty: int = 10):
        if confirm_frames < 1:
            raise ValueError("confirm_frames must be >= 1")
        if unlatch_after_empty < 1:
            raise ValueError("unlatch_after_empty must be >= 1")
        self.confirm_frames = int(confirm_frames)
        self.min_latch_conf = float(min_latch_conf)
        self.unlatch_after_empty = int(unlatch_after_empty)

        self.mode = self.SEARCHING
        self.latched_orientation = RAW
        self._cycle_idx = 0          # SEARCHING: index into ORIENTATION_CYCLE
        self._candidate_orientation = RAW
        self._hit_streak = 0         # CANDIDATE: consecutive detection frames
        self._empty_streak = 0       # LATCHED: consecutive empty frames

    def next_orientation(self) -> str:
        """Orientation (RAW | HFLIP | VFLIP) for the NEXT frame. Does not
        mutate state - call report_result() with the outcome afterwards."""
        if self.mode == self.LATCHED:
            return self.latched_orientation
        if self.mode == self.CANDIDATE:
            return self._candidate_orientation
        return ORIENTATION_CYCLE[self._cycle_idx]

    def report_result(self, orientation: str, detections: dict) -> None:
        """Feed back what happened on the frame that ran with `orientation`.
        Advances the cycle, builds/confirms a candidate, or unlatches."""
        detected = any(
            len(v) > _CONF_IDX and float(v[_CONF_IDX]) >= self.min_latch_conf
            for v in detections.values()
        )

        if self.mode == self.LATCHED:
            if detected:
                self._empty_streak = 0
                return
            # NOTE: a camera grab failure also reaches here as an empty dict
            # (YOLOModel.infer returns {} for both). Counting it toward the
            # unlatch streak is the safe default: a camera that stopped
            # delivering frames should put us back in SEARCHING, not pin us
            # to a stale orientation.
            self._empty_streak += 1
            if self._empty_streak >= self.unlatch_after_empty:
                self.unlatch()
            return

        if self.mode == self.CANDIDATE:
            if detected:
                self._hit_streak += 1
                if self._hit_streak >= self.confirm_frames:
                    self.mode = self.LATCHED
                    self.latched_orientation = self._candidate_orientation
                    self._empty_streak = 0
            else:
                # candidate died before confirming - resume the cycle at the
                # orientation AFTER the failed candidate
                self.mode = self.SEARCHING
                self._advance_cycle_past(self._candidate_orientation)
            return

        # SEARCHING
        if detected:
            self.mode = self.CANDIDATE
            self._candidate_orientation = orientation
            self._hit_streak = 1
            if self._hit_streak >= self.confirm_frames:  # confirm_frames == 1
                self.mode = self.LATCHED
                self.latched_orientation = orientation
                self._empty_streak = 0
        else:
            self._advance_cycle_past(orientation)

    def _advance_cycle_past(self, orientation: str) -> None:
        try:
            idx = ORIENTATION_CYCLE.index(orientation)
        except ValueError:
            idx = self._cycle_idx
        self._cycle_idx = (idx + 1) % len(ORIENTATION_CYCLE)

    def unlatch(self) -> None:
        """Force back to SEARCHING. Call externally when the DVL says the
        latched geometry is stale (yaw swing > ~90 deg since latching, or
        dead-reckoned position crossed the object's plane)."""
        self.mode = self.SEARCHING
        self._empty_streak = 0
        self._hit_streak = 0
        # resume the cycle at the orientation AFTER the stale latch: if the
        # latched view just went blind, another one is the better first guess
        self._advance_cycle_past(self.latched_orientation)

    def set_prior(self, orientation: str) -> None:
        """Seed the first orientation to try (DVL pose prior - Option 2 in
        HORIZONTAL_FLIP_PLAN.md). Only honored while SEARCHING; never
        overrides a candidate or latch, because live detections beat a
        dead-reckoned guess."""
        if self.mode == self.SEARCHING and orientation in ORIENTATION_CYCLE:
            self._cycle_idx = ORIENTATION_CYCLE.index(orientation)


class _FlipShimCamera:
    """Internal camera pass-through that FlipAwareYOLO hands to
    YOLOModel.infer(). .orientation selects how the grabbed frame is
    mirrored before YOLO sees it. On any flipped frame the point cloud is
    withheld so depth lookups can't silently sample the mirrored (wrong)
    pixel - depth then reads -1.0 for that frame, same as any camera
    without depth."""

    def __init__(self, inner):
        self._inner = inner
        self.orientation = RAW

    def _grab_with_pc(self):
        frame, point_cloud = self._inner._grab_with_pc()
        if frame is None:
            return None, None
        flip_code = _CV2_FLIP_CODE[self.orientation]
        if flip_code is None:
            return frame, point_cloud
        return cv2.flip(frame, flip_code), None

    # YOLOModel.infer only calls _grab_with_pc; close/depth stay with the
    # real camera object the caller already owns.


class FlipAwareYOLO:
    """Drop-in wrapper around a loaded YOLOModel. Same infer() call shape:

        detections = model.infer(cam, headless=True, verbose=False)

    Per frame it asks the FlipArbiter which orientation to run, mirrors the
    frame (via _FlipShimCamera) if told to, maps detection coordinates back
    into true camera coordinates, and reports the outcome to the arbiter.

    Preview/recording caveat: on flipped frames the annotated frame that
    headless=False / record_fn / overlay_fn receive is the FLIPPED view
    (boxes drawn where YOLO saw them, self-consistent with that image).
    Only the returned detection dict is guaranteed true-camera-coords.
    """

    def __init__(self, model, arbiter: FlipArbiter | None = None):
        self._model = model
        self.arbiter = arbiter if arbiter is not None else FlipArbiter()
        self._shims: dict[int, _FlipShimCamera] = {}

    @property
    def fps(self) -> float:
        return self._model.fps

    def _shim_for(self, cam) -> _FlipShimCamera:
        if type(cam).__name__ == "MirroredCamera":
            raise TypeError(
                "FlipAwareYOLO must not wrap a MirroredCamera feed - the two "
                "horizontal flips would cancel out and every HFLIP pass "
                "would silently test the unflipped image. Use the raw camera."
            )
        shim = self._shims.get(id(cam))
        if shim is None or shim._inner is not cam:
            shim = _FlipShimCamera(cam)
            self._shims[id(cam)] = shim
        return shim

    @staticmethod
    def _unmirror(detections: dict, orientation: str) -> dict:
        """Map detections made on a flipped frame back to true camera
        coordinates: HFLIP mirrors x_norm -> 1 - x_norm, VFLIP mirrors
        y_norm -> 1 - y_norm (exact to within half a pixel, matching
        _build_detections' 3-decimal rounding). width/height/class/conf are
        unaffected by either flip. Returns new lists - never mutates what
        the model handed back."""
        axis_idx = _XNORM_IDX if orientation == HFLIP else _YNORM_IDX
        out = {}
        for key, vals in detections.items():
            vals = list(vals)
            if len(vals) > axis_idx:
                vals[axis_idx] = round(min(1.0, max(0.0, 1.0 - float(vals[axis_idx]))), 3)
            out[key] = vals
        return out

    def infer(self, cam, **kwargs) -> dict:
        """Grab one frame via cam, run YOLO in the arbiter-chosen
        orientation, and return detections in TRUE camera coordinates
        ({} on grab failure or nothing detected - same contract as
        YOLOModel.infer). All keyword args (headless, verbose, overlay_fn,
        overlay_only, record_fn) pass straight through."""
        shim = self._shim_for(cam)
        orientation = self.arbiter.next_orientation()
        shim.orientation = orientation

        try:
            detections = self._model.infer(shim, **kwargs)
        except Exception:
            # Never let a single bad frame kill the mission loop from inside
            # the flip layer; report as empty so the arbiter keeps working.
            # (YOLOModel.infer itself already returns {} on grab failure -
            # this catches anything unexpected below it.)
            print("FlipAwareYOLO: inference raised, treating frame as empty", file=sys.stderr)
            detections = {}

        if orientation != RAW and detections:
            detections = self._unmirror(detections, orientation)

        self.arbiter.report_result(orientation, detections)
        return detections


if __name__ == "__main__":
    # Bench demo: laptop webcam + best.pt, prints which orientation each
    # frame ran in. Requires ultralytics + a camera.
    from modules.vision.vision_model_main import camera, yolo

    cam = camera("webcam")
    model = FlipAwareYOLO(yolo("models/best.pt"))
    try:
        while True:
            dets = model.infer(cam, headless=False, verbose=False)
            print(f"mode={model.arbiter.mode:9s} orient={model.arbiter.next_orientation():5s} "
                  f"dets={len(dets)} fps={model.fps:.1f}")
    except KeyboardInterrupt:
        pass
    finally:
        cam.close()