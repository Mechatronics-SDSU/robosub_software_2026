import os
import time
import atexit
import datetime
import cv2
from enum import Enum

from fsm.fsm                                import FSM_Template
from modules.logger.logger                  import Logger
from modules.vision.vision_model_main       import camera, yolo, MirroredCamera
from modules.vision.target_box_helpers      import get_target_error_meters, body_offset_to_world_offset


"""
    Vision showcase/feature-test FSM. Continuously runs whichever camera
    you point it at (downfacing, webcam, or zed) through the YOLO model,
    prints and logs every qualifying detection's label/confidence/coordinates/
    box to a dedicated vision.log file (see modules/logger/logger.py's
    Logger(file=...)), and records footage to disk (MP4 always; SVO too when
    camera_source="zed") instead of showing a live window - meant to run
    unattended and be reviewed afterward, not watched live.

    Pure vision smoke test - no alignment/offset math, no dropper/grabber
    checking cycle, never writes target_x/y/z. Built to answer "is the vision
    model loading and detecting correctly, on which camera(s)" (e.g. the ZED
    2i on Caracara vs. the downward-facing camera), with a log + video trail
    you can review after the fact.
"""

class States(Enum):
    """
    Enumeration for FSM states
    """
    INIT    = "INIT"
    RUNNING = "RUNNING" # single continuous loop, stopped manually (Ctrl+C)

    def __str__(self) -> str: # make elegant string
        return self.value


class Vision_Test_FSM(FSM_Template):
    """
    Vision test FSM - opens the requested camera + model, logs every
    qualifying detection (label, confidence, normalized center/box, depth if
    available) to vision.log, and periodically logs a running summary.
    """
    def __init__(self, shared_memory_object, run_list: list, camera_source: str = "downfacing",
                 target_label: str = None, conf_min: float = 0.70,
                 imgsz: int = 640, camera_id: int = None, log_period_s: float = 10.0,
                 model_weights: str = "models/best.pt", target_depth: float = 1.0,
                 record_mp4: bool = True, record_svo: bool = False, output_dir: str = "vision_recordings",
                 headless: bool = True, zed_fallback: str = None):
        """
        Vision test FSM constructor

        camera_source: "downfacing" (sub's calibrated camera), "webcam"
        (laptop/dev, no undistortion), or "zed" (ZED/ZED X-series, incl. ZED 2i).
        target_label: vision class label to filter to, or None (default) to
        log every detected class above conf_min - useful for a broad "does
        the model see anything" showcase rather than one specific object.
        conf_min: minimum confidence to log/display a detection (default 0.70).
        imgsz: YOLO inference resolution (default 640) - lower (e.g. 320) on
        weak/RAM-limited compute like a Jetson Orin Nano 4GB.
        camera_id: only used when camera_source="zed" - selects among
        multiple/GMSL cameras. None (default) = auto.
        log_period_s: how often (seconds) to log a running summary (frame
        count, detection count, rolling fps) in addition to per-detection lines.
        model_weights: path to YOLO weights, resolved relative to modules/vision/.
        target_depth: assumed depth (meters) of the target plane, used the
        same way dropper/grabber/lineup use it - target_depth minus the
        pressure sensor's current depth gives the vertical distance the
        metric back-projection needs. Placeholder default (1.0) unless the
        real target's depth is known - same caveat as everywhere else this
        pattern is used.
        record_mp4: True (default) - records the annotated (boxed) video to
        <output_dir>/<timestamp>/video.mp4. No live window is shown - this
        tool runs unattended, review the recording/log afterward.
        record_svo: False (default) - additionally records native ZED SVO
        footage to <output_dir>/<timestamp>/recording.svo. Only applies when
        camera_source="zed" (ignored, with a warning, otherwise).
        output_dir: base directory recordings are written under (default
        "vision_recordings"), one timestamped subfolder per run.
        headless: True (default) - no live preview window, runs unattended
        (recording/logging happen either way, independent of this). Set False
        to also pop up a live window while it runs - useful when you want to
        watch it work, not just review the recording afterward.
        zed_fallback: only relevant when camera_source="zed". If opening the
        ZED fails (raises RuntimeError - see ZEDCamera in vision_model_main.py,
        which now fails cleanly with diagnostics instead of killing the
        process), None (default) re-raises and stops the FSM; pass another
        camera_source string (e.g. "downfacing") to automatically fall back
        to that camera instead. The fallback happens once - if the fallback
        camera also fails, that failure is not caught.
        """
        super().__init__(shared_memory_object, run_list)
        self.name: str      = "VISION_TEST"
        self.state: States  = States.INIT
        self.logger = Logger(file="vision") # -> vision.log, separate from default.log

        if camera_source not in ("downfacing", "webcam", "zed"):
            self.logger.error(f"{self.name} ERROR: invalid camera_source '{camera_source}', defaulting to 'downfacing'")
            camera_source = "downfacing"
        self.camera_source = camera_source
        self.target_label = target_label
        self.conf_min = conf_min
        self.imgsz = imgsz
        self.camera_id = camera_id
        self.log_period_s = log_period_s
        self.model_weights = model_weights
        self.target_depth = target_depth

        self.record_mp4 = record_mp4
        self.record_svo = record_svo
        if self.record_svo and self.camera_source != "zed":
            self.logger.warning(f"{self.name}: record_svo=True has no effect unless camera_source='zed', ignoring")
            self.record_svo = False
        self.output_dir = output_dir
        self.headless = headless
        self.zed_fallback = zed_fallback
        self._run_dir = None
        self._mp4_writer = None
        self._svo_enabled = False

        self._camera = None
        self._model = None

        # picked up by test_fsm_ctrl.py's display() - no self.helper here since
        # this FSM doesn't need dropper/grabber-style offset math, just raw detections
        self.debug = {}

        self.frame_count = 0
        self.detection_count = 0
        self.last_summary_time = 0.0
        self.t_loop = 0.05

        atexit.register(self._cleanup_recording) # release the writer/SVO on any exit (Ctrl+C included)

    def start(self) -> None:
        """
        Start FSM by enabling and starting processes
        """
        super().start()

        if self.record_mp4 or self.record_svo:
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            self._run_dir = os.path.join(self.output_dir, timestamp)
            os.makedirs(self._run_dir, exist_ok=True)

        self.logger.info(
            f"=== NEW SESSION: camera_source={self.camera_source} "
            f"target_label={self.target_label or 'ALL'} conf_min={self.conf_min} "
            f"imgsz={self.imgsz} camera_id={self.camera_id} headless={self.headless} "
            f"record_mp4={self.record_mp4} record_svo={self.record_svo} run_dir={self._run_dir} ==="
        )
        self.next_state(States.RUNNING)

    def _record_frame(self, frame, detections: dict):
        """
        Writes the annotated frame to the MP4 writer, creating it lazily on
        the first frame once the real frame size is known (same pattern
        DownfacingCamera uses for its undistortion maps).
        """
        if not self.record_mp4:
            return

        if self._mp4_writer is None:
            h, w = frame.shape[:2]
            path = os.path.join(self._run_dir, 'video.mp4')
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            self._mp4_writer = cv2.VideoWriter(path, fourcc, 20.0, (w, h))
            self.logger.info(f"{self.name}: MP4 recording -> {path} ({w}x{h})")

        self._mp4_writer.write(frame)

    def _open_camera(self):
        """
        Opens self.camera_source, with an optional one-shot fallback (see
        zed_fallback in the constructor). ZEDCamera now raises a RuntimeError
        on open failure (instead of killing the process with sys.exit -
        see vision_model_main.py) specifically so this can catch it here.
        """
        try:
            if self.camera_source == "zed":
                opened = camera("zed", camera_id=self.camera_id)
            else:
                opened = camera(self.camera_source)
        except RuntimeError as e:
            if self.camera_source == "zed" and self.zed_fallback:
                self.logger.error(f"{self.name}: ZED open failed ({e}), falling back to camera_source='{self.zed_fallback}'")
                self.camera_source = self.zed_fallback
                if self.record_svo:
                    self.logger.warning(f"{self.name}: record_svo=True has no effect on the fallback camera, disabling")
                    self.record_svo = False
                opened = camera(self.camera_source, camera_id=self.camera_id) if self.camera_source == "zed" else camera(self.camera_source)
            else:
                self.logger.error(f"{self.name}: camera open failed and no fallback configured, stopping: {e}")
                self.stop()
                raise

        # mirror for ease of manual bench alignment - webcam only, never the
        # real downfacing camera or a ZED
        return MirroredCamera(opened) if self.camera_source == "webcam" else opened

    def _cleanup_recording(self) -> None:
        """
        Releases the MP4 writer and disables SVO recording, called on any
        interpreter exit via atexit (covers Ctrl+C, not just a clean stop()).
        """
        if self._mp4_writer is not None:
            self._mp4_writer.release()
            self._mp4_writer = None
        if self._svo_enabled and self._camera is not None and hasattr(self._camera, 'disable_svo_recording'):
            self._camera.disable_svo_recording()
            self._svo_enabled = False

    def next_state(self, next: States) -> None:
        """
        Change to next state
        """
        if not self.active or self.state == next: return

        match(next):
            case States.INIT:
                return

            case States.RUNNING:
                self.last_summary_time = time.time()

            case _:
                self.logger.error(f"{self.name} INVALID NEXT STATE {next}")
                return

        old_state = self.state
        self.state = next
        self.logger.info(f"State changed: {old_state} -> {self.state}")

    def _draw_overlay(self, frame, detections: dict):
        """
        Draws a box + label/conf/depth text for every qualifying detection
        (matches target_label if set, else any class, all at/above conf_min).
        Unlike lineup_test_fsm.py this shows every qualifying detection, not
        just one - this tool is a broad "what does the model see" showcase.

        detections is the raw {'objN': [label, class_id, conf, x_norm, y_norm,
        width, height, depth_m], ...} dict straight from YOLOModel.infer().
        """
        h, w = frame.shape[:2]

        for label, class_id, conf, x_norm, y_norm, width, height, depth_m in detections.values():
            if conf < self.conf_min:
                continue
            if self.target_label is not None and label != self.target_label:
                continue

            x1 = int((x_norm - width / 2) * w)
            x2 = int((x_norm + width / 2) * w)
            y1 = int((1.0 - (y_norm + height / 2)) * h)
            y2 = int((1.0 - (y_norm - height / 2)) * h)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

            depth_txt = f' depth={depth_m:.2f}m' if depth_m is not None and depth_m > 0 else ''
            cv2.putText(frame, f'{label} {conf:.2f}{depth_txt}', (x1, max(0, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        cv2.putText(frame, f'frames={self.frame_count}  detections={self.detection_count}  cam={self.camera_source}',
                    (10, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        return frame

    def loop(self) -> None:
        """
        Loop function - grabs a frame, runs YOLO, logs every qualifying
        detection's coordinates/box to vision.log, never writes target_x/y/z.
        """
        if not self.active: return
        self.display(0, 200, 255)

        match(self.state):
            case States.INIT:
                return

            case States.RUNNING:
                if self._camera is None:
                    self._camera = self._open_camera()

                    if self.record_svo:
                        svo_path = os.path.join(self._run_dir, 'recording.svo')
                        self._svo_enabled = self._camera.enable_svo_recording(svo_path)

                if self._model is None:
                    self._model = yolo(self.model_weights, imgsz=self.imgsz)

                raw_detections = self._model.infer(self._camera, headless=self.headless, verbose=False,
                                                    overlay_fn=self._draw_overlay, overlay_only=True,
                                                    record_fn=self._record_frame if self.record_mp4 else None)
                self.frame_count += 1

                sub_depth = self.shared_memory_object.depth.value
                sub_x = self.shared_memory_object.dvl_x.value
                sub_y = self.shared_memory_object.dvl_y.value
                yaw_deg = self.shared_memory_object.dvl_yaw.value

                for det in raw_detections.values():
                    label, class_id, conf, x_norm, y_norm, width, height, depth_m = det
                    if conf < self.conf_min:
                        continue
                    if self.target_label is not None and label != self.target_label:
                        continue

                    self.detection_count += 1

                    # same metric back-projection dropper/grabber/lineup use: how far
                    # (meters, body frame) the target is from the camera, then rotated
                    # by current yaw and added to the sub's DVL position to get where
                    # the target actually is in world coordinates - i.e. how the sub
                    # gets there. vertical_distance = target_depth - sub_depth, so this
                    # is only meaningful once target_depth is a real measured value,
                    # not the 1.0m placeholder default - see constructor docstring.
                    x_error_m, y_error_m = get_target_error_meters(x_norm, y_norm, sub_depth, self.target_depth)
                    x_offset_world, y_offset_world = body_offset_to_world_offset(x_error_m, y_error_m, yaw_deg)
                    target_world_x = sub_x + x_offset_world
                    target_world_y = sub_y + y_offset_world

                    self.debug = {
                        "label": label, "conf": conf,
                        "x_norm": x_norm, "y_norm": y_norm,
                        "width": width, "height": height,
                        "depth_m": depth_m,
                        "body_offset_m": (x_error_m, y_error_m),
                        "target_world": (target_world_x, target_world_y),
                    }
                    self.logger.info(
                        f"[{self.camera_source}] {label} conf={conf:.2f} "
                        f"center=({x_norm:.3f}, {y_norm:.3f}) box=({width:.3f}x{height:.3f}) depth_m={depth_m:.2f}"
                    )
                    self.logger.info(
                        f"[{self.camera_source}] {label} meters: sub_depth={sub_depth:.3f}m target_depth={self.target_depth:.3f}m "
                        f"body_offset=({x_error_m:.3f}, {y_error_m:.3f})m yaw={yaw_deg:.1f}deg "
                        f"sub_world=({sub_x:.3f}, {sub_y:.3f}) -> target_world=({target_world_x:.3f}, {target_world_y:.3f})"
                    )

                if time.time() - self.last_summary_time >= self.log_period_s:
                    self.logger.info(
                        f"[{self.camera_source}] SUMMARY: {self.frame_count} frames, "
                        f"{self.detection_count} qualifying detections, fps={self._model.fps:.1f}"
                    )
                    self.last_summary_time = time.time()

                time.sleep(self.t_loop)

            case _:
                self.logger.error(f"{self.name} INVALID STATE {self.state}")
