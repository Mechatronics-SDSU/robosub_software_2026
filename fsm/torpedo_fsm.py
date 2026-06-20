from __future__ import annotations

from enum import Enum
import os
import time
import yaml

from utils.socket_send import set_screen
from fsm.fsm import FSM_Template

try:
    from modules.vision.tor_pedo import TorpedoLineup, LineupTarget
    from modules.vision.torpedo_config import TorpedoConfig, load_torpedo_config
except ModuleNotFoundError:  # Allows local testing outside the full repo layout.
    from tor_pedo import TorpedoLineup, LineupTarget
    from torpedo_config import TorpedoConfig, load_torpedo_config

import modules.vision.main as vision


"""
    discord: @.kech
    github: @rsunderr

    FSM for navigating through torpedo.
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
    FSM for torpedo mode.

    Flow:
        TO_TORPEDO -> SEARCHING -> LINING_UP -> VERIFYING -> SHOOTING

    SEARCHING:
        Open vision once, collect a frame window, and lock target after enough
        confident torpedo detections.

    LINING_UP:
        Move to the absolute lineup setpoint calculated from the averaged
        vision target and camera FOV math.

    VERIFYING:
        Once the sub reaches that setpoint, collect a fresh detection window.
        If the target is centered and at desired distance, shoot. If the target
        is still seen but not aligned, calculate a new setpoint and line up
        again. If it is not seen reliably, search again.
    """

    def __init__(self, shared_memory_object, run_list: list):
        super().__init__(shared_memory_object, run_list)

        self.name: str = "TORPEDO"
        self.state: States = States.INIT
        self.state_start_time: float = time.time()

        self.config: TorpedoConfig = load_torpedo_config()
        self.lineup = TorpedoLineup(shared_memory_object, self.config)

        self.vision_open = False
        self.vision_runtime = None

        self.detection_history: list[dict] = []
        self.max_history_frames = max(
            self.config.search_window_frames,
            self.config.track_window_frames,
            self.config.verify_window_frames,
        )

        self.lineup_target: LineupTarget | None = None

        # Course / mission target values from objects.yaml.
        # Hardware-specific camera values belong in .env through TorpedoConfig.
        self.x1 = 0.0
        self.y1 = 0.0
        self.depth = 0.0
        self.x_buffer = 0.05
        self.y_buffer = 0.05
        self.z_buffer = 0.3
        self.desired_distance = 2.0

        self._load_course_targets()

    def _load_course_targets(self) -> None:
        try:
            with open(
                os.path.expanduser("~/robosub_software_2026/objects.yaml"),
                "r",
                encoding="utf-8",
            ) as file:
                data = yaml.safe_load(file)

            course = data["course"]
            torpedo_data = data[course]["torpedo"]

            self.x_buffer = float(torpedo_data["x_buf"])
            self.y_buffer = float(torpedo_data["y_buf"])
            self.z_buffer = float(torpedo_data["z_buf"])
            self.x1 = float(torpedo_data["x1"])
            self.y1 = float(torpedo_data["y1"])
            self.depth = float(torpedo_data["z"])
            self.desired_distance = float(torpedo_data["desired_distance"])

            # Optional per-course overrides. If missing, .env defaults are used.
            self.search_timeout = float(
                torpedo_data.get("timeout", self.config.search_timeout)
            )
            self.movement_timeout = float(
                torpedo_data.get("movement_timeout", self.config.movement_timeout)
            )

        except (FileNotFoundError, KeyError, TypeError, ValueError) as exc:
            print(
                "ERROR: Invalid torpedo data in objects.yaml. "
                f"Using defaults. Details: {exc}"
            )
            self.search_timeout = self.config.search_timeout
            self.movement_timeout = self.config.movement_timeout

    def start(self) -> None:
        super().start()
        self.next_state(States.TO_TORPEDO)

    def next_state(self, next: States) -> None:
        """
        State entry setup only.
        Repeated checks belong in loop().
        """

        if not self.active or self.state == next:
            return

        match next:
            case States.INIT:
                return

            case States.TO_TORPEDO:
                self.set_pid_target(self.x1, self.y1, self.depth)
                self.lineup_target = None
                self.state_start_time = time.time()

            case States.SEARCHING:
                self.state_start_time = time.time()
                self.detection_history.clear()
                self.lineup_target = None
                self.open_vision_if_needed()

            case States.LINING_UP:
                self.state_start_time = time.time()
                self.detection_history.clear()

            case States.VERIFYING:
                self.state_start_time = time.time()
                self.detection_history.clear()

            case States.SHOOTING:
                self.state_start_time = time.time()
                time.sleep(self.config.pre_shoot_hold_sec)

            case _:
                print(f"{self.name} INVALID NEXT STATE {next}")
                return

        self.state = next
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
                conf = 0
                vis_count = 0
                for vis in dict:
                    if vis["t"] > time.time() - self.config.time_window:
                        conf += vis["conf"]
                        vis_count += 1
                if conf > threshold and vis_count > 10: #TODO ask vision guys how many samples they expect to see in a second
                    target = self.average_seen_target(self.config.search_window_frames)

                    if target is not None:
                        self.set_lineup_target_from_detection(target)
                        self.next_state(States.LINING_UP)

                elif self.state_time() > self.search_timeout:
                    self.suspend()

            case States.LINING_UP:
                # Keep checking vision while moving, but do not constantly chase
                # the target. Movement target changes only after SEARCHING or
                # failed VERIFYING calculates a new averaged setpoint.
                self.update_detection_history()

                if self.lineup_target is None:
                    self.next_state(States.SEARCHING)
                    return

                if len(self.detection_history) >= self.config.track_window_frames:
                    seen_count = self.count_seen_frames(
                        self.config.track_window_frames
                    )
                    if seen_count < self.config.track_required_frames:
                        self.next_state(States.SEARCHING)
                        return

                if self.reached_xyz(
                    self.lineup_target.x,
                    self.lineup_target.y,
                    self.lineup_target.z,
                ):
                    self.next_state(States.VERIFYING)

                elif self.state_time() > self.movement_timeout:
                    self.next_state(States.SEARCHING)

            case States.VERIFYING:
                self.update_detection_history()

                aligned_count = self.count_aligned_frames(
                    self.config.verify_window_frames
                )
                seen_count = self.count_seen_frames(self.config.verify_window_frames)

                if aligned_count >= self.config.verify_required_frames:
                    self.next_state(States.SHOOTING)

                elif len(self.detection_history) >= self.config.verify_window_frames:
                    target = self.average_seen_target(self.config.verify_window_frames)

                    if target is not None and seen_count >= self.config.track_required_frames:
                        self.set_lineup_target_from_detection(target)
                        self.next_state(States.LINING_UP)
                    else:
                        self.next_state(States.SEARCHING)

            case States.SHOOTING:
                self.fire_torpedoes()
                time.sleep(self.config.post_shoot_wait_sec)
                self.suspend()

            case _:
                print(f"{self.name} INVALID STATE {self.state}")

    def open_vision_if_needed(self) -> None:
        if self.vision_open:
            return

        # Preferred API added to modules.vision.main for FSM usage.
        if hasattr(vision, "open_vision"):
            self.vision_runtime = vision.open_vision(self.config.vision_config_path)

        # Fallback for older vision modules that expose an already-managed camera.
        elif hasattr(vision, "open_zed"):
            try:
                cfg = vision.load_config(self.config.vision_config_path)
                self.vision_runtime = vision.open_zed(cfg)
            except TypeError:
                self.vision_runtime = vision.open_zed()

        self.vision_open = True

        if self.config.camera_startup_delay > 0:
            time.sleep(self.config.camera_startup_delay)

    def read_detections(self) -> dict:
        """
        Get one live detection dict from the vision module.
        """

        if hasattr(vision, "get_detections"):
            return vision.get_detections(self.vision_runtime)

        if hasattr(vision, "build_live_detections"):
            return vision.build_live_detections(self.vision_runtime)

        # Last-resort fallback for old code where build_detections() was a
        # no-argument live function.
        return vision.build_detections()

    def update_detection_history(self) -> None:
        detections = self.read_detections()

        best_target = None
        best_score = -1.0

        for detection in detections.values():
            t, label, class_id, conf, x_norm, y_norm, depth_m = detection

            if not self.is_valid_torpedo_detection(
                label,
                conf,
                x_norm,
                y_norm,
                depth_m,
            ):
                continue

            score = self.score_detection(conf, x_norm, y_norm, depth_m)

            if score > best_score:
                best_target = {
                    "t" : time.time(),
                    "label": label,
                    "class_id": class_id,
                    "conf": conf,
                    "x": x_norm,
                    "y": y_norm,
                    "z": depth_m,
                }
                best_score = score

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
            aligned = self.lineup.target_is_aligned(
                best_target,
                self.desired_distance,
                self.x_buffer,
                self.y_buffer,
                self.z_buffer,
            )

            frame = {
                "seen": True,
                "aligned": aligned,
                "x": best_target["x"],
                "y": best_target["y"],
                "z": best_target["z"],
                "conf": best_target["conf"],
            }

        self.detection_history.append(frame)
        self.detection_history = self.detection_history[-self.max_history_frames:]

    def is_valid_torpedo_detection(
        self,
        label,
        conf,
        x_norm,
        y_norm,
        depth_m,
    ) -> bool:
        return (
            str(label).lower() == self.config.target_label.lower()
            and conf >= self.config.conf_threshold
            and 0.0 <= x_norm <= 1.0
            and 0.0 <= y_norm <= 1.0
            and self.config.min_torpedo_distance
            <= depth_m
            <= self.config.max_torpedo_distance
        )

    def score_detection(
        self,
        conf: float,
        x_norm: float,
        y_norm: float,
        depth_m: float,
    ) -> float:
        """
        Prefer high confidence and avoid huge jumps from the recent average.
        """

        score = float(conf)
        recent_target = self.average_seen_target(self.config.track_window_frames)

        if recent_target is not None:
            score -= abs(x_norm - recent_target["x"]) * 0.35
            score -= abs(y_norm - recent_target["y"]) * 0.35
            score -= abs(depth_m - recent_target["z"]) * 0.05

        return score

    def set_lineup_target_from_detection(self, target: dict) -> None:
        base_x, base_y, base_z = self.get_pid_target()

        self.lineup_target = self.lineup.detection_to_target(
            base_x,
            base_y,
            base_z,
            target,
            self.desired_distance,
        )

        self.set_pid_target(
            self.lineup_target.x,
            self.lineup_target.y,
            self.lineup_target.z,
        )

    def set_pid_target(self, x: float, y: float, z: float) -> None:
        self.shared_memory_object.target_x.value = x
        self.shared_memory_object.target_y.value = y
        self.shared_memory_object.target_z.value = z

    def get_pid_target(self) -> tuple[float, float, float]:
        return (
            float(self.shared_memory_object.target_x.value),
            float(self.shared_memory_object.target_y.value),
            float(self.shared_memory_object.target_z.value),
        )

    def recent_frames(self, window_size: int) -> list[dict]:
        return self.detection_history[-window_size:]

    def count_seen_frames(self, window_size: int) -> int:
        return sum(1 for frame in self.recent_frames(window_size) if frame["seen"])

    def count_aligned_frames(self, window_size: int) -> int:
        return sum(
            1 for frame in self.recent_frames(window_size) if frame["aligned"]
        )

    def average_seen_target(self, window_size: int) -> dict | None:
        frames = [
            frame for frame in self.recent_frames(window_size) if frame["seen"]
        ]

        if not frames:
            return None

        return {
            "x": sum(frame["x"] for frame in frames) / len(frames),
            "y": sum(frame["y"] for frame in frames) / len(frames),
            "z": sum(frame["z"] for frame in frames) / len(frames),
            "conf": sum(frame["conf"] for frame in frames) / len(frames),
        }

    def state_time(self) -> float:
        return time.time() - self.state_start_time

    def fire_torpedoes(self) -> None:
        """
        Hook for the real torpedo firing code.
        """

        print(f"{self.name}: FIRE TORPEDO")
        # TODO: call the torpedo firing hardware function here.
