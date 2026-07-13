"""Simple camera + YOLO API — no config.yaml required.

    from api import camera, yolo

    cam   = camera("zed")               # or camera("downfacing") / camera("webcam")
    model = yolo("models/best.pt")

    detections = model.infer(cam)        # grabs one frame, runs YOLO → dict or {}
    depth_m    = cam.depth(0.5, 0.5)    # ZED only; metres at normalised position

    cam.close()

Detection dict format:
    {'obj1': ['ambulance', 2, 0.74, 0.20, 0.85, 0.30, 0.25, 5.0], ...}
    Fields: [label, class_id, conf, x_norm, y_norm, width, height, depth_m]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO as _YOLO

from modules.vision.target_box_helpers import (
    CAMERA_FX_NORM,
    CAMERA_FY_NORM,
    CAMERA_CX_NORM,
    CAMERA_CY_NORM,
    CAMERA_CALIB_WIDTH,
    CAMERA_CALIB_HEIGHT,
    DISTORTION_COEFFS,
)
from modules.vision.zed_diagnostics import diagnose_zed, check_zed_install_dir, ZED_INSTALL_DIR

_VISION_DIR = Path(__file__).resolve().parent


def _build_detections(r, frame_h: int, frame_w: int, point_cloud=None, class_names=None) -> dict:
    detections: dict = {}
    if r.boxes is None or len(r.boxes) == 0:
        return detections

    for idx, box in enumerate(r.boxes, start=1):
        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
        cls_id = int(box.cls[0].item())
        conf = round(float(box.conf[0].item()), 2)

        cx = int(np.clip((x1 + x2) // 2, 0, frame_w - 1))
        cy = int(np.clip((y1 + y2) // 2, 0, frame_h - 1))

        x_norm = round(cx / frame_w, 3)
        y_norm = round(1.0 - cy / frame_h, 3)
        width  = round((x2 - x1) / frame_w, 3)
        height = round((y2 - y1) / frame_h, 3)

        depth = -1.0
        if point_cloud is not None:
            _, pc_val = point_cloud.get_value(cx, cy)
            z = float(pc_val[2])
            if np.isfinite(z) and z > 0:
                depth = round(z, 2)

        names = class_names or {}
        label = names.get(cls_id, str(cls_id))
        detections[f'obj{idx}'] = [label, cls_id, conf, x_norm, y_norm, width, height, depth]

    return detections


def _auto_device():
    try:
        import torch
        if torch.cuda.is_available():
            return 0
        if torch.backends.mps.is_available():
            return 'mps'
    except Exception:
        pass
    return 'cpu'


# ── Cameras ───────────────────────────────────────────────────────────────────

class _Camera:
    """Base — use camera() factory, not this directly."""

    def grab(self) -> np.ndarray | None:
        raise NotImplementedError

    def depth(self, x_norm: float, y_norm: float) -> float:
        """Depth in metres at a normalised position. Always -1.0 for non-ZED cameras."""
        return -1.0

    def close(self) -> None:
        pass

    def _grab_with_pc(self) -> tuple[np.ndarray | None, object]:
        raise NotImplementedError


class ZEDCamera(_Camera):
    """ZED stereo camera with depth. Covers both standard USB ZED cameras
    (ZED/ZED2/ZED2i/ZED Mini) and GMSL2 ZED X-series cameras (ZED X, ZED X
    Mini) - the ZED SDK uses the same sl.Camera()/InitParameters API for
    both, per Stereolabs. NOT verified against real ZED X Mini hardware in
    this codebase yet - if open() fails or behaves unexpectedly on that
    hardware, check the ZED SDK version supports ZED X (4.0+) and check
    Stereolabs' current InitParameters docs for anything GMSL-specific that
    may have changed since this was written.

    Parameters
    ----------
    resolution : 'VGA' | 'HD720' | 'HD1080' | 'HD2K' | 'HD1200' | 'SVGA' | 'WVGA'
                 (default 'HD1080'; HD1200/SVGA/WVGA are ZED X-series-only and
                 silently skipped if the installed SDK doesn't expose them)
    fps        : frames per second                       (default 10)
    depth_mode : 'PERFORMANCE' | 'QUALITY' | 'ULTRA' | 'NEURAL'  (default 'PERFORMANCE')
    depth_minimum_distance : closest measurable depth in metres   (default 0.3)
    camera_id  : select among multiple connected/GMSL cameras by ID (0-3 on
                 boxes with multiple GMSL ports) via sl.InitParameters.input.
                 set_from_camera_id() - None (default) leaves the SDK to pick
                 automatically, same as before this param existed.
    """

    def __init__(
        self,
        resolution: str = 'VGA',
        fps: int = 60,
        depth_mode: str = 'PERFORMANCE',
        depth_minimum_distance: float = 0.3,
        camera_id: int | None = None,
    ):
        try:
            import pyzed.sl as sl
        except Exception as e:
            print(f'ZED SDK (pyzed.sl) failed to import: {e}', file=sys.stderr)
            print(f'Checked {ZED_INSTALL_DIR} exists: {check_zed_install_dir()}', file=sys.stderr)
            raise RuntimeError(f'pyzed.sl import failed: {e}') from e

        self._sl = sl

        _RES = {
            'VGA': sl.RESOLUTION.VGA,
            'HD720': sl.RESOLUTION.HD720,
            'HD1080': sl.RESOLUTION.HD1080,
            'HD2K': sl.RESOLUTION.HD2K,
        }
        for _r in ('HD1200', 'SVGA', 'WVGA'):
            if hasattr(sl.RESOLUTION, _r):
                _RES[_r] = getattr(sl.RESOLUTION, _r)

        _DEPTH = {
            'PERFORMANCE': sl.DEPTH_MODE.PERFORMANCE,
            'QUALITY': sl.DEPTH_MODE.QUALITY,
            'ULTRA': sl.DEPTH_MODE.ULTRA,
            'NEURAL': sl.DEPTH_MODE.NEURAL,
        }

        zed = sl.Camera()
        init = sl.InitParameters()
        init.camera_resolution = _RES.get(resolution.upper(), sl.RESOLUTION.HD1080)
        init.camera_fps = fps
        init.depth_mode = _DEPTH.get(depth_mode.upper(), sl.DEPTH_MODE.PERFORMANCE)
        init.coordinate_units = sl.UNIT.METER
        init.depth_minimum_distance = depth_minimum_distance
        if camera_id is not None:
            init.input.set_from_camera_id(camera_id)

        err = zed.open(init)
        if err != sl.ERROR_CODE.SUCCESS:
            print(f'ZED open failed: {err}', file=sys.stderr)
            diagnose_zed(emit=lambda msg: print(msg, file=sys.stderr))
            # Neither calling zed.close() nor leaving it to get collected naturally
            # avoids the SDK's own "sl::Camera::Open has not been called" message on
            # a never-opened Camera (measured on real hardware: both print it, twice).
            # `del zed` here, before raising, drops our own reference immediately -
            # raising an exception keeps this frame (and its locals, incl. `zed`)
            # alive via the traceback object until it's garbage collected, which on
            # an uncaught exception means "until interpreter shutdown", not "now".
            # Explicitly deleting the name here means the traceback captures this
            # frame *after* `zed` is already gone from its locals, so it can't pin
            # the object's lifetime out that far - the SDK's own message may still
            # print (that part seems to be triggered by destruction of a never-
            # opened Camera regardless), but promptly, not deferred to process exit.
            del zed
            # raise instead of sys.exit(1): sys.exit ends the whole process,
            # which makes a caller-side fallback (e.g. camera_source="zed"
            # falling back to "downfacing") impossible. A RuntimeError can be
            # caught by whoever called camera("zed") and handled - see
            # fsm/vision_test_fsm.py's zed_fallback support.
            raise RuntimeError(f'ZED open failed: {err}')

        info = zed.get_camera_information()
        res = info.camera_configuration.resolution
        print(f'ZED opened — {res.width}x{res.height}  depth={depth_mode.upper()}  fps={fps}')

        self._zed = zed
        self._runtime = sl.RuntimeParameters()
        self._image_mat = sl.Mat()
        self._point_cloud = sl.Mat()
        self._last_pc = None

    def _grab_with_pc(self):
        if self._zed.grab(self._runtime) != self._sl.ERROR_CODE.SUCCESS:
            return None, None
        self._zed.retrieve_image(self._image_mat, self._sl.VIEW.LEFT)
        self._zed.retrieve_measure(self._point_cloud, self._sl.MEASURE.XYZRGBA)
        self._last_pc = self._point_cloud
        frame = cv2.cvtColor(self._image_mat.get_data(), cv2.COLOR_RGBA2BGR)
        return frame, self._point_cloud

    def grab(self) -> np.ndarray | None:
        """Return the next BGR frame, or None on grab failure."""
        frame, _ = self._grab_with_pc()
        return frame

    def depth(self, x_norm: float, y_norm: float) -> float:
        """Return depth in metres at a normalised (x, y) position.

        Call after grab() or model.infer(cam) — uses the point cloud from the
        most recent frame. Returns -1.0 if the point is invalid or no frame
        has been grabbed yet.

        x_norm : 0 = left,   1 = right
        y_norm : 0 = bottom, 1 = top  (same convention as detection dict)
        """
        if self._last_pc is None:
            return -1.0
        w = self._last_pc.get_width()
        h = self._last_pc.get_height()
        cx = int(np.clip(x_norm * w, 0, w - 1))
        cy = int(np.clip((1.0 - y_norm) * h, 0, h - 1))
        _, pc_val = self._last_pc.get_value(cx, cy)
        z = float(pc_val[2])
        if np.isfinite(z) and z > 0:
            return round(z, 2)
        return -1.0

    def enable_svo_recording(self, path: str, compression: str = 'H264') -> bool:
        """Starts native ZED SVO recording to path - every subsequent grab()/
        infer() call writes a frame automatically, no per-frame work needed
        on the caller's side. Returns True on success. compression:
        'H264' (default) | 'H265' | 'LOSSLESS'.
        """
        sl = self._sl
        _COMPRESSION = {
            'H264': sl.SVO_COMPRESSION_MODE.H264,
            'H265': sl.SVO_COMPRESSION_MODE.H265,
            'LOSSLESS': sl.SVO_COMPRESSION_MODE.LOSSLESS,
        }
        rec_params = sl.RecordingParameters()
        rec_params.video_filename = str(path)
        rec_params.compression_mode = _COMPRESSION.get(compression.upper(), sl.SVO_COMPRESSION_MODE.H264)

        err = self._zed.enable_recording(rec_params)
        if err != sl.ERROR_CODE.SUCCESS:
            print(f'SVO recording enable failed: {err}', file=sys.stderr)
            return False
        print(f'SVO recording -> {path}  compression={compression.upper()}')
        return True

    def disable_svo_recording(self) -> None:
        if self._zed is not None:
            self._zed.disable_recording()

    def close(self) -> None:
        if self._zed is not None:
            self._zed.close()
            self._zed = None


class WebcamCamera(_Camera):
    """Plain USB webcam via OpenCV - no calibration, no undistortion, no
    orientation correction. Use this for a laptop/dev webcam or any camera
    that isn't the sub's calibrated downward-facing camera (see
    DownfacingCamera for that one, which subclasses this and adds the
    calibration-specific correction on top). No depth available.

    Parameters
    ----------
    index   : OpenCV VideoCapture device index (default 0)
    fps     : requested capture frame rate, or None to leave the camera's
              default alone (default None)
    quality : requested (width, height) capture resolution, or None to leave
              the camera's default alone (default None)
    """

    def __init__(self, index: int = 0, fps: int | None = None, quality: tuple | None = None):
        self._cap = cv2.VideoCapture(index)
        if not self._cap.isOpened():
            print(f'Webcam (index={index}) could not be opened.', file=sys.stderr)
            sys.exit(1)

        if fps is not None:
            self._cap.set(cv2.CAP_PROP_FPS, fps)
        if quality is not None:
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, quality[0])
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, quality[1])
        print(f'Webcam opened — index={index}' + (f'  requested {quality[0]}x{quality[1]}' if quality else '') + (f' @ {fps}fps' if fps else ''))

    def _grab_with_pc(self):
        ok, frame = self._cap.read()
        if not ok:
            return None, None
        return frame, None

    def grab(self) -> np.ndarray | None:
        """Return the next raw BGR frame, or None on read failure."""
        frame, _ = self._grab_with_pc()
        return frame

    # depth() stays at base-class default → always -1.0

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None


class DownfacingCamera(WebcamCamera):
    """The sub's calibrated downward-facing USB camera. No depth available
    (this camera has no stereo/depth sensing of its own - depth()
    intentionally stays at the base-class default of always -1.0, no
    depth_mode setting exists here on purpose, don't add one).

    Every grabbed frame is corrected before it's returned: fisheye
    undistortion (using the calibration intrinsics/distortion coefficients in
    modules/vision/target_box_helpers.py) followed by a vertical flip, since
    this camera is physically mounted backwards on the hull (y-axis reversed).
    Downstream vision math (target_box_helpers.py) assumes it's already
    getting an undistorted, correctly-oriented image - see that file's
    back_project_to_body_frame() for why. A plain webcam (laptop/dev camera)
    doesn't need any of this - use WebcamCamera / camera("webcam") for that.

    Parameters
    ----------
    index   : OpenCV VideoCapture device index (default 0)
    fps     : requested capture frame rate (default 30)
    quality : requested (width, height) capture resolution. Defaults to
              1280x720, not the calibration's full native 2894x1630 -
              this camera runs off a lower-tier ZED Box Mini with no GPU,
              so capturing/undistorting a smaller frame matters for
              real-world fps. Undistortion stays mathematically correct at
              whatever resolution is actually obtained regardless (K is
              rebuilt from the resolution-independent normalized intrinsics
              each time) - pass quality=(CAMERA_CALIB_WIDTH, CAMERA_CALIB_HEIGHT)
              if you specifically need full calibration resolution.
    """

    def __init__(self, index: int = 0, fps: int = 30, quality: tuple = (1280, 720)):
        super().__init__(index=index, fps=fps, quality=quality)
        print(f'  (calibrated downfacing camera - fisheye undistortion + mount-flip enabled)')

        self._requested_quality = quality
        self._map1 = None
        self._map2 = None
        self._warned_mismatch = False

    def _build_undistort_maps(self, frame_size: tuple) -> None:
        """
        Builds the fisheye undistortion maps for the actual captured frame
        size, scaling the normalized (resolution-independent) intrinsics up
        to that size - same request-then-verify pattern as
        live_calibration_check.py, but resolution-independent instead of
        requiring an exact match to the calibration's native resolution.
        """
        if frame_size != self._requested_quality and not self._warned_mismatch:
            print(
                f'WARNING: downfacing camera would not honor the requested resolution — live frame '
                f'size {frame_size} != requested {self._requested_quality}. Undistortion still applies '
                f'correctly (K is rescaled to the actual frame size), but check what resolutions this '
                f'camera actually supports if you need the exact requested size.',
                file=sys.stderr,
            )
            self._warned_mismatch = True

        w, h = frame_size
        K = np.array([
            [CAMERA_FX_NORM * w, 0.0, CAMERA_CX_NORM * w],
            [0.0, CAMERA_FY_NORM * h, CAMERA_CY_NORM * h],
            [0.0, 0.0, 1.0],
        ])
        D = np.array(DISTORTION_COEFFS)

        self._map1, self._map2 = cv2.fisheye.initUndistortRectifyMap(
            K, D, np.eye(3), K, frame_size, cv2.CV_16SC2
        )

    def _grab_with_pc(self):
        frame, _ = super()._grab_with_pc()
        if frame is None:
            return None, None

        frame_size = (frame.shape[1], frame.shape[0]) # (width, height)
        if self._map1 is None:
            self._build_undistort_maps(frame_size)

        # undistort first (maps were built for the raw, as-mounted geometry),
        # then flip to correct the backwards mount - flipping first would
        # shift the principal point out from under the undistortion maps
        corrected = cv2.remap(frame, self._map1, self._map2, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        corrected = cv2.flip(corrected, 0) # vertical flip (y-axis reversed mount), x is unaffected

        return corrected, None

    def grab(self) -> np.ndarray | None:
        """Return the next undistorted, mount-corrected BGR frame, or None on read failure."""
        frame, _ = self._grab_with_pc()
        return frame

    # depth() stays at base-class default → always -1.0


class MirroredCamera:
    """
    Thin wrapper that horizontally mirrors every grabbed frame from another
    camera - a pure ease-of-use convenience for manual bench testing (moving
    the camera left visibly moves things left on screen, like a selfie
    camera). Only ever wrap a "webcam" camera with this - never a
    "downfacing" or "zed" camera, since flipping would corrupt the real
    calibrated geometry any alignment math depends on. Used by
    fsm/lineup_test_fsm.py and fsm/vision_test_fsm.py.
    """
    def __init__(self, inner_camera):
        self._inner = inner_camera

    def _grab_with_pc(self):
        frame, point_cloud = self._inner._grab_with_pc()
        if frame is None:
            return None, None
        return cv2.flip(frame, 1), point_cloud

    def close(self) -> None:
        self._inner.close()


def camera(type: str, **kwargs) -> _Camera:  # noqa: A002
    """Open and return a camera.

    Parameters
    ----------
    type : "zed"        — ZED stereo camera (has depth)
           "downfacing" — the sub's calibrated downward-facing camera (fisheye
                          undistortion + mount-flip applied, no depth)
           "webcam"     — a plain USB webcam, e.g. a laptop's built-in camera
                          (no calibration/undistortion applied, no depth)

    All extra keyword arguments are forwarded to the camera class.

    ZED kwargs       : resolution, fps, depth_mode, depth_minimum_distance, camera_id
                       (camera_id picks among multiple/GMSL cameras e.g. ZED X Mini
                       on a multi-port box - see ZEDCamera's docstring)
    Downfacing kwargs: index, fps, quality (capture resolution, defaults to
                       1280x720 - lower than the calibration's native
                       2894x1630 for fps on the weak downcam compute box)
    Webcam kwargs    : index, fps, quality (both default to None - leaves the
                       camera's own defaults alone)

    Examples
    --------
    cam = camera("zed")
    cam = camera("zed", fps=30, depth_mode="ULTRA")
    cam = camera("downfacing", index=2)
    cam = camera("webcam")                  # laptop webcam, no undistortion
    """
    t = type.strip().lower()
    if t == 'zed':
        return ZEDCamera(**kwargs)
    if t in ('downfacing', 'down'):
        return DownfacingCamera(**kwargs)
    if t in ('webcam', 'usb'):
        return WebcamCamera(**kwargs)
    raise ValueError(f'Unknown camera type "{type}". Use "zed", "downfacing", or "webcam".')


# ── YOLO ──────────────────────────────────────────────────────────────────────

class YOLOModel:
    """Loaded YOLO model ready for per-frame inference."""

    def __init__(
        self,
        weights: Path,
        device,
        conf: float,
        iou: float,
        imgsz: int,
        max_det: int,
        augment: bool,
    ):
        self._model = _YOLO(weights)
        self._model.to(device)
        self._device = device
        self._conf = conf
        self._iou = iou
        self._imgsz = imgsz
        self._max_det = max_det
        self._augment = augment
        print(f'YOLO loaded — {weights}  device={device}')
        print(f'Model class names: {self._model.names}')

        # rolling fps (exponential moving average, smoother than raw instantaneous fps)
        self.fps = 0.0
        self._last_infer_time = None

    def infer(self, cam: _Camera, headless: bool = True, verbose: bool = False, overlay_fn=None, overlay_only: bool = False,
              record_fn=None) -> dict:
        """Grab one frame from cam, run YOLO, and return a detection dict.

        Returns {} if the grab failed or nothing was detected.

        headless     : True  — no preview window (default). Independent of record_fn - the
                       annotated frame still gets built and handed to record_fn even when
                       headless=True, it's only the on-screen cv2.imshow window that's skipped.
                       False — also shows a preview window with YOLO overlays + fps (press q to close)
        verbose      : True  — prints grab/predict stage timing, raw box count, and final detections
        overlay_fn   : optional callable (frame, detections) -> frame, called on the annotated
                       frame whenever one is built (headless=False and/or record_fn is set) - lets
                       a caller draw extra markers/lines without needing its own display/record loop.
                       Return the frame you want shown/recorded (usually the same frame, drawn on
                       in place).
        overlay_only : False (default) — overlay_fn draws on top of YOLO's own all-class box plot.
                       True — skip YOLO's box plot entirely and hand overlay_fn the plain undrawn
                       frame instead, so only whatever overlay_fn itself draws shows up (e.g. a
                       caller that only cares about one specific class/confidence and wants every
                       other detection disregarded, not just uncommented-on).
        record_fn    : optional callable (frame, detections) -> None, called with the final
                       annotated frame (after overlay_fn) every tick - e.g. write it to a
                       cv2.VideoWriter. Building the annotated frame has some cost even with no
                       preview window, but only happens when record_fn or headless=False needs it.

        self.fps holds a rolling estimate of the full grab+predict loop rate,
        updated every call — read it directly, or pass verbose=True to have
        it (and the per-stage breakdown) printed each frame.
        """
        loop_start = time.perf_counter()

        grab_start = time.perf_counter()
        frame, point_cloud = cam._grab_with_pc()
        grab_time = time.perf_counter() - grab_start

        if frame is None:
            if verbose:
                print('[infer] frame grab failed — returned None')
            return {}

        if verbose:
            print(f'[infer] frame grabbed — {frame.shape[1]}x{frame.shape[0]}  grab_time={grab_time * 1000:.1f}ms')

        h, w = frame.shape[:2]
        predict_start = time.perf_counter()
        results = self._model.predict(
            frame,
            conf=self._conf,
            iou=self._iou,
            imgsz=self._imgsz,
            max_det=self._max_det,
            augment=self._augment,
            device=self._device,
            verbose=False,
        )
        predict_time = time.perf_counter() - predict_start

        raw_boxes = len(results[0].boxes) if results[0].boxes is not None else 0
        if verbose:
            print(f'[infer] YOLO raw boxes: {raw_boxes}  (conf>={self._conf})  predict_time={predict_time * 1000:.1f}ms')

        # rolling fps over the full loop (grab + predict + everything below), not just predict -
        # this is what you'd actually perceive as "slow", not just model inference speed
        now = time.perf_counter()
        if self._last_infer_time is not None:
            dt = now - self._last_infer_time
            if dt > 0:
                instantaneous_fps = 1.0 / dt
                self.fps = instantaneous_fps if self.fps == 0.0 else (0.9 * self.fps + 0.1 * instantaneous_fps)
        self._last_infer_time = now

        detections = _build_detections(results[0], h, w, point_cloud, self._model.names)

        if not headless or record_fn is not None:
            annotated = frame.copy() if overlay_only else results[0].plot()
            cv2.putText(annotated, f'FPS: {self.fps:.1f}', (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            if overlay_fn is not None:
                annotated = overlay_fn(annotated, detections)
            if not headless:
                cv2.imshow('Vision preview (q to close)', annotated)
                cv2.waitKey(1)
            if record_fn is not None:
                record_fn(annotated, detections)

        if verbose:
            total_time = time.perf_counter() - loop_start
            print(f'[infer] detections: {detections}')
            print(f'[infer] fps={self.fps:.1f}  total_time={total_time * 1000:.1f}ms  (grab={grab_time * 1000:.1f}ms  predict={predict_time * 1000:.1f}ms)')
        return detections


def yolo(
    path: str,
    *,
    device=None,
    conf: float = 0.50,
    iou: float = 0.50,
    imgsz: int = 640,
    max_det: int = 4,
    augment: bool = False,
) -> YOLOModel:
    """Load and return a YOLO model.

    Parameters
    ----------
    path    : path to .pt weights file
    device  : 'cpu', 'mps', or 0 for CUDA — auto-detected if None
    conf    : confidence threshold        (default 0.50)
    iou     : NMS IoU threshold           (default 0.50)
    imgsz   : inference image size        (default 640)
    max_det : max detections per frame    (default 4)
    augment : test-time augmentation      (default False)

    Examples
    --------
    model = yolo("models/best.pt")
    model = yolo("models/fire_v2.pt", conf=0.6, max_det=2)
    """
    resolved = Path(path).expanduser()
    if not resolved.is_absolute():
        resolved = _VISION_DIR / resolved
    if not resolved.is_file():
        raise FileNotFoundError(f'YOLO weights not found: {resolved}')
    dev = device if device is not None else _auto_device()
    return YOLOModel(resolved, dev, conf, iou, imgsz, max_det, augment)