"""Simple camera + YOLO API — no config.yaml required.

    from api import camera, yolo

    cam   = camera("zed")               # or camera("downfacing")
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
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO as _YOLO

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
    """ZED stereo camera with depth.

    Parameters
    ----------
    resolution : 'VGA' | 'HD720' | 'HD1080' | 'HD2K'  (default 'HD1080')
    fps        : frames per second                       (default 10)
    depth_mode : 'PERFORMANCE' | 'QUALITY' | 'ULTRA' | 'NEURAL'  (default 'PERFORMANCE')
    depth_minimum_distance : closest measurable depth in metres   (default 0.3)
    """

    def __init__(
        self,
        resolution: str = 'HD1080',
        fps: int = 10,
        depth_mode: str = 'PERFORMANCE',
        depth_minimum_distance: float = 0.3,
    ):
        import pyzed.sl as sl

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

        err = zed.open(init)
        if err != sl.ERROR_CODE.SUCCESS:
            print(f'ZED open failed: {err}', file=sys.stderr)
            sys.exit(1)

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

    def close(self) -> None:
        if self._zed is not None:
            self._zed.close()
            self._zed = None


class DownfacingCamera(_Camera):
    """Downward-facing USB camera via OpenCV. No depth available.

    Parameters
    ----------
    index : OpenCV VideoCapture device index (default 0)
    """

    def __init__(self, index: int = 0):
        self._cap = cv2.VideoCapture(index)
        if not self._cap.isOpened():
            print(f'Downfacing camera (index={index}) could not be opened.', file=sys.stderr)
            sys.exit(1)
        print(f'Downfacing camera opened — index={index}')

    def _grab_with_pc(self):
        ok, frame = self._cap.read()
        if not ok:
            return None, None
        return frame, None

    def grab(self) -> np.ndarray | None:
        """Return the next BGR frame, or None on read failure."""
        frame, _ = self._grab_with_pc()
        return frame

    # depth() stays at base-class default → always -1.0

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None


def camera(type: str, **kwargs) -> _Camera:  # noqa: A002
    """Open and return a camera.

    Parameters
    ----------
    type : "zed"        — ZED stereo camera (has depth)
           "downfacing" — downward-facing USB camera (no depth)

    All extra keyword arguments are forwarded to the camera class.

    ZED kwargs       : resolution, fps, depth_mode, depth_minimum_distance
    Downfacing kwargs: index

    Examples
    --------
    cam = camera("zed")
    cam = camera("zed", fps=30, depth_mode="ULTRA")
    cam = camera("downfacing", index=2)
    """
    t = type.strip().lower()
    if t == 'zed':
        return ZEDCamera(**kwargs)
    if t in ('downfacing', 'down'):
        return DownfacingCamera(**kwargs)
    raise ValueError(f'Unknown camera type "{type}". Use "zed" or "downfacing".')


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

    def infer(self, cam: _Camera, headless: bool = True, verbose: bool = False) -> dict:
        """Grab one frame from cam, run YOLO, and return a detection dict.

        Returns {} if the grab failed or nothing was detected.

        headless : True  — no window (default)
                   False — shows a preview window with YOLO overlays (press q to close)
        verbose  : True  — prints grab status, raw box count, and final detections
        """
        frame, point_cloud = cam._grab_with_pc()
        if frame is None:
            if verbose:
                print('[infer] frame grab failed — returned None')
            return {}

        if verbose:
            print(f'[infer] frame grabbed — {frame.shape[1]}x{frame.shape[0]}  device={self._device}')
            cv2.imwrite('debug_frame.jpg', frame)
            print('[infer] frame saved → debug_frame.jpg (check what the camera sees)')

        h, w = frame.shape[:2]
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

        raw_boxes = len(results[0].boxes) if results[0].boxes is not None else 0
        if verbose:
            print(f'[infer] YOLO raw boxes: {raw_boxes}  (conf>={self._conf})')

        if not headless:
            cv2.imshow('Vision preview (q to close)', results[0].plot())
            cv2.waitKey(1)

        detections = _build_detections(results[0], h, w, point_cloud, self._model.names)
        if verbose:
            print(f'[infer] detections: {detections}')
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
    # if not found locally, pass the raw name to ultralytics (triggers auto-download)
    weights = resolved if resolved.is_file() else path
    dev = device if device is not None else _auto_device()
    return YOLOModel(weights, dev, conf, iou, imgsz, max_det, augment)
