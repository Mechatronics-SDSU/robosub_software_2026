from __future__ import annotations

from enum import Enum
import os
import time
import yaml

from utils.socket_send import set_screen
from fsm.fsm import FSM_Template
from modules.vision.tor_pedo import DEFAULT_ENV_PATH, TorpedoLineup, load_env_file
import modules.vision.main as vision


"""
    discord: @.kech
    github: @rsunderr

    FSM for navigating through torpedo.

    The FSM owns state transitions only. The vision module owns camera/model
    inference. tor_pedo.py owns camera-FOV math and conversion to meter offsets.
"""


class States(Enum):
    INIT = "INIT"
    TO_TORPEDO = "TO_TORPEDO"
    SEARCHING = "SEARCHING"
    LINING_UP = "LINING_UP"
    VERIFYING = "VERIFYING"
    SHOOTING = "SHOOTING"

    def __str__(self) -> str:
        return self.value


class Torpedo_FSM(FSM_Template):
    """
    Torpedo FSM.

    Flow:
        TO_TORPEDO: move to the rough YAML position.
        SEARCHING: open vision and collect confident target frames.
        LINING_UP: move to the computed lineup setpoint.
        VERIFYING: collect fresh frames at the setpoint.
        SHOOTING: fire torpedoes, wait briefly, then suspend.
    """

    def __init__(self, shared_memory_object, run_list: list):
        super().__init__(shared_memory_object, run_list)

        self.name: str = "TORPEDO"
        self.state: States = States.INIT
        self.state_start_time: float = time.time()

        self.env_path = os.environ.get("ROBO_SUB_ENV_PATH", DEFAULT_ENV_PATH)
        self.env_values = load_env_file(self.env_path)
        self.env_values.update(os.environ)

        self.lineup = TorpedoLineup(
            shared_memory_object=shared_memory_object,
            env_path=self.env_path,
        )

        self.vision_detector = None
        self.vision_open = False
        self.vision_config_path = self._get_env_value(
            ["TORPEDO_VISION_CONFIG_PATH", "VISION_CONFIG_PATH"],
            "~/robosub_software_2026/modules/vision/config.yaml",
        )

        self.target_label = "torpedo"
        self.conf_threshold = 0.70
        self.min_torpedo_distance = 0.5
        self.max_torpedo_distance = 8.0

        self.search_window_frames = 30
        self.search_required_frames = 10

        self.track_window_frames = 15
        self.track_required_frames = 4
        self.track_aligned_required_frames = 5

        self.verify_window_frames = 10
        self.verify_required_frames = 6
        self.verify_seen_required_frames = 4

        self.detection_history: list[dict] = []
        self.max_history_frames = max(
            self.search_window_frames,
            self.track_window_frames,
            self.verify_window_frames,
        )

        self.lineup_setpoint = None
        self.has_fired = False
        self.last_target = None

        # Target and mission values from objects.yaml.
        self.x1 = 0.0
        self.y1 = 0.0
        self.depth = 0.0
        self.x_buffer = 0.05
        self.y_buffer = 0.05
        self.z_buffer = 0.30
        self.yaw_buffer = 5.0
        self.timeout = 30.0
        self.desired_distance = 2.0
        self.t_loop = 0.0

        self._load_torpedo_yaml()

        print(
            f"{self.name}: camera={self.lineup.config.camera_model} "
            f"res={self.lineup.config.camera_resolution} "
            f"hfov={self.lineup.config.horizontal_fov_deg} "
            f"vfov={self.lineup.config.vertical_fov_deg}"
        )

    def _load_torpedo_yaml(self) -> None:
        yaml_path = os.path.expanduser(
            self._get_env_value(
                ["TORPEDO_OBJECTS_PATH", "OBJECTS_YAML_PATH"],
                "~/robosub_software_2026/objects.yaml",
            )
        )

        try:
            with open(yaml_path, "r") as file:
                data = yaml.safe_load(file) or {}

            course = data.get("course")
            torpedo_data = data.get(course, {}).get("torpedo", {})

            self.x_buffer = float(torpedo_data.get("x_buf", self.x_buffer))
            self.y_buffer = float(torpedo_data.get("y_buf", self.y_buffer))
            self.z_buffer = float(torpedo_data.get("z_buf", self.z_buffer))
            self.yaw_buffer = float(torpedo_data.get("yaw_buf", self.yaw_buffer))

            self.x1 = float(torpedo_data.get("x1", self.x1))
            self.y1 = float(torpedo_data.get("y1", self.y1))
            self.depth = float(torpedo_data.get("z", self.depth))

            self.timeout = float(torpedo_data.get("timeout", self.timeout))
            self.t_loop = float(torpedo_data.get("t_loop", self.t_loop))
            self.desired_distance = float(
                torpedo_data.get("desired_distance", self.desired_distance)
            )
            self.target_label = str(torpedo_data.get("target_label", self.target_label))

            self.conf_threshold = float(
                torpedo_data.get("conf_threshold", self.conf_threshold)
            )
            self.min_torpedo_distance = float(
                torpedo_data.get("min_torpedo_distance", self.min_torpedo_distance)
            )
            self.max_torpedo_distance = float(
                torpedo_data.get("max_torpedo_distance", self.max_torpedo_distance)
            )

            self.search_window_frames = int(
                torpedo_data.get("search_window_frames", self.search_window_frames)
            )
            self.search_required_frames = int(
                torpedo_data.get("search_required_frames", self.search_required_frames)
            )
            self.track_window_frames = int(
                torpedo_data.get("track_window_frames", self.track_window_frames)
            )
            self.track_required_frames = int(
                torpedo_data.get("track_required_frames", self.track_required_frames)
            )
            self.track_aligned_required_frames = int(
                torpedo_data.get(
                    "track_aligned_required_frames",
                    self.track_aligned_required_frames,
                )
            )
            self.verify_window_frames = int(
                torpedo_data.get("verify_window_frames", self.verify_window_frames)
            )
            self.verify_required_frames = int(
                torpedo_data.get("verify_required_frames", self.verify_required_frames)
            )
            self.verify_seen_required_frames = int(
                torpedo_data.get(
                    "verify_seen_required_frames",
                    self.verify_seen_required_frames,
                )
            )

            self.max_history_frames = max(
                self.search_window_frames,
                self.track_window_frames,
                self.verify_window_frames,
            )

        except FileNotFoundError:
            print(f"{self.name}: objects.yaml not found at {yaml_path}; using defaults")

        except (KeyError, TypeError, ValueError) as exc:
            print(f"{self.name}: invalid torpedo YAML data; using defaults: {exc}")

    def start(self) -> None:
        super().start()
        self.next_state(States.TO_TORPEDO)

    def next_state(self, next_state: States) -> None:
        """
        Enter a new state. Only one-time setup belongs here.
        Repeated checks belong in loop().
        """

        if not self.active or self.state == next_state:
            return

        match next_state:
            case States.INIT:
                return

            case States.TO_TORPEDO:
                self._set_target_xyz(self.x1, self.y1, self.depth)
                self.state_start_time = time.time()

            case States.SEARCHING:
                self.state_start_time = time.time()
                self.detection_history.clear()
                self.open_vision()

            case States.LINING_UP:
                self.state_start_time = time.time()
                self.detection_history.clear()

            case States.VERIFYING:
                self.state_start_time = time.time()
                self.detection_history.clear()

            case States.SHOOTING:
                self.state_start_time = time.time()

            case _:
                print(f"{self.name} INVALID NEXT STATE {next_state}")
                return

        self.state = next_state
        print(f"{self.name}:{self.state}")

    def loop(self) -> None:
        if not self.active:
            return

        self.display(0, 255, 0)

        match self.state:
            case States.INIT:
                return

            case States.TO_TORPEDO:
                if self.reached_xyz(self.x1, self.y1, self.depth):
                    self.next_state(States.SEARCHING)

            case States.SEARCHING:
                self.update_detection_history()

                if self.count_seen_frames(self.search_window_frames) >= self.search_required_frames:
                    target = self.average_seen_target(self.search_window_frames)
                    if target is not None:
                        self.update_lineup_setpoint_from_detection(target)
                        self.next_state(States.LINING_UP)

                elif self._state_timed_out():
                    print(f"{self.name}: search timed out")
                    self.suspend()

            case States.LINING_UP:
                if self.reached_lineup_setpoint():
                    self.next_state(States.VERIFYING)

                elif self._state_timed_out():
                    print(f"{self.name}: lineup timed out; searching again")
                    self.next_state(States.SEARCHING)

            case States.VERIFYING:
                self.update_detection_history()

                aligned_count = self.count_aligned_frames(self.verify_window_frames)
                seen_count = self.count_seen_frames(self.verify_window_frames)

                if aligned_count >= self.verify_required_frames:
                    self.next_state(States.SHOOTING)

                elif len(self.detection_history) >= self.verify_window_frames:
                    target = self.average_seen_target(self.verify_window_frames)

                    if target is not None and seen_count >= self.verify_seen_required_frames:
                        self.update_lineup_setpoint_from_detection(target)
                        self.next_state(States.LINING_UP)
                    else:
                        self.next_state(States.SEARCHING)

                elif self._state_timed_out():
                    self.next_state(States.SEARCHING)

            case States.SHOOTING:
                self.fire_torpedo()
                time.sleep(1)
                self.suspend()

            case _:
                print(f"{self.name} INVALID STATE {self.state}")

    def open_vision(self) -> None:
        if self.vision_open:
            return

        if not hasattr(vision, "create_live_detector"):
            raise RuntimeError(
                "modules.vision.main must expose create_live_detector(). "
                "Update main.py with the LiveVisionDetector wrapper."
            )

        self.vision_detector = vision.create_live_detector(self.vision_config_path)
        self.vision_detector.open()
        self.vision_open = True

    def close_vision(self) -> None:
        if self.vision_detector is not None:
            self.vision_detector.close()
            self.vision_detector = None

        self.vision_open = False

    def update_detection_history(self) -> None:
        if not self.vision_open:
            self.open_vision()

        detections = self.vision_detector.get_detections()
        best_target = self.choose_best_target(detections)

        if best_target is None:
            frame = {
                "seen": False,
                "aligned": False,
                "x": None,
                "y": None,
                "z": None,
                "conf": 0.0,
            }
        else:
            aligned = self.target_is_aligned(best_target)
            frame = {
                "seen": True,
                "aligned": aligned,
                "x": best_target["x"],
                "y": best_target["y"],
                "z": best_target["z"],
                "conf": best_target["conf"],
            }
            self.last_target = frame

        self.detection_history.append(frame)
        self.detection_history = self.detection_history[-self.max_history_frames:]

    def choose_best_target(self, detections: dict) -> dict | None:
        best_target = None
        best_score = -999.0

        for detection in detections.values():
            label, class_id, conf, x_norm, y_norm, depth_m = detection

            if not self.is_valid_torpedo_detection(label, conf, x_norm, y_norm, depth_m):
                continue

            score = float(conf)

            if self.last_target is not None and self.last_target.get("seen"):
                score -= abs(float(x_norm) - float(self.last_target["x"])) * 0.25
                score -= abs(float(y_norm) - float(self.last_target["y"])) * 0.25
                score -= abs(float(depth_m) - float(self.last_target["z"])) * 0.05

            if score > best_score:
                best_target = {
                    "label": label,
                    "class_id": class_id,
                    "conf": float(conf),
                    "x": float(x_norm),
                    "y": float(y_norm),
                    "z": float(depth_m),
                }
                best_score = score

        return best_target

    def is_valid_torpedo_detection(self, label, conf, x_norm, y_norm, depth_m) -> bool:
        return (
            label == self.target_label
            and float(conf) >= self.conf_threshold
            and 0.0 <= float(x_norm) <= 1.0
            and 0.0 <= float(y_norm) <= 1.0
            and self.min_torpedo_distance <= float(depth_m) <= self.max_torpedo_distance
        )

    def target_is_aligned(self, target: dict) -> bool:
        return (
            abs(target["x"] - 0.5) <= self.x_buffer
            and abs(target["y"] - 0.5) <= self.y_buffer
            and abs(target["z"] - self.desired_distance) <= self.z_buffer
        )

    def recent_frames(self, window_size: int) -> list[dict]:
        return self.detection_history[-window_size:]

    def count_seen_frames(self, window_size: int) -> int:
        return sum(1 for frame in self.recent_frames(window_size) if frame["seen"])

    def count_aligned_frames(self, window_size: int) -> int:
        return sum(1 for frame in self.recent_frames(window_size) if frame["aligned"])

    def average_seen_target(self, window_size: int) -> dict | None:
        frames = [frame for frame in self.recent_frames(window_size) if frame["seen"]]

        if not frames:
            return None

        return {
            "x": sum(frame["x"] for frame in frames) / len(frames),
            "y": sum(frame["y"] for frame in frames) / len(frames),
            "z": sum(frame["z"] for frame in frames) / len(frames),
            "conf": sum(frame["conf"] for frame in frames) / len(frames),
        }

    def update_lineup_setpoint_from_detection(self, target: dict) -> None:
        base_x = self._read_shared_value("dvl_x", self.x1)
        base_y = self._read_shared_value("dvl_y", self.y1)
        base_z = self._read_shared_value("dvl_z", self.depth)
        base_yaw = self._read_shared_value("dvl_yaw", self._read_shared_value("target_yaw", 0.0))

        self.lineup_setpoint = self.lineup.detection_to_setpoint(
            x_norm=target["x"],
            y_norm=target["y"],
            depth_m=target["z"],
            desired_distance_m=self.desired_distance,
            base_x=base_x,
            base_y=base_y,
            base_z=base_z,
            base_yaw_deg=base_yaw,
        )

        self._set_target_xyz(
            self.lineup_setpoint.x,
            self.lineup_setpoint.y,
            self.lineup_setpoint.z,
        )
        self._set_target_yaw(self.lineup_setpoint.yaw)

        print(
            f"{self.name}: lineup target x={self.lineup_setpoint.x:.2f} "
            f"y={self.lineup_setpoint.y:.2f} z={self.lineup_setpoint.z:.2f} "
            f"yaw={self.lineup_setpoint.yaw:.2f}"
        )

    def reached_lineup_setpoint(self) -> bool:
        if self.lineup_setpoint is None:
            return False

        xyz_ok = self.reached_xyz(
            self.lineup_setpoint.x,
            self.lineup_setpoint.y,
            self.lineup_setpoint.z,
        )

        if not xyz_ok:
            return False

        current_yaw = self._read_shared_value("dvl_yaw", None)
        if current_yaw is None:
            return True

        yaw_error = abs(self._angle_delta_deg(self.lineup_setpoint.yaw, current_yaw))
        return yaw_error <= self.yaw_buffer

    def fire_torpedo(self) -> None:
        if self.has_fired:
            return

        # Replace or extend these names once the shooter shared-memory flag is final.
        for flag_name in ["fire_torpedo", "torpedo_fire", "shoot_torpedo"]:
            flag = getattr(self.shared_memory_object, flag_name, None)
            if flag is not None and hasattr(flag, "value"):
                flag.value = True
                self.has_fired = True
                print(f"{self.name}: fired using shared memory flag {flag_name}")
                return

        self.has_fired = True
        print(f"{self.name}: TODO fire torpedo actuator")

    def suspend(self) -> None:
        self.close_vision()
        super().suspend()

    def _state_timed_out(self) -> bool:
        return time.time() - self.state_start_time > self.timeout

    def _set_target_xyz(self, x: float, y: float, z: float) -> None:
        self.shared_memory_object.target_x.value = x
        self.shared_memory_object.target_y.value = y
        self.shared_memory_object.target_z.value = z

    def _set_target_yaw(self, yaw: float) -> None:
        target_yaw = getattr(self.shared_memory_object, "target_yaw", None)
        if target_yaw is not None and hasattr(target_yaw, "value"):
            target_yaw.value = yaw

    def _read_shared_value(self, name: str, default):
        obj = getattr(self.shared_memory_object, name, None)

        if obj is None:
            return default

        if hasattr(obj, "value"):
            return float(obj.value)

        return float(obj)

    def _get_env_value(self, keys: list[str], default: str) -> str:
        sub_name = self.env_values.get("SUB_NAME", "").upper()

        for key in keys:
            sub_key = f"{sub_name}_{key}"
            if sub_key in self.env_values:
                return str(self.env_values[sub_key])

        for key in keys:
            if key in self.env_values:
                return str(self.env_values[key])

        return default

    @staticmethod
    def _angle_delta_deg(target_deg: float, current_deg: float) -> float:
        delta = target_deg - current_deg

        while delta > 180.0:
            delta -= 360.0

        while delta < -180.0:
            delta += 360.0

        return delta
