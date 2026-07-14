import atexit
import datetime
import os
import time
import yaml
import cv2

from fsm.fsm                                import FSM_Template
from modules.logger.logger                  import Logger
from modules.dropper.dropper_helpers        import DropperHelpers
from modules.vision.vision_model_main       import camera, yolo, MirroredCamera
from modules.vision.target_box_helpers      import (
    CONF,
    convert_vision_runtime_detections,
    get_target_detection,
)
from enum                                   import Enum


"""
    Bench test FSM for the dropper — camera + dropper actuation only, no motors.
    Flow: SEARCH_FOR_BIN -> VERIFY_BIN_TARGET -> DROP_MARKER -> (repeat for 2nd marker) -> COMPLETE
    No shared_memory target writes, no navigation, no alignment.

    Settings in test_fsm_ctrl.py:
        DROPPER_TEST_CAMERA_SOURCE  "downfacing" | "webcam" | "zed"
        DROPPER_TEST_TARGET_LABEL   None (use role default) or e.g. "fire" / "blood"
        DROPPER_TEST_SHOW_VIDEO     True = live preview window (requires X display)
        DROPPER_TEST_RECORD_VIDEO   True = save annotated MP4 to dropper_test_recordings/
        DROPPER_TEST_CONF_MIN       minimum detection confidence (0.0–1.0)
        DROPPER_TEST_IMGSZ          YOLO inference resolution
"""

class States(Enum):
    INIT              = "INIT"
    SEARCH_FOR_BIN    = "SEARCH_FOR_BIN"
    VERIFY_BIN_TARGET = "VERIFY_BIN_TARGET"
    DROP_MARKER       = "DROP_MARKER"
    COMPLETE          = "COMPLETE"
    FAIL              = "FAIL"

    def __str__(self) -> str:
        return self.value


class DropperTest_FSM(FSM_Template):
    """
    Dropper bench test FSM.
    Points the chosen camera at a bin, waits for a stable detection, fires the
    dropper, then looks for the second bin. No motor commands are sent.

    signal_wrapper : real SignalWrapper to actuate hardware, or None for print
                     placeholders (same as the real Dropper_FSM).
    camera_source  : "downfacing" | "webcam" | "zed"
    target_label   : vision class to look for. None = use role default from
                     objects.yaml ("fire" for survey_and_repair, "blood" for
                     search_and_rescue). Pass e.g. "fire" to override.
    show_video     : True = live preview window (requires an X display).
    record_video   : True = save annotated MP4 to dropper_test_recordings/.
    conf_min       : minimum confidence threshold.
    imgsz          : YOLO inference resolution.
    """
    def __init__(self, shared_memory_object, run_list: list, signal_wrapper=None,
                 camera_source: str = "downfacing", target_label: str | None = None,
                 show_video: bool = False, record_video: bool = True,
                 conf_min: float = 0.50, imgsz: int = 640):
        super().__init__(shared_memory_object, run_list)
        self.name: str     = "DROPPER_TEST"
        self.state: States = States.INIT
        self.logger = Logger()

        self.timeout      = 8.0
        self.t_loop       = 0.10
        self.show_video   = show_video
        self.record_video = record_video
        self.conf_min     = conf_min

        self.marker_num     = 1
        self.max_markers    = 2
        self.current_target = None
        self.wait_time      = 0.0

        role          = "survey_and_repair"
        model_weights = "models/best.pt"

        hw_path = os.path.expanduser("~/robosub_software_2026/config/hardware.yaml")
        try:
            with open(hw_path) as f:
                hw = yaml.safe_load(f)
                d = hw.get('dropper', {})
                model_weights = d.get('model_weights', model_weights)
        except FileNotFoundError:
            self.logger.error(f"{self.name} ERROR: config/hardware.yaml not found, using defaults")
        except KeyError:
            self.logger.error(f"{self.name} ERROR: Invalid format in config/hardware.yaml, using defaults")

        try:
            with open(os.path.expanduser("~/robosub_software_2026/objects.yaml"), 'r') as file:
                data = yaml.safe_load(file)
                course = data['course']
                role = data.get('role', role)
                self.timeout = data[course]['dropper'].get('timeout', self.timeout)
                self.t_loop  = data[course]['dropper'].get('t_loop',   self.t_loop)
        except FileNotFoundError:
            self.logger.error(f"{self.name} ERROR: objects.yaml not found, using defaults")
        except KeyError:
            self.logger.error(f"{self.name} ERROR: Invalid data format in objects.yaml, using defaults")

        # helper is used for tracking/actuation only — this FSM manages its own
        # camera and model so it can control video output independently
        self.helper    = DropperHelpers(shared_memory_object, signal_wrapper, weights_path=model_weights)
        role_bin_label = self.helper.get_bin_label(role)
        self.bin_label = target_label if target_label is not None else role_bin_label

        self.camera_source = camera_source
        self.model_weights = model_weights
        self.imgsz         = imgsz
        self._camera       = None
        self._model        = None

        self._mp4_writer = None
        self._run_dir    = None

        atexit.register(self._cleanup_recording)

    def _cleanup_recording(self) -> None:
        if self._mp4_writer is not None:
            self._mp4_writer.release()
            self._mp4_writer = None

    def _record_frame(self, frame, _detections):
        if not self.record_video:
            return
        if self._mp4_writer is None:
            h, w = frame.shape[:2]
            path = os.path.join(self._run_dir, 'dropper_test.mp4')
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            self._mp4_writer = cv2.VideoWriter(path, fourcc, 20.0, (w, h))
            self.logger.info(f"{self.name}: recording -> {path}  ({w}x{h})")
        self._mp4_writer.write(frame)

    def _open_camera_and_model(self) -> None:
        if self._camera is None:
            opened = camera(self.camera_source)
            # mirror for easier manual bench alignment — only safe on webcam,
            # never flip the real downfacing/ZED camera (corrupts geometry)
            self._camera = MirroredCamera(opened) if self.camera_source == "webcam" else opened
        if self._model is None:
            self._model = yolo(self.model_weights, conf=self.conf_min, imgsz=self.imgsz)

    def _draw_overlay(self, frame, raw_detections: dict):
        h, w = frame.shape[:2]

        for label, class_id, conf, x_norm, y_norm, width, height, depth_m in raw_detections.values():
            if label != self.bin_label or conf < self.conf_min:
                continue

            x1 = int((x_norm - width / 2) * w)
            x2 = int((x_norm + width / 2) * w)
            y1 = int((1.0 - (y_norm + height / 2)) * h)
            y2 = int((1.0 - (y_norm - height / 2)) * h)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, f'{label} {conf:.2f}', (x1, max(0, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)

            center_px = (int(x_norm * w), int((1.0 - y_norm) * h))
            cv2.drawMarker(frame, center_px, (0, 255, 0),
                           markerType=cv2.MARKER_CROSS, markerSize=24, thickness=2)
            break

        cv2.putText(frame,
                    f'state={self.state}  marker={self.marker_num}/{self.max_markers}  target={self.bin_label}',
                    (10, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        return frame

    def _get_target(self):
        """Grabs one frame, runs inference (with overlay), returns flat-list detection or None."""
        self._open_camera_and_model()
        raw = self._model.infer(
            self._camera,
            headless=not self.show_video,
            overlay_fn=self._draw_overlay,
            overlay_only=True,
            record_fn=self._record_frame if self.record_video else None,
        )
        detections = convert_vision_runtime_detections(raw)
        target = get_target_detection(detections, self.bin_label)
        if target is None or target[CONF] < self.conf_min:
            return None
        return target

    def start(self) -> None:
        super().start()

        if self.record_video:
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            self._run_dir = os.path.join(
                os.path.expanduser("~/robosub_software_2026/dropper_test_recordings"), timestamp
            )
            os.makedirs(self._run_dir, exist_ok=True)

        self.logger.info(
            f"=== DROPPER TEST: camera={self.camera_source} target={self.bin_label} "
            f"conf_min={self.conf_min} show_video={self.show_video} "
            f"record_video={self.record_video} run_dir={self._run_dir} ==="
        )
        self.next_state(States.SEARCH_FOR_BIN)

    def next_state(self, next: States) -> None:
        if not self.active or self.state == next: return

        match(next):
            case States.INIT:
                return

            case States.SEARCH_FOR_BIN:
                self.helper.reset_tracking()
                self.wait_time = time.time()

            case States.VERIFY_BIN_TARGET:
                self.wait_time = time.time()

            case States.DROP_MARKER:
                self.helper.release_marker()

            case States.COMPLETE:
                self.suspend()

            case States.FAIL:
                self.logger.warning(f"{self.name} FAILED on marker {self.marker_num}, restarting search")
                self.marker_num = 1

            case _:
                self.logger.error(f"{self.name} INVALID NEXT STATE {next}")
                return

        old_state = self.state
        self.state = next
        self.logger.info(f"State changed: {old_state} -> {self.state}")

    def loop(self) -> None:
        if not self.active: return
        self.display(255, 100, 0)

        match(self.state):
            case States.INIT:
                return

            case States.SEARCH_FOR_BIN:
                target = self._get_target()
                if target is not None:
                    self.current_target = target
                    self.helper.record_detection(target)
                    self.next_state(States.VERIFY_BIN_TARGET)
                elif time.time() - self.wait_time > self.timeout:
                    self.next_state(States.FAIL)
                time.sleep(self.t_loop)

            case States.VERIFY_BIN_TARGET:
                target = self._get_target()
                if target is not None:
                    self.current_target = target
                    if self.helper.check_target_stable(target):
                        self.next_state(States.DROP_MARKER)
                elif time.time() - self.wait_time > self.timeout:
                    self.next_state(States.FAIL)
                time.sleep(self.t_loop)

            case States.DROP_MARKER:
                if self.marker_num < self.max_markers:
                    self.marker_num += 1
                    self.next_state(States.SEARCH_FOR_BIN)
                else:
                    self.next_state(States.COMPLETE)

            case States.COMPLETE:
                return

            case States.FAIL:
                self.next_state(States.SEARCH_FOR_BIN)

            case _:
                self.logger.error(f"{self.name} INVALID STATE {self.state}")
