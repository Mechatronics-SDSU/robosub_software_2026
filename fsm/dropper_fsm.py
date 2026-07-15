import os
import time
import yaml

from fsm.fsm                                import FSM_Template
from modules.logger.logger                  import Logger
from modules.dropper.dropper_helpers        import DropperHelpers
from modules.vision.target_box_helpers      import stop_vehicle_motion
from enum                                   import Enum


"""
    FSM for the Recon Bins (dropper) task - step-move search with digital
    zoom, one confirmed bin, both markers:

    1. park over the bins area from objects.yaml coordinates, holding a fixed
       yaw (forward = shallower bins; a steady heading also lets the flip
       arbiter latch an orientation)
    2. search with YOLO filtered to fire/blood; the frame gate demands
       stable_frames consecutive frames at conf_strict + stable_iou overlap +
       a non-empty all-boxes intersection before anything counts
    3. 8 empty frames -> advance the DIGITAL zoom ladder (center-crop before
       inference - the sub never descends; balls land fine from height)
    4. on a confirmed target: ONE absolute move over the bin (dropper offset
       applied), settle ~1s for bubbles/blur, re-confirm, drop both markers
    5. hard 25s budget -> blind drop and move on (points beat pride)
"""

class States(Enum):
    """
    Enumeration for FSM states
    """
    INIT          = "INIT"
    MOVE_TO_BINS  = "MOVE_TO_BINS"
    SEARCH        = "SEARCH"
    MOVE_OVER_BIN = "MOVE_OVER_BIN"
    CONFIRM       = "CONFIRM"
    RECOVERY      = "RECOVERY"
    DROP          = "DROP"
    BLIND_DROP    = "BLIND_DROP"
    COMPLETE      = "COMPLETE"
    FAIL          = "FAIL"

    def __str__(self) -> str: # make elegant string
        return self.value


# states past the point of no return - the budget watchdog must not preempt an actual drop
ENDGAME_STATES = {States.DROP, States.BLIND_DROP, States.COMPLETE, States.FAIL}


class Dropper_FSM(FSM_Template):
    """
    FSM for dropper mode (Recon Bins) - single-bin / both-markers strategy.

    Search is measurement-first: no continuous nudging (the sub can't do
    small movements reliably). The loop is measure 4 clean frames -> command
    one absolute move -> settle -> re-confirm -> drop, with a digital-zoom
    ladder when nothing is seen and a blind drop on the hard time budget so
    the run always continues to the next FSM.
    """
    def __init__(self, shared_memory_object, run_list: list, signal_wrapper=None):
        """
        Dropper FSM constructor

        signal_wrapper: a real SignalWrapper (modules/signals/SignalWrapper.py)
        built from the shared USB_Transmitter, or None to use safe print
        placeholders instead of actuating real hardware (e.g. test mode).
        """
        # call parent constructor
        super().__init__(shared_memory_object, run_list)
        self.name: str      = "DROPPER"
        self.state: States  = States.INIT  # initial state
        self.logger = Logger()

        # APPROACH VALUES-----------------------------------------------------------------------------------------------------------
        self.x1 = self.y1 = self.depth = 0.0
        self.yaw = 0.0                    # heading held over the bins (forward = shallower bins)
        self.x_buffer = self.y_buffer = self.z_buffer = 0.10
        self.timeout = 8.0                # per-state timeout (approach / confirm windows)
        self.t_loop = 0.10

        # VISION / GATE VALUES------------------------------------------------------------------------------------------------------
        self.target_depth = 1.0           # m, bin plane depth (FIXME placeholder, measure on-site)
        self.conf_strict = 0.70           # per-frame confidence the gate demands
        self.stable_frames = 4            # consecutive frames before a target counts
        self.stable_iou = 0.60            # positional overlap between those frames
        self.class_swap_wait = 0.2        # settle when the YOLO classes filter changes
        self.center_outlier_iqr = 1.5     # IQR multiplier for the aim-point outlier drop
        self.role_patience = 6.0          # s accepting ONLY the role's bin before either counts
        self.max_object_yaml_error = 1.0  # m, reject an aim whose world estimate is this far from x1/y1

        # ZOOM LADDER (digital - center-crop before inference, the sub never moves for this)---------------------------------------
        self.zoom_factors = [1.0, 1.5, 2.0, 3.0]
        self.empty_frames_trigger = 8     # consecutive empty frames before advancing the zoom

        # STEP-MOVE / DROP VALUES---------------------------------------------------------------------------------------------------
        self.move_settle = 1.0            # s pause after a move (bubbles, motion blur)
        self.move_timeout = 6.0           # s to reach the commanded position before confirming anyway
        self.align_attempts = 3           # re-aim moves allowed before dropping from wherever we are
        self.x_lineup_tolerance = 0.10    # m, dropper-to-aim error allowed at drop time
        self.y_lineup_tolerance = 0.10    # m
        self.drop_count = 2               # both balls into the one confirmed bin
        self.drop_gap = 1.0               # s between the two spins

        # BUDGET / WATCHDOGS--------------------------------------------------------------------------------------------------------
        self.task_time_budget = 25.0      # s from starting the search to the blind-drop fallback
        self.dvl_grace = 5.0
        self.max_depth_limit = 3.0

        # RECOVERY PLACEHOLDER------------------------------------------------------------------------------------------------------
        self.recovery_enabled = False     # stub only - see States.RECOVERY below

        role = "survey_and_repair"
        dropper_offset_x = dropper_offset_y = 0.0
        model_weights = "models/best.pt"

        # hardware settings live in hardware.yaml (camera-independent, deployment-specific)
        hw_path = os.path.expanduser("~/robosub_software_2026/config/hardware.yaml")
        try:
            with open(hw_path) as f:
                hw = yaml.safe_load(f)
                d = hw.get('dropper', {})
                model_weights    = d.get('model_weights', model_weights)
                dropper_offset_x = d.get('offset_x', dropper_offset_x)
                dropper_offset_y = d.get('offset_y', dropper_offset_y)
        except FileNotFoundError:
            self.logger.error(f"{self.name} ERROR: config/hardware.yaml not found, using default dropper hardware values")
        except KeyError:
            self.logger.error(f"{self.name} ERROR: Invalid format in config/hardware.yaml, using default dropper hardware values")

        try:
            with open(os.path.expanduser("~/robosub_software_2026/objects.yaml"), 'r') as file: # read from yaml
                data = yaml.safe_load(file)
                course = data['course']
                # role is a single top-level switch for the whole run, not duplicated per-course/per-task
                role = data.get('role', role)
                dropper = data[course]['dropper']

                self.x_buffer = dropper.get('x_buf', self.x_buffer)
                self.y_buffer = dropper.get('y_buf', self.y_buffer)
                self.z_buffer = dropper.get('z_buf', self.z_buffer)
                self.x1 = dropper.get('x1', self.x1)
                self.y1 = dropper.get('y1', self.y1)
                self.depth = dropper.get('z', self.depth)
                self.yaw = dropper.get('yaw', self.yaw)

                self.timeout = dropper.get('timeout', self.timeout)
                self.t_loop = dropper.get('t_loop', self.t_loop)
                self.target_depth = dropper.get('target_depth', self.target_depth)
                self.conf_strict = dropper.get('conf_strict', self.conf_strict)
                self.stable_frames = dropper.get('stable_frames', self.stable_frames)
                self.stable_iou = dropper.get('stable_iou', self.stable_iou)
                self.class_swap_wait = dropper.get('class_swap_wait', self.class_swap_wait)
                self.center_outlier_iqr = dropper.get('center_outlier_iqr', self.center_outlier_iqr)
                self.role_patience = dropper.get('role_patience', self.role_patience)
                self.max_object_yaml_error = dropper.get('max_object_yaml_error', self.max_object_yaml_error)

                self.zoom_factors = list(dropper.get('zoom_factors', self.zoom_factors))
                self.empty_frames_trigger = dropper.get('empty_frames_trigger', self.empty_frames_trigger)

                self.move_settle = dropper.get('move_settle', self.move_settle)
                self.move_timeout = dropper.get('move_timeout', self.move_timeout)
                self.align_attempts = dropper.get('align_attempts', self.align_attempts)
                self.x_lineup_tolerance = dropper.get('x_lineup_tolerance', self.x_lineup_tolerance)
                self.y_lineup_tolerance = dropper.get('y_lineup_tolerance', self.y_lineup_tolerance)
                self.drop_count = dropper.get('drop_count', self.drop_count)
                self.drop_gap = dropper.get('drop_gap', self.drop_gap)

                self.task_time_budget = dropper.get('task_time_budget', self.task_time_budget)
                self.dvl_grace = dropper.get('dvl_grace', self.dvl_grace)
                self.max_depth_limit = dropper.get('max_depth_limit', self.max_depth_limit)
                self.recovery_enabled = dropper.get('recovery_enabled', self.recovery_enabled)

        except FileNotFoundError:
            self.logger.error(f"{self.name} ERROR: objects.yaml not found, using default dropper values")
        except KeyError:
            self.logger.error(f"{self.name} ERROR: Invalid data format in objects.yaml, using default dropper values")

        self.role = role # "survey_and_repair" or "search_and_rescue", set once for the whole run in objects.yaml
        self.helper = DropperHelpers(shared_memory_object, signal_wrapper, weights_path=model_weights,
                                      dropper_offset_body=(dropper_offset_x, dropper_offset_y),
                                      stable_frames=self.stable_frames, stable_iou=self.stable_iou,
                                      conf_strict=self.conf_strict, class_swap_wait=self.class_swap_wait,
                                      center_outlier_iqr=self.center_outlier_iqr)
        self.bin_ids = self.helper.get_bin_ids(self.role) # [preferred, other]

        # RUN PROGRESS--------------------------------------------------------------------------------------------------------------
        self.committed_class = None  # bin class id the gate confirmed (CONFIRM re-checks the SAME class)
        self.move_target = None      # world (x, y) commanded by MOVE_OVER_BIN
        self.last_aim = None         # last confirmed aim center (normalized)
        self.zoom_idx = 0
        self.aim_attempts = 0
        self.recovery_ran = False
        self.dropped_blind = False
        self.search_started = 0.0    # the 25s budget clock (starts on first SEARCH entry)
        self.wait_time = 0.0
        self.dvl_invalid_since = None

    # HELPERS----------------------------------------------------------------------------------------------------------------------
    def _accept_ids(self) -> list:
        """
        Acceptance order for the gate: role's bin only until role_patience has
        elapsed on the budget clock, then either bin (any bin scores; the
        correct one stays preferred because it's first in the list).
        """
        if time.time() - self.search_started < self.role_patience:
            return self.bin_ids[:1]
        return self.bin_ids

    def _budget_spent(self) -> bool:
        return self.search_started > 0 and time.time() - self.search_started > self.task_time_budget

    def _advance_zoom(self) -> bool:
        """
        Steps the digital zoom ladder. Returns True if a new level was
        engaged, False when max zoom was already reached.
        """
        if self.zoom_idx + 1 >= len(self.zoom_factors):
            return False
        self.zoom_idx += 1
        self.helper.set_zoom(self.zoom_factors[self.zoom_idx]) # also resets the gate + empty streak
        self.logger.info(f"{self.name} nothing seen for {self.empty_frames_trigger} frames - digital zoom -> x{self.zoom_factors[self.zoom_idx]}")
        return True

    # LIFECYCLE--------------------------------------------------------------------------------------------------------------------
    def start(self) -> None:
        """
        Start FSM by enabling and starting processes
        """
        super().start()  # call parent start method

        # loud early warning if the weights can't produce the configured bin ids
        try:
            missing = self.helper.verify_model_classes(self.bin_ids)
            if missing:
                self.logger.error(f"{self.name} MODEL MISSING CLASS IDS {missing} - "
                                  f"weights '{self.helper.weights_path}' can't see those bins, update the model!")
        except Exception as error:
            self.logger.error(f"{self.name} could not verify model classes: {error}")

        # set initial state
        self.next_state(States.MOVE_TO_BINS)

    def next_state(self, next: States) -> None:
        """
        Change to next state
        """
        if not self.active or self.state == next: return # do nothing if not enabled or no state change

        # STATES-----------------------------------------------------------------------------------------------------------------------
        match(next):
            case States.INIT:
                return # initial state

            case States.MOVE_TO_BINS: # park over the bins area, hold the configured heading
                self.shared_memory_object.target_x.value = self.x1
                self.shared_memory_object.target_y.value = self.y1
                self.shared_memory_object.target_z.value = self.depth
                self.shared_memory_object.target_yaw.value = self.yaw
                self.wait_time = time.time()

            case States.SEARCH: # frame-gated hunt; zoom ladder on empty streaks; budget clock runs
                if self.search_started == 0.0:
                    self.search_started = time.time() # the 25s budget starts at the FIRST search
                self.helper.gate_reset()
                self.wait_time = time.time()

            case States.MOVE_OVER_BIN: # ONE absolute move (dropper offset applied) - no nudging
                self.shared_memory_object.target_x.value = self.move_target[0]
                self.shared_memory_object.target_y.value = self.move_target[1]
                self.wait_time = time.time()

            case States.CONFIRM: # settle for bubbles/blur, then demand the gate pass again, same class
                time.sleep(self.move_settle)
                self.helper.gate_reset()
                self.wait_time = time.time()

            case States.RECOVERY:
                # ── PLACEHOLDER (do not implement yet - team decides next prompt) ──────────────
                # Candidate probes when nothing is seen / the wrong emoji is suspected:
                #   - extra frame orientations: X, Y, XY(180 deg) flips. NOTE: RAW/HFLIP/VFLIP are
                #     ALREADY cycled by FlipAwareYOLO's arbiter (modules/vision/dropper_flip_vision.py);
                #     only the combined XY/180 rotation would be new.
                #   - yaw notches: rotate in 30-degree intervals to offer YOLO a different aspect.
                # Gated by objects.yaml `recovery_enabled` (default false). Currently a no-op that
                # logs and returns to SEARCH so the ladder (zoom -> recovery -> blind drop) has its
                # slot reserved.
                self.logger.info(f"{self.name} RECOVERY placeholder (recovery_enabled={self.recovery_enabled}) - no probes implemented yet")
                self.recovery_ran = True

            case States.DROP: # both markers into the one confirmed bin
                self.helper.release_markers(self.drop_count, self.drop_gap)

            case States.BLIND_DROP: # timeout process: drop anyway and keep the run moving
                self.logger.warning(f"{self.name} budget spent without a confirmed bin - BLIND dropping {self.drop_count} markers at "
                                    f"({self.shared_memory_object.dvl_x.value:.2f}, {self.shared_memory_object.dvl_y.value:.2f})")
                self.dropped_blind = True
                self.helper.release_markers(self.drop_count, self.drop_gap)

            case States.COMPLETE:
                self.logger.info(f"{self.name} DONE: class={self.committed_class} blind={self.dropped_blind} "
                                 f"zoom=x{self.zoom_factors[self.zoom_idx]} aim_attempts={self.aim_attempts}")
                self.suspend() # finish dropper mode, ready for next mode

            case States.FAIL: # invalid-state landing only - normal failures blind-drop instead
                self.logger.warning(f"{self.name} FAILED")
                self.suspend() # give up, ready for next mode

            case _: # do nothing if invalid state
                self.logger.error(f"{self.name} INVALID NEXT STATE {next}")
                return

        old_state = self.state
        self.state = next
        self.logger.info(f"State changed: {old_state} -> {self.state}")

    def loop(self) -> None:
        """
        Loop function, mostly state transitions within conditionals
        """
        if not self.active: return # do nothing if not enabled
        self.display(255, 150, 0) # update display

        # GLOBAL WATCHDOGS-------------------------------------------------------------------------------------------------------
        # never dive past the course's hard depth limit, whatever wrote target_z
        if self.shared_memory_object.target_z.value > self.max_depth_limit:
            self.shared_memory_object.target_z.value = self.max_depth_limit
        # out of budget anywhere before the drop -> blind drop (the timeout process)
        if self.state not in ENDGAME_STATES and self._budget_spent():
            self.next_state(States.BLIND_DROP)
            return
        # navigating without DVL is drift - hold, then take the blind drop
        if self.state not in ENDGAME_STATES and hasattr(self.shared_memory_object, "dvl_velocity_valid"):
            if not self.shared_memory_object.dvl_velocity_valid.value:
                if self.dvl_invalid_since is None:
                    self.dvl_invalid_since = time.time()
                    stop_vehicle_motion(self.shared_memory_object)
                elif time.time() - self.dvl_invalid_since > self.dvl_grace:
                    self.logger.warning(f"{self.name} DVL invalid too long - taking the blind drop")
                    self.next_state(States.BLIND_DROP)
                    return
            else:
                self.dvl_invalid_since = None

        # TRANSITIONS------------------------------------------------------------------------------------------------------
        match(self.state):
            case States.INIT:
                return

            case States.MOVE_TO_BINS: # transition: MOVE_TO_BINS -> SEARCH
                if self.reached_xyz(self.x1, self.y1, self.depth):
                    self.next_state(States.SEARCH)
                elif time.time() - self.wait_time > self.timeout:
                    self.next_state(States.SEARCH)

            case States.SEARCH: # transition: SEARCH -> MOVE_OVER_BIN (confirmed) / zoom ladder / RECOVERY
                detections = self.helper.get_target_detections(classes=self.bin_ids)
                verdict = self.helper.gate_feed(detections, self._accept_ids())

                if verdict["confirmed"]:
                    move_target = self.helper.compute_move_target(verdict["aim_center"], self.target_depth)
                    if self.helper.validate_against_assumed(self.helper.bin_world, (self.x1, self.y1), self.max_object_yaml_error):
                        self.committed_class = verdict["class_id"]
                        self.last_aim = verdict["aim_center"]
                        self.move_target = move_target
                        self.aim_attempts = 0
                        self.logger.info(f"{self.name} bin class {self.committed_class} confirmed (outliers dropped: {verdict['n_outliers']}) - moving over it")
                        self.next_state(States.MOVE_OVER_BIN)
                    else:
                        self.logger.warning(f"{self.name} confirmed target rejected - world estimate too far from assumed bins, re-searching")
                        self.helper.gate_reset()
                elif verdict["empty_streak"] >= self.empty_frames_trigger:
                    if not self._advance_zoom():
                        if self.recovery_enabled and not self.recovery_ran:
                            self.next_state(States.RECOVERY)
                        # max zoom + no recovery: keep looking until the budget takes the blind drop
                        self.helper.gate_reset()

                time.sleep(self.t_loop)

            case States.MOVE_OVER_BIN: # transition: MOVE_OVER_BIN -> CONFIRM (arrived or move timeout)
                if self.reached_xy(self.move_target[0], self.move_target[1]) or time.time() - self.wait_time > self.move_timeout:
                    self.next_state(States.CONFIRM)

                time.sleep(self.t_loop)

            case States.CONFIRM: # transition: CONFIRM -> DROP / re-aim / SEARCH
                detections = self.helper.get_target_detections(classes=self.bin_ids)
                verdict = self.helper.gate_feed(detections, [self.committed_class]) # same class only

                if verdict["confirmed"]:
                    self.last_aim = verdict["aim_center"]
                    x_err, y_err = self.helper.aim_error_m(verdict["aim_center"], self.target_depth)
                    if abs(x_err) <= self.x_lineup_tolerance and abs(y_err) <= self.y_lineup_tolerance:
                        self.next_state(States.DROP)
                    else:
                        self.aim_attempts += 1
                        if self.aim_attempts > self.align_attempts:
                            self.logger.warning(f"{self.name} re-aim cap hit (err {x_err:.2f}, {y_err:.2f}m) - dropping from here, close beats never")
                            self.next_state(States.DROP)
                        else:
                            self.move_target = self.helper.compute_move_target(verdict["aim_center"], self.target_depth)
                            self.next_state(States.MOVE_OVER_BIN)
                elif time.time() - self.wait_time > self.timeout:
                    self.logger.warning(f"{self.name} bin not re-confirmed under the dropper - back to searching")
                    self.next_state(States.SEARCH)

                time.sleep(self.t_loop)

            case States.RECOVERY: # transition: RECOVERY -> SEARCH (placeholder is a no-op)
                self.next_state(States.SEARCH)

            case States.DROP: # transition: DROP -> COMPLETE
                self.next_state(States.COMPLETE)

            case States.BLIND_DROP: # transition: BLIND_DROP -> COMPLETE
                self.next_state(States.COMPLETE)

            case States.COMPLETE:
                return

            case States.FAIL:
                return

            case _: # do nothing if invalid state
                self.logger.error(f"{self.name} INVALID STATE {self.state}")
