"""Vision Summer 2026 — live ZED + YOLO inference entry point.

Reads config.yaml, opens the ZED camera, and runs YOLO every frame.
Per-frame detections are returned as a dict:

    {
        'obj1': ['ambulance', 2, 0.74, 0.20, 0.85, 5.0],
        'obj2': ['fire',      1, 0.97, 0.30, 0.60, 11.2],
    }

Fields: [class_label, class_id, conf, x_norm, y_norm, depth_m]
  x_norm  : 0 = far-left,  1 = far-right
  y_norm  : 0 = bottom,    1 = top
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


def _auto_device() -> str:
    try:
        import torch
        if torch.cuda.is_available():
            return '0'
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

def build_detections(r, frame_h: int, frame_w: int, point_cloud=None) -> dict:
    """Convert a YOLO result into the standard detection dict.

    point_cloud : sl.Mat when running with ZED, None when running with webcam.
                  When None, depth_m is always -1.

    Returns
    -------
    dict  e.g. {'obj1': ['ambulance', 2, 0.74, 0.20, 0.85, 5.0], ...}
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

        # Depth: Z component of the point-cloud at box centre (ZED only)
        depth = -1.0
        if point_cloud is not None:
            _, pc_val = point_cloud.get_value(cx, cy)
            z = float(pc_val[2])
            if np.isfinite(z) and z > 0:
                depth = round(z, 2)

        label = CLASS_NAMES.get(cls_id, str(cls_id))
        detections[f'obj{idx}'] = [label, cls_id, conf, x_norm, y_norm, depth]

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
            recording.svo                       ← svo: true (ZED only, via _start_svo)
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
        'H264':     sl.SVO_COMPRESSION_TYPE.H264,
        'H265':     sl.SVO_COMPRESSION_TYPE.H265,
        'LOSSLESS': sl.SVO_COMPRESSION_TYPE.LOSSLESS,
    }
    rec_cfg  = cfg.get('recording', {})
    comp_key = str(rec_cfg.get('svo_compression', 'H264')).upper()

    rec_params                  = sl.RecordingParameters()
    rec_params.video_filename   = str(run_dir / 'recording.svo')
    rec_params.compression_mode = _COMPRESSION_MAP.get(comp_key, sl.SVO_COMPRESSION_TYPE.H264)

    err = zed.enable_recording(rec_params)
    if err != sl.ERROR_CODE.SUCCESS:
        print(f'[SVO] enable_recording failed: {err}', file=sys.stderr)
        sys.exit(1)

    print(f'[SVO] recording → {rec_params.video_filename}  compression={comp_key}')


## Main

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else '')
    parser.add_argument(
        '--config', default='config.yaml',
        help='path to YAML config (default: config.yaml)',
    )
    args = parser.parse_args()

    cfg = load_config(args.config)

    ## MODEL
    model_cfg = cfg.get('model', {})
    weights   = model_cfg.get('weights', 'runs_cnn_transfer/v1.1/weights/best.pt')
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

                detections = build_detections(results[0], h, w, point_cloud)
                if detections:
                    print(detections)

                annotated = results[0].plot()
                recorder.write(frame, annotated)
                cv2.imshow('ZED + YOLO  (press q to quit)', annotated)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

        finally:
            if svo_active:
                zed.disable_recording()
                print('[SVO] recording stopped')
            recorder.close()
            zed.close()
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
                detections = build_detections(results[0], h, w, point_cloud=None)
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
