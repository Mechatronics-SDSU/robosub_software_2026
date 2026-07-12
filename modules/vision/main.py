"""Vision Summer 2026 — live ZED + YOLO inference entry point.

Reads config.yaml, opens the ZED camera, and runs YOLO every frame.
Per-frame detections are returned as a dict:

    {
        'obj1': ['ambulance', 2, 0.74, 0.20, 0.85, 0.30, 0.25, 5.0],
        'obj2': ['fire',      1, 0.97, 0.30, 0.60, 0.18, 0.20, 11.2],
    }

Fields: [class_label, class_id, conf, x_norm, y_norm, width, height, depth_m]
  x_norm  : 0 = far-left,  1 = far-right  (normalised box centre)
  y_norm  : 0 = bottom,    1 = top         (normalised box centre, y-flipped)
  width   : normalised box width  (0–1)
  height  : normalised box height (0–1)
  depth_m : Euclidean distance to box centre in metres (-1 if unavailable)

Press q in the preview window to quit.
"""
from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

import cv2
import numpy as np
import yaml
from ultralytics import YOLO


# Canonical class map — must match training labels in vision_config.py
CLASS_NAMES: dict[int, str] = {
    0: 'firetruck',
    1: 'fire',
    2: 'ambulance',
    3: 'blood',
}

def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


_VISION_DIR = Path(__file__).resolve().parent
_DEFAULT_WEIGHTS = 'models/best.pt'


def resolve_weights_path(weights: str) -> Path:
    """Resolve a weights path from config.yaml.

    Relative paths are resolved against this script's directory (not the
    caller's cwd), so main.py works the same regardless of which machine or
    working directory it's launched from.
    """
    path = Path(weights).expanduser()
    if not path.is_absolute():
        path = _VISION_DIR / path
    if not path.is_file():
        raise FileNotFoundError(
            f'YOLO weights not found: {path}\n'
            f"Check 'model.weights' in config.yaml — it should point to a "
            f'.pt file that exists on this machine.'
        )
    return path


def _auto_device() -> str:
    try:
        import torch
        if torch.cuda.is_available():
            return 0
        if torch.backends.mps.is_available():
            return 'mps'
    except Exception:
        pass
    return 'cpu'

## ZED

def open_zed(cfg: dict):
    """Open the ZED camera from config; return (zed, runtime, image_mat, point_cloud).
    pyzed.sl is imported here so the file is importable on machines without the ZED SDK.
    """
    import pyzed.sl as sl

    _RESOLUTION_MAP = {
        'VGA':    sl.RESOLUTION.VGA,
        'HD720':  sl.RESOLUTION.HD720,
        'HD1080': sl.RESOLUTION.HD1080,
        'HD2K':   sl.RESOLUTION.HD2K,
    }
    for _res_name in ('HD1200', 'SVGA', 'WVGA'):
        if hasattr(sl.RESOLUTION, _res_name):
            _RESOLUTION_MAP[_res_name] = getattr(sl.RESOLUTION, _res_name)
    _DEPTH_MODE_MAP = {
        'PERFORMANCE': sl.DEPTH_MODE.PERFORMANCE,
        'QUALITY':     sl.DEPTH_MODE.QUALITY,
        'ULTRA':       sl.DEPTH_MODE.ULTRA,
        'NEURAL':      sl.DEPTH_MODE.NEURAL,
    }

    zed_cfg = cfg.get('zed', {})

    zed = sl.Camera()
    init = sl.InitParameters()

    res_key = str(zed_cfg.get('resolution', 'HD1080')).upper()
    init.camera_resolution = _RESOLUTION_MAP.get(res_key, sl.RESOLUTION.HD1080)
    init.camera_fps = int(zed_cfg.get('fps', 10))

    dm_key = str(zed_cfg.get('depth_mode', 'PERFORMANCE')).upper()
    init.depth_mode = _DEPTH_MODE_MAP.get(dm_key, sl.DEPTH_MODE.PERFORMANCE)

    init.coordinate_units = sl.UNIT.METER
    init.depth_minimum_distance = float(zed_cfg.get('depth_minimum_distance', 0.3))

    err = zed.open(init)
    if err != sl.ERROR_CODE.SUCCESS:
        print(f'ZED open failed: {err}', file=sys.stderr)
        sys.exit(1)

    cam_info = zed.get_camera_information()
    res = cam_info.camera_configuration.resolution
    print(f'ZED opened — {res.width}x{res.height}  depth={dm_key}  fps={init.camera_fps}')

    runtime     = sl.RuntimeParameters()
    image_mat   = sl.Mat()
    point_cloud = sl.Mat()

    return zed, runtime, image_mat, point_cloud, sl


## Webcam

def open_webcam(cfg: dict) -> cv2.VideoCapture:
    """Open a local webcam via OpenCV; return the VideoCapture object."""
    index = int(cfg.get('webcam', {}).get('index', 0))
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        print(f'Webcam index {index} could not be opened.', file=sys.stderr)
        sys.exit(1)
    print(f'Webcam opened — index={index}')
    return cap


## Detection Builder

def build_detections(
    r,
    frame_h: int,
    frame_w: int,
    point_cloud=None,
    class_names: dict[int, str] | None = None,
) -> dict:
    """Convert a YOLO result into the standard detection dict.

    point_cloud : sl.Mat when running with ZED, None when running with webcam.
                  When None, depth_m is always -1.

    Returns
    -------
    dict  e.g. {'obj1': ['ambulance', 2, 0.74, 0.20, 0.85, 0.30, 0.25, 5.0], ...}
    """
    detections: dict = {}
    if r.boxes is None or len(r.boxes) == 0:
        return detections

    for idx, box in enumerate(r.boxes, start=1):
        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
        cls_id = int(box.cls[0].item())
        conf   = round(float(box.conf[0].item()), 2)

        # Centre pixel — clamped to valid image bounds
        cx = int(np.clip((x1 + x2) // 2, 0, frame_w - 1))
        cy = int(np.clip((y1 + y2) // 2, 0, frame_h - 1))

        # Normalised spatial position
        x_norm = round(cx / frame_w, 3)
        # Invert y: image y=0 is top, but convention wants 0=bottom, 1=top
        y_norm = round(1.0 - cy / frame_h, 3)

        # Normalised box dimensions
        width  = round((x2 - x1) / frame_w, 3)
        height = round((y2 - y1) / frame_h, 3)

        # Depth: Z component of the point-cloud at box centre (ZED only)
        depth = -1.0
        if point_cloud is not None:
            _, pc_val = point_cloud.get_value(cx, cy)
            z = float(pc_val[2])
            if np.isfinite(z) and z > 0:
                depth = round(z, 2)

        names = class_names or CLASS_NAMES
        label = names.get(cls_id, str(cls_id))
        detections[f'obj{idx}'] = [label, cls_id, conf, x_norm, y_norm, width, height, depth]

    return detections

## Recorder

class Recorder:
    """Records raw MP4 video (and optionally an annotated copy).

    run_dir is computed once in main() and shared with _start_svo() so that
    video.mp4, recording.svo, and video_annotated.mp4 all land in the same folder.

    Output layout:
        <output_dir>/<YYYYMMDD_HHMMSS>/
            video.mp4                           ← mp4: true — raw frames, no annotations
            video_annotated.mp4                 ← annotated_mp4: true — YOLO boxes burned in
            recording.svo2                      ← svo: true (ZED only, via _start_svo)
    """

    def __init__(self, cfg: dict, fps: float, run_dir: Path | None = None):
        rec_cfg            = cfg.get('recording', {})
        self.enabled       = bool(rec_cfg.get('mp4', False))
        self._annotated_on = bool(rec_cfg.get('annotated_mp4', False))
        self._writer       = None
        self._writer_ann   = None
        self.frame_idx     = 0

        if not self.enabled:
            return

        # Use the shared run_dir if provided, otherwise make our own
        if run_dir is None:
            ts      = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            run_dir = Path(rec_cfg.get('output_dir', 'recordings')) / ts
            run_dir.mkdir(parents=True, exist_ok=True)
        self._base_dir       = run_dir
        self._video_path     = run_dir / 'video.mp4'
        self._video_ann_path = run_dir / 'video_annotated.mp4'
        self._fps            = fps

        print(f'[Recorder] output → {run_dir}')

    def write(self, frame: np.ndarray, annotated: np.ndarray) -> None:
        if not self.enabled:
            return

        # Lazy VideoWriter init — we need the frame size first
        if self._writer is None:
            h, w   = frame.shape[:2]
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            self._writer = cv2.VideoWriter(
                str(self._video_path), fourcc, self._fps, (w, h)
            )
            print(f'[Recorder] VideoWriter opened ({w}x{h} @ {self._fps:.0f} fps)')
            if self._annotated_on:
                self._writer_ann = cv2.VideoWriter(
                    str(self._video_ann_path), fourcc, self._fps, (w, h)
                )
                print(f'[Recorder] annotated VideoWriter opened')

        self._writer.write(frame)
        if self._annotated_on and self._writer_ann is not None:
            self._writer_ann.write(annotated)

        self.frame_idx += 1

    def close(self) -> None:
        if not self.enabled:
            return
        if self._writer is not None:
            self._writer.release()
        if self._writer_ann is not None:
            self._writer_ann.release()
        print(f'[Recorder] closed — {self.frame_idx} frames → {self._base_dir}')


## SVO Recording

def _start_svo(zed, sl, cfg: dict, run_dir: Path) -> None:
    """Enable ZED SVO recording into run_dir.
    Every subsequent zed.grab() call automatically writes a frame.
    Call zed.disable_recording() to stop.
    """
    _COMPRESSION_MAP = {
        'H264':     sl.SVO_COMPRESSION_MODE.H264,
        'H265':     sl.SVO_COMPRESSION_MODE.H265,
        'LOSSLESS': sl.SVO_COMPRESSION_MODE.LOSSLESS,
    }
    rec_cfg  = cfg.get('recording', {})
    comp_key = str(rec_cfg.get('svo_compression', 'H264')).upper()

    rec_params                  = sl.RecordingParameters()
    rec_params.video_filename   = str(run_dir / 'recording.svo2')
    rec_params.compression_mode = _COMPRESSION_MAP.get(comp_key, sl.SVO_COMPRESSION_MODE.H264)

    err = zed.enable_recording(rec_params)
    if err != sl.ERROR_CODE.SUCCESS:
        print(f'[SVO] enable_recording failed: {err}', file=sys.stderr)
        sys.exit(1)

    print(f'[SVO] recording → {rec_params.video_filename}  compression={comp_key}')


class VisionRuntime:
    """
    Small live vision wrapper for FSMs.

    The CLI main() below is still useful for testing and recording, but FSMs
    need a callable API that opens the camera/model once and returns one
    detection dict per call.
    """

    def __init__(self, config_path: str = 'config.yaml'):
        self.config_path = str(Path(config_path).expanduser())
        self.cfg: dict | None = None
        self.model = None
        self.source = None
        self.device = None
        self.yolo_cfg = {}
        self.classes = None

        self.zed = None
        self.runtime = None
        self.image_mat = None
        self.point_cloud = None
        self.sl = None
        self.cap = None

    def open(self) -> 'VisionRuntime':
        self.cfg = load_config(self.config_path)

        model_cfg = self.cfg.get('model', {})
        weights = resolve_weights_path(model_cfg.get('weights', _DEFAULT_WEIGHTS))
        self.device = model_cfg.get('device') or _auto_device()

        self.yolo_cfg = self.cfg.get('yolo', {})
        self.classes = self.cfg.get('classes', None)

        print(f'Loading weights: {weights}  device={self.device}')
        self.model = YOLO(weights)
        self.model.to(self.device)
        print(f'Model class names: {self.model.names}')
        print(f'Active classes filter: {self.classes}')

        self.source = self.cfg.get('source', 'zed').strip().lower()

        if self.source == 'zed':
            (
                self.zed,
                self.runtime,
                self.image_mat,
                self.point_cloud,
                self.sl,
            ) = open_zed(self.cfg)

        elif self.source == 'webcam':
            self.cap = open_webcam(self.cfg)

        else:
            raise ValueError(
                f'Unknown source "{self.source}". Set source to "zed" or "webcam".'
            )

        return self

    def get_detections(self) -> dict:
        if self.model is None:
            self.open()

        conf_thres = float(self.yolo_cfg.get('conf', 0.50))
        iou_thres = float(self.yolo_cfg.get('iou', 0.50))
        imgsz = int(self.yolo_cfg.get('imgsz', 640))
        max_det = int(self.yolo_cfg.get('max_det', 4))
        augment = bool(self.yolo_cfg.get('augment', False))

        if self.source == 'zed':
            if self.zed.grab(self.runtime) != self.sl.ERROR_CODE.SUCCESS:
                return {}

            self.zed.retrieve_image(self.image_mat, self.sl.VIEW.LEFT)
            self.zed.retrieve_measure(self.point_cloud, self.sl.MEASURE.XYZRGBA)

            frame = cv2.cvtColor(self.image_mat.get_data(), cv2.COLOR_RGBA2BGR)
            h, w = frame.shape[:2]

            results = self.model.predict(
                frame,
                conf=conf_thres,
                iou=iou_thres,
                imgsz=imgsz,
                max_det=max_det,
                classes=self.classes,
                augment=augment,
                device=self.device,
                verbose=False,
            )

            return build_detections(
                results[0],
                h,
                w,
                self.point_cloud,
                self.model.names,
            )

        if self.source == 'webcam':
            ok, frame = self.cap.read()
            if not ok:
                return {}

            h, w = frame.shape[:2]
            results = self.model.predict(
                frame,
                conf=conf_thres,
                iou=iou_thres,
                imgsz=imgsz,
                max_det=max_det,
                classes=self.classes,
                augment=augment,
                device=self.device,
                verbose=False,
            )

            return build_detections(
                results[0],
                h,
                w,
                point_cloud=None,
                class_names=self.model.names,
            )

        return {}

    def close(self) -> None:
        if self.zed is not None:
            self.zed.close()
            self.zed = None

        if self.cap is not None:
            self.cap.release()
            self.cap = None


_DEFAULT_RUNTIME: VisionRuntime | None = None


def open_vision(config_path: str = 'config.yaml') -> VisionRuntime:
    """Open the camera and model once for FSM usage."""

    global _DEFAULT_RUNTIME
    _DEFAULT_RUNTIME = VisionRuntime(config_path).open()
    return _DEFAULT_RUNTIME


def get_detections(runtime: VisionRuntime | None = None) -> dict:
    """Return one live detection dict for FSM usage."""

    global _DEFAULT_RUNTIME

    if runtime is None:
        if _DEFAULT_RUNTIME is None:
            _DEFAULT_RUNTIME = open_vision()
        runtime = _DEFAULT_RUNTIME

    return runtime.get_detections()


def build_live_detections(runtime: VisionRuntime | None = None) -> dict:
    """Backward-readable alias for get_detections()."""

    return get_detections(runtime)


def close_vision(runtime: VisionRuntime | None = None) -> None:
    global _DEFAULT_RUNTIME

    target = runtime or _DEFAULT_RUNTIME
    if target is not None:
        target.close()

    if runtime is None:
        _DEFAULT_RUNTIME = None


## Main

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else '')
    parser.add_argument(
        '--config', default='config.yaml',
        help='path to YAML config (default: config.yaml)',
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    headless = bool(cfg.get('headless', False))

    ## MODEL
    model_cfg = cfg.get('model', {})
    weights   = resolve_weights_path(model_cfg.get('weights', _DEFAULT_WEIGHTS))
    device    = model_cfg.get('device') or _auto_device()

    ## YOLO
    yolo_cfg   = cfg.get('yolo', {})
    conf_thres = float(yolo_cfg.get('conf',   0.50))
    iou_thres  = float(yolo_cfg.get('iou',    0.50))
    imgsz      = int(yolo_cfg.get('imgsz',    640))
    max_det    = int(yolo_cfg.get('max_det',  4))
    augment    = bool(yolo_cfg.get('augment', False))
    classes    = cfg.get('classes', None)  # None → all classes

    print(f'Loading weights: {weights}  device={device}')
    model = YOLO(weights)
    model.to(device)
    print(f'Model class names: {model.names}')
    print(f'Active classes filter: {classes}')

    ## Source
    source = cfg.get('source', 'zed').strip().lower()

    if source == 'zed':
        zed, runtime, image_mat, point_cloud, sl = open_zed(cfg)
        rec_fps = float(cfg.get('zed', {}).get('fps', 10))

        # Build shared run folder if any recording is active
        rec_cfg    = cfg.get('recording', {})
        mp4_on     = bool(rec_cfg.get('mp4', False))
        svo_on     = bool(rec_cfg.get('svo', False))
        run_dir    = None
        svo_active = False
        if mp4_on or svo_on:
            ts      = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            run_dir = Path(rec_cfg.get('output_dir', 'recordings')) / ts
            run_dir.mkdir(parents=True, exist_ok=True)
            print(f'[Recording] run folder → {run_dir}')

        recorder = Recorder(cfg, rec_fps, run_dir)
        if svo_on:
            _start_svo(zed, sl, cfg, run_dir)
            svo_active = True

        print('Running — press q to quit')
        try:
            while True:
                if zed.grab(runtime) != sl.ERROR_CODE.SUCCESS:
                    continue

                zed.retrieve_image(image_mat, sl.VIEW.LEFT)
                zed.retrieve_measure(point_cloud, sl.MEASURE.XYZRGBA)

                # RGBA → BGR for YOLO / cv2
                frame = cv2.cvtColor(image_mat.get_data(), cv2.COLOR_RGBA2BGR)
                h, w  = frame.shape[:2]

                results = model.predict(
                    frame,
                    conf=conf_thres, iou=iou_thres, imgsz=imgsz,
                    max_det=max_det, classes=classes,
                    augment=augment, device=device, verbose=False,
                )

                detections = build_detections(results[0], h, w, point_cloud, model.names)
                if detections:
                    print(detections)

                annotated = results[0].plot()
                recorder.write(frame, annotated)
                if not headless:
                    cv2.imshow('ZED + YOLO  (press q to quit)', annotated)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break

        finally:
            if svo_active:
                zed.disable_recording()
                print('[SVO] recording stopped')
            recorder.close()
            zed.close()
            if not headless:
                cv2.destroyAllWindows()
            print('Done.')

    elif source == 'webcam':
        cap     = open_webcam(cfg)
        rec_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

        rec_cfg = cfg.get('recording', {})
        mp4_on  = bool(rec_cfg.get('mp4', False))
        run_dir = None
        if mp4_on:
            ts      = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            run_dir = Path(rec_cfg.get('output_dir', 'recordings')) / ts
            run_dir.mkdir(parents=True, exist_ok=True)
            print(f'[Recording] run folder → {run_dir}')

        recorder = Recorder(cfg, rec_fps, run_dir)

        print('Running on webcam — depth disabled (depth_m = -1) — press q to quit')
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    print('Webcam read failed.', file=sys.stderr)
                    break

                h, w = frame.shape[:2]

                results = model.predict(
                    frame,
                    conf=conf_thres, iou=iou_thres, imgsz=imgsz,
                    max_det=max_det, classes=classes,
                    augment=augment, device=device, verbose=False,
                )

                # point_cloud=None → depth_m will always be -1
                detections = build_detections(results[0], h, w, point_cloud=None, class_names=model.names)
                if detections:
                    print(detections)

                annotated = results[0].plot()
                recorder.write(frame, annotated)
                cv2.imshow('Webcam + YOLO  (press q to quit)', annotated)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

        finally:
            recorder.close()
            cap.release()
            cv2.destroyAllWindows()
            print('Done.')

    else:
        print(f'Unknown source "{source}". Set source to "zed" or "webcam" in config.', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()