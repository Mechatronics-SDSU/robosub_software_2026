import os
import time
import yaml
import random
import cv2

from fsm.fsm                                import FSM_Template
from modules.logger.logger                  import Logger
from modules.dropper.dropper_helpers        import DropperHelpers
from modules.grabber.grabber_helpers        import GrabberHelpers
from modules.vision.vision_model_main       import camera, yolo
from modules.vision.target_box_helpers      import (
    CONF,
    X_NORM,
    Y_NORM,
    MIN_CONFIDENCE,
    FINAL_SETTLE_TIME_S,
    get_target_detection,
    is_stable_target,
    average_target_center,
    back_project_to_body_frame,
    get_target_error_meters,
    is_target_centered_metric,
    has_required_center_time,
    body_offset_to_image_norm,
    convert_vision_runtime_detections,
)
from enum                                   import Enum


"""
    Bench-diagnostic FSM for the vision + reliability-checking logic, using
    the same building blocks dropper/grabber use (IoU-based multi-frame
    stability, dwell-time gating, stricter final-verify pass) but without
    ever touching target_x/y/z - it never drives the sub.

    Instead of aligning to a fixed real-world bin/item, this cycles through a
    SEARCH -> VERIFY_TARGET -> ALIGN -> VERIFY_FINAL -> SUCCESS state machine
    (mirroring fsm/dropper_fsm.py's shape) against a "goal" point placed at a
    random normalized image position each cycle. Once a cycle passes the full
    checking pipeline, a new random goal is picked and the cycle repeats -
    move the camera/target so the detected box center reaches the goal
    reticle to complete a cycle, over and over, to exercise the checking
    logic repeatedly without needing the real sub.

    Intended use: sub floating (or lifted out of water onto a stand), or a
    laptop webcam on the bench (camera_source="webcam"). Validates the
    checking LOGIC (confidence/stability/dwell/verify gating) - it does NOT
    validate real DVL world-position integration, yaw rotation, or PID
    response, since none of those are driven by anything on a bare laptop.
"""

class States(Enum):
    """
    Enumeration for FSM states
    """
    INIT          = "INIT"
    SEARCH        = "SEARCH"
    VERIFY_TARGET = "VERIFY_TARGET"
    ALIGN         = "ALIGN"
    VERIFY_FINAL  = "VERIFY_FINAL"
    SUCCESS       = "SUCCESS" # transient - picks a new random goal, then back to SEARCH

    def __str__(self) -> str: # make elegant string
        return self.value


# how close to the frame edges a random goal point is allowed to land -
# keeps goals reachable/visible instead of picking something right at the border
GOAL_MARGIN = 0.25


class _MirroredCamera:
    """
    Thin wrapper that horizontally mirrors every grabbed frame - a pure
    ease-of-use convenience for manual webcam bench testing (moving the
    camera left then visibly moves things left on screen, like a selfie
    camera), applied before detection so boxes/markers stay self-consistent
    with what's drawn. Only ever wraps a "webcam" camera (see loop()) - never
    applied to camera_source="downfacing", since flipping would corrupt the
    real calibrated geometry the sub's alignment math depends on.
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


class Lineup_Test_FSM(FSM_Template):
    """
    Lineup test FSM - picks which tool offset/config to test with (dropper or
    grabber's claw), reuses the same stability/verify/dwell checking helpers,
    and cycles through random goal points to repeatedly exercise that
    checking logic without ever driving the sub.
    """
    def __init__(self, shared_memory_object, run_list: list, system: str = "dropper", target_label: str = "fire",
                 camera_source: str = "downfacing", conf_min: float = MIN_CONFIDENCE, show_video: bool = True,
                 imgsz: int = 640, camera_id: int | None = None):
        """
        Lineup test FSM constructor

        system: "dropper" or "grabber" - which tool offset/config to test with.
        target_label: vision class label to search for (default "fire", one of
        the few classes actually trained today - set to whatever image you're
        holding under the camera).
        camera_source: "downfacing" (the sub's calibrated camera), "webcam" (a
        plain laptop/dev webcam, no undistortion), or "zed" (ZED/ZED X-series
        stereo camera, incl. ZED X Mini over GMSL2 - NOT verified against real
        ZED X Mini hardware yet, see ZEDCamera's docstring in vision_model_main.py)
        - independent of system, so you can test either offset's math against
        any camera.
        conf_min: minimum detection confidence to produce any output at all
        (default MIN_CONFIDENCE, 0.70) - ticks below this are silently skipped.
        show_video: True (default) shows a live preview window with the target
        box + goal reticle + fps overlay (press q to close the window, doesn't
        stop the FSM) - see YOLOModel.infer()'s headless param in vision_model_main.py.
        imgsz: YOLO inference resolution (default 640) - lower this (e.g. 320)
        on weak/RAM-limited compute like a Jetson Orin Nano 4GB.
        camera_id: only used when camera_source="zed" - selects among multiple/
        GMSL cameras, see ZEDCamera's camera_id param. None (default) = auto.
        """
        super().__init__(shared_memory_object, run_list)
        self.name: str      = "LINEUP_TEST"
        self.state: States  = States.INIT
        self.logger = Logger()

        if system not in ("dropper", "grabber"):
            self.logger.error(f"{self.name} ERROR: invalid system '{system}', defaulting to 'dropper'")
            system = "dropper"
        self.system = system
        self.target_label = target_label
        self.show_video = show_video
        self.conf_min = conf_min
        self.imgsz = imgsz
        self.camera_id = camera_id

        if camera_source not in ("downfacing", "webcam", "zed"):
            self.logger.error(f"{self.name} ERROR: invalid camera_source '{camera_source}', defaulting to 'downfacing'")
            camera_source = "downfacing"
        self.camera_source = camera_source
        # opened lazily on first use, same pattern as DropperHelpers/GrabberHelpers,
        # independent of self.helper's own camera wiring - this tool always manages
        # its own camera so camera_source can differ from what dropper/grabber use
        self._camera = None
        self._model = None

        self.t_loop = 0.10
        self.desired_height = 0.3
        self.target_depth = 1.0
        self.x_lineup_tolerance = 0.05
        self.y_lineup_tolerance = 0.05
        model_weights = "models/best.pt"
        offset_x = offset_y = 0.0

        try:
            with open(os.path.expanduser("~/robosub_software_2026/objects.yaml"), 'r') as file:
                data = yaml.safe_load(file)
                course = data['course']
                section = data[course][system] # "dropper" or "grabber" section

                self.desired_height = section.get('desired_height', self.desired_height)
                self.x_lineup_tolerance = section.get('x_lineup_tolerance', self.x_lineup_tolerance)
                self.y_lineup_tolerance = section.get('y_lineup_tolerance', self.y_lineup_tolerance)
                model_weights = section.get('model_weights', model_weights)

                if system == "dropper":
                    self.target_depth = section.get('target_depth', self.target_depth)
                    offset_x = section.get('dropper_offset_x', offset_x)
                    offset_y = section.get('dropper_offset_y', offset_y)
                else: # grabber
                    self.target_depth = section.get('item_target_depth', self.target_depth)
                    offset_x = section.get('claw_offset_x', offset_x)
                    offset_y = section.get('claw_offset_y', offset_y)

        except FileNotFoundError:
            self.logger.error(f"{self.name} ERROR: objects.yaml not found, using default lineup values")
        except KeyError:
            self.logger.error(f"{self.name} ERROR: Invalid data format in objects.yaml, using default lineup values")

        self.model_weights = model_weights # used to open self._model directly, see loop()

        # signal_wrapper always None - this tool never actuates a dropper/claw,
        # it never calls release_marker()/grab_object()/etc. weights_path passed
        # here too, but self.helper's own camera/model are never used by this
        # FSM (see loop()) - only its tracking/stability methods.
        if system == "dropper":
            self.helper = DropperHelpers(shared_memory_object, signal_wrapper=None, weights_path=model_weights,
                                          dropper_offset_body=(offset_x, offset_y))
        else:
            self.helper = GrabberHelpers(shared_memory_object, signal_wrapper=None, weights_path=model_weights,
                                          claw_offset_body=(offset_x, offset_y))

        # cycle state: the current random goal point, and dwell/verify timers
        # kept locally (not on self.helper) since this FSM drives its own
        # SEARCH/VERIFY_TARGET/ALIGN/VERIFY_FINAL cycle instead of calling
        # helper.align_step()
        self.goal_norm = None
        self.centered_since = None
        self.verify_entered_time = 0.0
        self.cycles_completed = 0
        self._pick_new_goal()

    def _pick_new_goal(self) -> None:
        """
        Picks a new random (x_norm, y_norm) goal point within GOAL_MARGIN of
        the frame edges - "the point that counts as center" for this cycle's
        checking logic. Called on init and every time a cycle completes.
        """
        self.goal_norm = (
            random.uniform(GOAL_MARGIN, 1.0 - GOAL_MARGIN),
            random.uniform(GOAL_MARGIN, 1.0 - GOAL_MARGIN),
        )
        self.logger.info(f"{self.name}: new goal point picked: {self.goal_norm}")

    def _goal_and_target_metric_error(self, target) -> tuple:
        """
        Converts the current goal point and a detection into the same metric
        camera-frame space (via the exact back-projection math dropper/grabber
        use) and returns (remaining_x_error, remaining_y_error) - how far the
        detected target still is from the goal point, in meters.
        """
        sub_depth = self.shared_memory_object.depth.value
        vertical_distance = self.target_depth - sub_depth

        goal_x_m, goal_y_m = back_project_to_body_frame(self.goal_norm[0], self.goal_norm[1], vertical_distance)
        target_x_m, target_y_m = get_target_error_meters(target[X_NORM], target[Y_NORM], sub_depth, self.target_depth)

        return target_x_m - goal_x_m, target_y_m - goal_y_m

    def start(self) -> None:
        """
        Start FSM by enabling and starting processes
        """
        super().start()
        self.next_state(States.SEARCH)

    def _draw_overlay(self, frame, detections: dict):
        """
        Draws on the plain (undrawn) camera frame - YOLO's own all-class box
        plot is skipped (see overlay_only=True in loop()) so anything that
        isn't the target label at/above conf_min is fully disregarded, not
        just left uncommented: the real tool offset (dropper/claw) reference
        marker, this cycle's random GOAL reticle (the point actually being
        checked against), the matching target's own box + center marker, and
        a line from the goal to it. Move the camera so the target marker
        slides onto the GOAL reticle to complete this cycle.

        detections is the raw {'objN': [label, class_id, conf, x_norm, y_norm,
        width, height, depth_m], ...} dict straight from YOLOModel.infer(),
        not the flat-list format converted elsewhere in this file.
        """
        h, w = frame.shape[:2]

        # real tool offset, drawn as a dim reference point only - not what this
        # cycle's pass/fail logic checks against, see the GOAL marker for that
        offset_body = self.helper.dropper_offset_body if self.system == "dropper" else self.helper.claw_offset_body
        sub_depth = self.shared_memory_object.depth.value
        vertical_distance = self.target_depth - sub_depth
        tool_x_norm, tool_y_norm = body_offset_to_image_norm(offset_body[0], offset_body[1], vertical_distance)
        tool_px = (int(tool_x_norm * w), int((1.0 - tool_y_norm) * h))
        cv2.drawMarker(frame, tool_px, (180, 90, 0), markerType=cv2.MARKER_CROSS, markerSize=16, thickness=1)
        cv2.putText(frame, "tool offset", (tool_px[0] + 10, tool_px[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 90, 0), 1)

        # this cycle's goal reticle - what the checking logic actually targets
        goal_px = (int(self.goal_norm[0] * w), int((1.0 - self.goal_norm[1]) * h))
        cv2.drawMarker(frame, goal_px, (255, 0, 255), markerType=cv2.MARKER_CROSS, markerSize=28, thickness=2)
        cv2.putText(frame, "GOAL", (goal_px[0] + 12, goal_px[1] - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)

        for label, class_id, conf, x_norm, y_norm, width, height, depth_m in detections.values():
            if label != self.target_label or conf < self.conf_min:
                continue # not the target class, or below conf_min - disregarded entirely, not drawn

            x1 = int((x_norm - width / 2) * w)
            x2 = int((x_norm + width / 2) * w)
            y1 = int((1.0 - (y_norm + height / 2)) * h)
            y2 = int((1.0 - (y_norm - height / 2)) * h)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, f'{label} {conf:.2f}', (x1, max(0, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

            target_px = (int(x_norm * w), int((1.0 - y_norm) * h))
            cv2.drawMarker(frame, target_px, (0, 255, 0), markerType=cv2.MARKER_TILTED_CROSS, markerSize=24, thickness=2)
            cv2.line(frame, goal_px, target_px, (0, 255, 255), 2)
            break # only line up the first matching detection, same as get_target_detection()

        cv2.putText(frame, f'state={self.state}  cycles={self.cycles_completed}', (10, h - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        return frame

    def next_state(self, next: States) -> None:
        """
        Change to next state
        """
        if not self.active or self.state == next: return

        match(next):
            case States.INIT:
                return

            case States.SEARCH:
                self.helper.reset_tracking()
                self.centered_since = None

            case States.VERIFY_TARGET:
                pass

            case States.ALIGN:
                self.centered_since = None

            case States.VERIFY_FINAL:
                self.verify_entered_time = time.time()

            case States.SUCCESS:
                self.cycles_completed += 1
                self.logger.info(f"{self.name}: cycle {self.cycles_completed} complete (goal {self.goal_norm}) - picking a new goal")
                self._pick_new_goal()

            case _:
                self.logger.error(f"{self.name} INVALID NEXT STATE {next}")
                return

        old_state = self.state
        self.state = next
        self.logger.info(f"State changed: {old_state} -> {self.state}")

    def _get_target(self):
        """
        Grabs one frame, runs inference (with the overlay drawn if
        show_video), and returns the flat-list target detection matching
        target_label at/above conf_min, or None.
        """
        if self._camera is None:
            if self.camera_source == "zed":
                opened = camera("zed", camera_id=self.camera_id) # camera_id=None is ZEDCamera's own default (auto)
            else:
                opened = camera(self.camera_source)
            # mirror for ease of manual alignment on the bench - webcam only,
            # never the real downfacing camera or a ZED (see _MirroredCamera docstring)
            self._camera = _MirroredCamera(opened) if self.camera_source == "webcam" else opened
        if self._model is None:
            self._model = yolo(self.model_weights, imgsz=self.imgsz)

        raw_detections = self._model.infer(self._camera, headless=not self.show_video, verbose=False,
                                            overlay_fn=self._draw_overlay, overlay_only=True)
        detections = convert_vision_runtime_detections(raw_detections)
        target = get_target_detection(detections, self.target_label)

        if target is None or target[CONF] < self.conf_min:
            return None
        return target

    def loop(self) -> None:
        """
        Loop function - runs the SEARCH -> VERIFY_TARGET -> ALIGN ->
        VERIFY_FINAL -> SUCCESS cycle against the current random goal point,
        never writing target_x/y/z.
        """
        if not self.active: return
        self.display(0, 200, 200)

        match(self.state):
            case States.INIT:
                return

            case States.SEARCH:
                target = self._get_target()
                if target is not None:
                    self.helper.record_detection(target)
                    self.next_state(States.VERIFY_TARGET)
                time.sleep(self.t_loop)

            case States.VERIFY_TARGET:
                target = self._get_target()
                if target is not None:
                    if self.helper.check_target_stable(target):
                        self.next_state(States.ALIGN)
                elif self.helper.is_target_lost():
                    self.next_state(States.SEARCH)
                time.sleep(self.t_loop)

            case States.ALIGN:
                target = self._get_target()
                if target is None:
                    if self.helper.is_target_lost():
                        self.next_state(States.SEARCH)
                    time.sleep(self.t_loop)
                    return

                self.helper.record_detection(target)
                x_error_m, y_error_m = self._goal_and_target_metric_error(target)
                centered = is_target_centered_metric(x_error_m, y_error_m, self.x_lineup_tolerance, self.y_lineup_tolerance)

                if centered:
                    if self.centered_since is None:
                        self.centered_since = time.time()
                else:
                    self.centered_since = None

                self.helper.debug.update({
                    "x_error": x_error_m, "y_error": y_error_m,
                    "stable": True, "centered": centered,
                    "dwell_ok": has_required_center_time(self.centered_since),
                    "move_x": x_error_m, "move_y": y_error_m,
                })

                if centered and has_required_center_time(self.centered_since):
                    self.next_state(States.VERIFY_FINAL)
                time.sleep(self.t_loop)

            case States.VERIFY_FINAL:
                target = self._get_target()
                if target is None:
                    if self.helper.is_target_lost():
                        self.next_state(States.SEARCH)
                    time.sleep(self.t_loop)
                    return

                self.helper.record_detection(target)
                x_error_m, y_error_m = self._goal_and_target_metric_error(target)
                centered = is_target_centered_metric(x_error_m, y_error_m, self.x_lineup_tolerance, self.y_lineup_tolerance)

                if not centered:
                    # drifted back out of tolerance during the final settle/verify hold - re-align
                    self.next_state(States.ALIGN)
                    time.sleep(self.t_loop)
                    return

                settled = time.time() - self.verify_entered_time >= FINAL_SETTLE_TIME_S
                verified = self.helper.check_target_verified(target)

                self.helper.debug.update({
                    "x_error": x_error_m, "y_error": y_error_m,
                    "stable": verified, "centered": centered, "dwell_ok": True,
                    "move_x": x_error_m, "move_y": y_error_m,
                })

                if settled and verified:
                    self.next_state(States.SUCCESS)
                time.sleep(self.t_loop)

            case States.SUCCESS:
                self.next_state(States.SEARCH)

            case _:
                self.logger.error(f"{self.name} INVALID STATE {self.state}")
