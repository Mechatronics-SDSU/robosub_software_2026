from utils.socket_send                      import set_screen
from fsm.fsm                                import FSM_Template
from enum                                   import Enum
from modules.vision.tor_pedo                import lineup
import modules.vision.main as vision

import yaml, os, time


"""
    discord: @.kech
    github: @rsunderr

    FSM for navigating through torpedo
    
"""

class States(Enum):
    INIT = "INIT"
    TO_TORPEDO = "TO_TORPEDO"
    SEARCHING = "SEARCHING"
    LINING_UP = "LINING_UP"
    VERIFYING = "VERIFYING"
    SHOOTING = "SHOOTING"

    def __str__(self) -> str: # make elegant string
        return self.value

class Torpedo_FSM(FSM_Template):
    """
    FSM for torpedo mode - Lining up and shooting torpedoes
    """
    def __init__(self, shared_memory_object, run_list: list):
        """
        Torpedo FSM constructor
        """
        # call parent constructor
        super().__init__(shared_memory_object, run_list)
        self.name: str      = "TORPEDO"
        self.state: States  = States.INIT  # initial state
        self.wait_time: time = time.time() # time tracking variable
        self.lineup = lineup(shared_memory_object)

        self.min_torpedo_distance = 0.5
        self.max_torpedo_distance = 8.0

        self.vision_open = False
        self.conf_threshold = 0.70

        self.search_window_frames = 30
        self.search_required_frames = 10

        self.track_window_frames = 15
        self.track_required_frames = 4
        self.track_aligned_required_frames = 5

        self.verify_window_frames = 10
        self.verify_required_frames = 6

        self.detection_history = []
        self.max_history_frames = max(
            self.search_window_frames,
            self.track_window_frames,
            self.verify_window_frames,
        )

        # TARGET VALUES-----------------------------------------------------------------------------------------------------------------------
        self.x1 = self.y1 = self.x2 = self.y2 = self.x3 = self.y3 = self.depth = 0
        try:
            with open(os.path.expanduser("~/robosub_software_2026/objects.yaml"), 'r') as file: # read from yaml
                data = yaml.safe_load(file)
                course = data['course']
                self.x_buffer = data[course]['torpedo']['x_buf']
                self.y_buffer = data[course]['torpedo']['y_buf']
                self.z_buffer = data[course]['torpedo']['z_buf']
                self.x1 = data[course]['torpedo']['x1']
                self.y1 = data[course]['torpedo']['y1']
                self.depth = data[course]['torpedo']['z']

                self.timeout = data[course]['torpedo']['timeout'] #FIXME how long before looking for torpedoes gives up
                self.t_loop = data[course]['torpedo']['t_loop'] # FIXME how long to wait before updating torpedo coordinates in loop
                self.desired_distance = data[course]['torpedo']['desired_distance'] # FIXME how far away do we want to be facing the torpedo target

        except KeyError:
            print("ERROR: Invalid data format in objects.yaml, using all 0's")

    def start(self) -> None:
        """
        Start FSM by enabling and starting processes
        """
        super().start()  # call parent start method

        # set initial state
        self.next_state(States.TO_TORPEDO)

    def next_state(self, next: States) -> None:
        """
        Change to the next FSM state.
        This should only contain one-time setup for entering a state.
        Repeated logic belongs in loop().
        """
        if not self.active or self.state == next:
            return

        match next:
            case States.INIT:
                return

            case States.TO_TORPEDO:
                # Move to rough YAML torpedo location
                self.shared_memory_object.target_x.value = self.x1
                self.shared_memory_object.target_y.value = self.y1
                self.shared_memory_object.target_z.value = self.depth

                self.wait_time = time.time()

            case States.SEARCHING:
                # Start a fresh vision search
                self.wait_time = time.time()
                self.detection_history.clear()

                if not self.vision_open:
                    vision.open_zed()
                    self.vision_open = True

            case States.LINING_UP:
                # Start tracking/alignment timer
                self.wait_time = time.time()
                self.detection_history.clear()

            case States.VERIFYING:
                # Start a clean verification window
                self.wait_time = time.time()
                self.detection_history.clear()

            case States.SHOOTING:
                # hold position before shooting
                time.sleep(2)

            case _:
                print(f"{self.name} INVALID NEXT STATE {next}")
                return

        self.state = next
        print(f"{self.name}:{self.state}")
    def loop(self) -> None:
        """
        Loop function, mostly state transitions within conditionals
        """
        if not self.active: return # do nothing if not enabled
        self.display(0, 255, 0) # update display

        # TRANSITIONS------------------------------------------------------------------------------------------------------
        match(self.state):
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
                        self.update_pid_targets_from_detection(target)
                        self.next_state(States.LINING_UP)

                elif time.time() - self.wait_time > self.timeout:
                    self.suspend()        

            case States.LINING_UP:
                self.update_detection_history()

                seen_count = self.count_seen_frames(self.track_window_frames)
                aligned_count = self.count_aligned_frames(self.track_window_frames)

                if len(self.detection_history) >= self.track_window_frames:
                    if seen_count < self.track_required_frames:
                        self.next_state(States.SEARCHING)

                    elif aligned_count >= self.track_aligned_required_frames:
                        self.next_state(States.VERIFYING)

                    else:
                        target = self.average_seen_target(self.track_window_frames)
                        if target is not None:
                            self.update_pid_targets_from_detection(target)
                else:
                    target = self.average_seen_target(self.track_window_frames)
                    if target is not None:
                        self.update_pid_targets_from_detection(target)            
            case States.VERIFYING:
                self.update_detection_history()

                aligned_count = self.count_aligned_frames(self.verify_window_frames)

                if aligned_count >= self.verify_required_frames:
                    self.next_state(States.SHOOTING)

                elif len(self.detection_history) >= self.verify_window_frames:
                    self.next_state(States.LINING_UP)    

            case States.SHOOTING:
                # TODO: run torpedo firing function here
                time.sleep(1)
                self.suspend()
            case _: # do nothing if invalid state
                print(f"{self.name} INVALID STATE {self.state}")

    def update_detection_history(self) -> None:
        detections = vision.build_detections()

        best_target = None
        best_conf = -1

        for detection in detections.values():
            label, class_id, conf, x_norm, y_norm, depth_m = detection

            if not self.is_valid_torpedo_detection(label, conf, x_norm, y_norm, depth_m):
                continue

            if conf > best_conf:
                best_target = {
                    "label": label,
                    "conf": conf,
                    "x": x_norm,
                    "y": y_norm,
                    "z": depth_m,
                }
                best_conf = conf

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
            aligned = (
                abs(best_target["x"] - 0.5) <= self.x_buffer
                and abs(best_target["y"] - 0.5) <= self.y_buffer
                and abs(best_target["z"] - self.desired_distance) <= self.z_buffer
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

    def recent_frames(self, window_size: int):
        return self.detection_history[-window_size:]


    def count_seen_frames(self, window_size: int) -> int:
        return sum(1 for frame in self.recent_frames(window_size) if frame["seen"])


    def count_aligned_frames(self, window_size: int) -> int:
        return sum(1 for frame in self.recent_frames(window_size) if frame["aligned"])

    def average_seen_target(self, window_size: int):
        frames = [
            frame for frame in self.recent_frames(window_size)
            if frame["seen"]
        ]

        if not frames:
            return None

        return {
            "x": sum(frame["x"] for frame in frames) / len(frames),
            "y": sum(frame["y"] for frame in frames) / len(frames),
            "z": sum(frame["z"] for frame in frames) / len(frames),
            "conf": sum(frame["conf"] for frame in frames) / len(frames),
        }
    
    def is_valid_torpedo_detection(self, label, conf, x_norm, y_norm, depth_m) -> bool:
        return (
            label == "torpedo"
            and conf >= self.conf_threshold
            and 0.0 <= x_norm <= 1.0
            and 0.0 <= y_norm <= 1.0
            and self.min_torpedo_distance <= depth_m <= self.max_torpedo_distance
        )
    
    def update_pid_targets_from_detection(self, target) -> None:
        self.lineup.update_xy_lineup(
            target["x"],
            target["y"],
            target["z"],
            self.desired_distance,
        )