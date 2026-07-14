import os
import time
import yaml

from fsm.fsm                                import FSM_Template
from modules.logger.logger                  import Logger
from modules.torpedo.torpedo_helpers        import TorpedoHelpers, DISTANCE_MODES, DEFAULT_DISTANCE_MODE
from modules.vision.target_box_helpers      import FINAL_SETTLE_TIME_S
from enum                                   import Enum


"""
    FSM for Task 4 — Deploy Torpedoes.

    Always runs in search_and_rescue mode: detects the blood board image and
    associates the spatially-closest large or small hole to it, then aligns the
    torpedo tube (not just the camera) using the forward-facing ZED stereo camera
    and fires. Torpedo 1 → large hole, torpedo 2 → small hole (competition's
    max-points sequence).

    Mission waypoints and tolerances are read from objects.yaml under
    data[course]['torpedo']. Hardware settings (camera, model weights, tube offset)
    are read from config/hardware.yaml.
"""


class States(Enum):
    INIT                 = "INIT"
    MOVE_TO_BOARD        = "MOVE_TO_BOARD"
    SEARCH_FOR_HOLE      = "SEARCH_FOR_HOLE"
    VERIFY_HOLE          = "VERIFY_HOLE"
    ALIGN_TO_HOLE        = "ALIGN_TO_HOLE"
    VERIFY_FIRE_POSITION = "VERIFY_FIRE_POSITION"
    FIRE_TORPEDO         = "FIRE_TORPEDO"
    COMPLETE             = "COMPLETE"
    FAIL                 = "FAIL"

    def __str__(self) -> str:
        return self.value


class Torpedo_FSM(FSM_Template):
    """
    FSM for the Deploy Torpedoes task (Task 4).

    Uses a forward-facing ZED stereo camera (not the downfacing camera).
    Aligns the torpedo tube's exit point (not the camera center) on the target
    hole using ZED depth + FOV-based metric error computation.

    States reuse one set of SEARCH/VERIFY/ALIGN/VERIFY_FIRE states for both
    torpedoes, switching the target hole label (large → small) after FIRE_TORPEDO,
    the same counter pattern as Dropper_FSM's marker_num loop.
    """
    def __init__(self, shared_memory_object, run_list: list, signal_wrapper=None):
        super().__init__(shared_memory_object, run_list)
        self.name: str     = "TORPEDO"
        self.state: States = States.INIT
        self.logger = Logger()

        # TARGET VALUES
        self.x1 = self.y1 = self.depth = 0.0
        self.x_buffer = self.y_buffer = self.z_buffer = 0.10
        self.timeout  = 8.0
        self.t_loop   = 0.10

        # TORPEDO COUNT
        self.torpedo_num  = 1  # which torpedo we are currently lining up (1 or 2)
        self.max_torpedoes = 2
        self.current_target = None

        # VISION / LINEUP VALUES
        self.x_lineup_tolerance = 0.05  # meters, metric error allowed when "centered"
        self.y_lineup_tolerance = 0.05  # meters
        self.distance_mode = DEFAULT_DISTANCE_MODE  # standoff distance mode from YAML

        self.final_settle_time  = FINAL_SETTLE_TIME_S
        self.verify_entered_time = 0.0
        self.wait_time = 0.0

        # hardware defaults (overridden from hardware.yaml)
        camera_source  = "zed"
        camera_id      = 0
        fov_x_deg      = 90.0
        fov_y_deg      = 60.0
        model_weights  = "models/best.pt"
        tube_offset_x  = 0.0
        tube_offset_y  = 0.0

        # load hardware config
        hw_path = os.path.expanduser("~/robosub_software_2026/config/hardware.yaml")
        try:
            with open(hw_path) as f:
                hw = yaml.safe_load(f)
                cam = hw.get('camera', {})
                camera_source = cam.get('source', camera_source)
                camera_id     = cam.get('camera_id', camera_id)
                fov_x_deg     = cam.get('fov_x_deg', fov_x_deg)
                fov_y_deg     = cam.get('fov_y_deg', fov_y_deg)
                torp = hw.get('torpedo', {})
                model_weights = torp.get('model_weights', model_weights)
                tube_offset_x = torp.get('tube_offset_x', tube_offset_x)
                tube_offset_y = torp.get('tube_offset_y', tube_offset_y)
        except FileNotFoundError:
            self.logger.error(f"{self.name} ERROR: config/hardware.yaml not found, using defaults")
        except KeyError:
            self.logger.error(f"{self.name} ERROR: Invalid format in config/hardware.yaml, using defaults")

        # load mission config
        try:
            with open(os.path.expanduser("~/robosub_software_2026/objects.yaml"), 'r') as file:
                data = yaml.safe_load(file)
                course = data['course']

                t = data[course]['torpedo']
                self.x_buffer = t.get('x_buf', self.x_buffer)
                self.y_buffer = t.get('y_buf', self.y_buffer)
                self.z_buffer = t.get('z_buf', self.z_buffer)
                self.x1    = t.get('x1',      self.x1)
                self.y1    = t.get('y1',      self.y1)
                self.depth = t.get('z',       self.depth)

                self.timeout              = t.get('timeout',           self.timeout)
                self.t_loop               = t.get('t_loop',            self.t_loop)
                self.x_lineup_tolerance   = t.get('x_lineup_tolerance', self.x_lineup_tolerance)
                self.y_lineup_tolerance   = t.get('y_lineup_tolerance', self.y_lineup_tolerance)
                self.distance_mode        = t.get('distance_mode',     self.distance_mode)
                self.final_settle_time    = t.get('final_settle_time', self.final_settle_time)

        except FileNotFoundError:
            self.logger.error(f"{self.name} ERROR: objects.yaml not found, using default torpedo values")
        except KeyError:
            self.logger.error(f"{self.name} ERROR: Invalid data format in objects.yaml, using default torpedo values")

        self.helper = TorpedoHelpers(
            shared_memory_object,
            signal_wrapper,
            weights_path=model_weights,
            tube_offset_body=(tube_offset_x, tube_offset_y),
            camera_id=camera_id if camera_source == "zed" else None,
            fov_x_deg=fov_x_deg,
            fov_y_deg=fov_y_deg,
            distance_mode=self.distance_mode,
        )

    def start(self) -> None:
        super().start()
        self.next_state(States.MOVE_TO_BOARD)

    def next_state(self, next: States) -> None:
        if not self.active or self.state == next:
            return

        match(next):
            case States.INIT:
                return

            case States.MOVE_TO_BOARD:
                self.shared_memory_object.target_x.value = self.x1
                self.shared_memory_object.target_y.value = self.y1
                self.shared_memory_object.target_z.value = self.depth
                self.wait_time = time.time()

            case States.SEARCH_FOR_HOLE:
                self.helper.reset_tracking()
                hole_label = self.helper.get_hole_label_for_torpedo(self.torpedo_num)
                self.helper.debug["current_hole"] = hole_label
                self.wait_time = time.time()

            case States.VERIFY_HOLE:
                self.wait_time = time.time()

            case States.ALIGN_TO_HOLE:
                self.wait_time = time.time()

            case States.VERIFY_FIRE_POSITION:
                self.wait_time = time.time()
                self.verify_entered_time = time.time()

            case States.FIRE_TORPEDO:
                self.helper.fire_torpedo(self.torpedo_num)

            case States.COMPLETE:
                self.suspend()

            case States.FAIL:
                self.logger.warning(f"{self.name} FAILED on torpedo {self.torpedo_num}")
                self.suspend()

            case _:
                self.logger.error(f"{self.name} INVALID NEXT STATE {next}")
                return

        old_state = self.state
        self.state = next
        self.logger.info(f"State changed: {old_state} -> {self.state}")

    def loop(self) -> None:
        if not self.active:
            return
        self.display(255, 80, 0)

        hole_label  = self.helper.get_hole_label_for_torpedo(self.torpedo_num)
        image_label = self.helper.get_image_label_for_torpedo(self.torpedo_num)

        match(self.state):
            case States.INIT:
                return

            case States.MOVE_TO_BOARD:
                if self.reached_xyz(self.x1, self.y1, self.depth):
                    self.next_state(States.SEARCH_FOR_HOLE)
                elif time.time() - self.wait_time > self.timeout:
                    self.next_state(States.SEARCH_FOR_HOLE)

            case States.SEARCH_FOR_HOLE:
                detections = self.helper.get_target_detections()
                board_image = self.helper.find_board_image(detections, image_label)
                target = self.helper.find_closest_hole(detections, hole_label, board_image)

                if target is not None:
                    self.current_target = target
                    self.next_state(States.VERIFY_HOLE)
                elif time.time() - self.wait_time > self.timeout:
                    self.next_state(States.FAIL)

                time.sleep(self.t_loop)

            case States.VERIFY_HOLE:
                detections = self.helper.get_target_detections()
                board_image = self.helper.find_board_image(detections, image_label)
                target = self.helper.find_closest_hole(detections, hole_label, board_image)

                if target is not None:
                    self.current_target = target
                    if self.helper.check_target_stable(target):
                        self.next_state(States.ALIGN_TO_HOLE)
                elif time.time() - self.wait_time > self.timeout:
                    self.next_state(States.FAIL)

                time.sleep(self.t_loop)

            case States.ALIGN_TO_HOLE:
                result = self.helper.align_step(hole_label, image_label, self.x_lineup_tolerance, self.y_lineup_tolerance)
                self.current_target = result["target"]

                if result["lost"]:
                    self.next_state(States.SEARCH_FOR_HOLE)
                elif result["centered"] and result["at_range"] and result["dwell_ok"]:
                    self.next_state(States.VERIFY_FIRE_POSITION)
                elif time.time() - self.wait_time > self.timeout:
                    self.next_state(States.FAIL)

                time.sleep(self.t_loop)

            case States.VERIFY_FIRE_POSITION:
                result = self.helper.align_step(hole_label, image_label, self.x_lineup_tolerance, self.y_lineup_tolerance)
                self.current_target = result["target"]

                if result["lost"]:
                    self.next_state(States.SEARCH_FOR_HOLE)
                elif result["centered"] and result["at_range"] and result["dwell_ok"]:
                    settled  = time.time() - self.verify_entered_time >= self.final_settle_time
                    verified = result["target"] is not None and self.helper.check_target_verified(result["target"])
                    if settled and verified:
                        self.next_state(States.FIRE_TORPEDO)
                elif time.time() - self.wait_time > self.timeout:
                    self.next_state(States.FAIL)

                time.sleep(self.t_loop)

            case States.FIRE_TORPEDO:
                if self.torpedo_num < self.max_torpedoes:
                    self.torpedo_num += 1
                    self.next_state(States.SEARCH_FOR_HOLE)
                else:
                    self.next_state(States.COMPLETE)

            case States.COMPLETE:
                return

            case States.FAIL:
                return

            case _:
                self.logger.error(f"{self.name} INVALID STATE {self.state}")
