import os
import time
import yaml

from fsm.fsm                                import FSM_Template
from modules.logger.logger                  import Logger
from modules.octagon.octagon_helpers        import OctagonHelpers, CLASS_LABELS, DEFAULT_ITEM_IDS, DEFAULT_ITEM_TO_BIN
from modules.vision.target_box_helpers      import stop_vehicle_motion
from enum                                   import Enum


"""
    FSM for the full Octagon/Resupply task (handbook 3.2.6) - THE octagon
    implementation (the old grabber FSM is retired into this):

    arrive at the octagon center (start_z ~1.0) -> one rise to unfold the new
    FIXED claw (grip-only: SignalWrapper.open()/close()) -> for each item on
    the whitelist [4 bandaid, 5 electric, 6 nutbolt, 7 pill]:
        search with the shared FrameGate (4 frames @ 0.7 conf, IoU chain,
        all-boxes intersection), highest confidence first (ties 4->5->6->7);
        nothing seen -> descend ~0.1m anchored steps to the no-scrape floor,
        bounce back up, repeat; found -> one big move over it, re-anchor when
        the box fills half the frame, refine, VERTICAL sink (the only state
        allowed below the floor), tighten the grip, rise to the surface
        watching for the item reappearing below (stable sighting = failed
        grab -> retry), then sort it: 4/7 -> redcross basket (8),
        5/6 -> warning basket (13), first item per bin placed BESIDE the
        marker so the second visit can still see it.
    All four handled (blacklist full) -> surface -> rotate until an icon for
    the count is seen -> spin 360 x len(blacklist). 720s budget backstop.
"""

class States(Enum):
    """
    Enumeration for FSM states
    """
    INIT           = "INIT"
    TO_OCT         = "TO_OCT"
    EXTEND_CLAW    = "EXTEND_CLAW"
    SEARCH_ITEM    = "SEARCH_ITEM"
    APPROACH_ITEM  = "APPROACH_ITEM"
    REFINE_ALIGN   = "REFINE_ALIGN"
    SINK_GRAB      = "SINK_GRAB"
    RISE_VERIFY    = "RISE_VERIFY"
    SORT_TO_BIN    = "SORT_TO_BIN"
    SEARCH_BIN     = "SEARCH_BIN"
    ALIGN_BIN      = "ALIGN_BIN"
    RELEASE        = "RELEASE"
    TO_TABLE       = "TO_TABLE"
    FINALE_SURFACE = "FINALE_SURFACE"
    FACE_ICON      = "FACE_ICON"
    SPIN           = "SPIN"
    COMPLETE       = "COMPLETE"
    FAIL           = "FAIL"

    def __str__(self) -> str: # make elegant string
        return self.value


FINALE_STATES = {States.FINALE_SURFACE, States.FACE_ICON, States.SPIN, States.COMPLETE, States.FAIL}
# the anti-scrape invariant: only the vertical sink may command deeper than the no-scrape floor
SINK_EXEMPT_STATES = {States.SINK_GRAB}


class Octagon_FSM(FSM_Template):
    """
    FSM for octagon mode - the full four-item manipulation task. Every state
    degrades toward banking the finale points (surface + icon + spins): item
    failures skip the item, carry losses re-add the class, and the budget
    watchdog jumps to the finale rather than dying in place.
    """
    def __init__(self, shared_memory_object, run_list: list, signal_wrapper=None):
        """
        Octagon FSM constructor

        signal_wrapper: a real SignalWrapper (modules/signals/SignalWrapper.py)
        built from the shared USB_Transmitter, or None to use safe print
        placeholders instead of actuating real hardware (e.g. test mode).
        """
        # call parent constructor
        super().__init__(shared_memory_object, run_list)
        self.name: str      = "OCTAGON"
        self.state: States  = States.INIT  # initial state
        self.logger = Logger()

        # APPROACH / GEOMETRY-------------------------------------------------------------------------------------------------------
        self.oct_x = self.oct_y = 0.0
        self.yaw = 0.0
        self.x_buffer = self.y_buffer = self.z_buffer = 0.10
        self.start_z = 1.0            # working depth the task starts and searches from (dvl.z ~ 1)
        self.table_top_z = 1.3716     # 7ft pool (2.1336) - 30in table (0.762); FIXME jesse_pool: measure
        self.item_height = 0.05       # items are ~1.97in tall
        self.hover_margin = 0.15      # extra clearance above the no-scrape floor (the ??? buffer)
        self.grab_depth_frac = 0.5    # grip lands this fraction down the item's height
        self.extend_lift = 0.4        # m to rise on arrival so the fixed claw's tines hang fully open
        self.timeout = 8.0
        self.t_loop = 0.10

        # ITEMS / BINS--------------------------------------------------------------------------------------------------------------
        self.item_class_ids = list(DEFAULT_ITEM_IDS)
        self.item_to_bin = dict(DEFAULT_ITEM_TO_BIN)
        self.baskets = { # bin class id -> {x, y, face_yaw}
            8:  {"x": 0.0, "y": 0.0, "face_yaw": 0.0},
            13: {"x": 0.0, "y": 0.0, "face_yaw": 0.0},
        }

        # GATE / VISION KNOBS-------------------------------------------------------------------------------------------------------
        self.conf_strict = 0.70
        self.stable_frames = 4
        self.stable_iou = 0.60
        self.center_outlier_iqr = 1.5
        self.class_swap_wait = 0.2
        self.anchor_settle = 1.0      # the standardized anchor pause (motion blur / bubbles)
        self.max_object_yaml_error = 1.5

        # SEARCH LADDER-------------------------------------------------------------------------------------------------------------
        self.empty_frames_trigger = 8 # consecutive empty frames before a descend step
        self.descend_step = 0.1       # m per anchored step down
        self.reanchor_frac = 0.5      # bbox w/h fraction of frame that triggers the mid-approach re-anchor

        # GRAB / CARRY--------------------------------------------------------------------------------------------------------------
        self.x_lineup_tolerance = 0.05
        self.y_lineup_tolerance = 0.05
        self.align_attempts = 3
        self.grab_retries = 2
        self.grip_settle = 1.0        # s after close() before rising
        self.surface_pause = 1.0      # s at the surface with the item (scored)
        self.rise_check_time = 2.5    # s an anchored rise-check watches before resuming ascent
        self.carry_max_width = 0.35
        self.carry_ignore_region = None

        # PLACEMENT-----------------------------------------------------------------------------------------------------------------
        self.place_side = "left"      # side of the bin marker the FIRST item lands on
        self.place_margin = 0.10
        self.place_margin_max = 0.25

        # FINALE / WATCHDOGS--------------------------------------------------------------------------------------------------------
        self.finale_turn_degrees = 360.0
        self.icon_scan_step = 15.0
        self.icon_timeout = 20.0
        self.icon_deg_per_image = 90.0
        self.icon_yaw_sign = 1.0
        self.rotation_step_timeout = 6.0
        self.task_time_budget = 720.0 # 12 min - last vision task, but return-home still needs its slice
        self.dvl_grace = 5.0
        self.max_depth_limit = 3.0

        # hardware settings live in config/hardware.yaml (deployment-specific, course-independent)
        model_weights = "models/best.pt"
        claw_offset_x = claw_offset_y = 0.0
        camera_rotate_180 = False
        auv_height = auv_height_claw_extended = None
        hw_path = os.path.expanduser("~/robosub_software_2026/config/hardware.yaml")
        try:
            with open(hw_path) as f:
                hw = yaml.safe_load(f)
                o = hw.get('octagon', {})
                model_weights = o.get('model_weights', model_weights)
                claw_offset_x = o.get('claw_offset_x', claw_offset_x)
                claw_offset_y = o.get('claw_offset_y', claw_offset_y)
                camera_rotate_180 = o.get('camera_rotate_180', camera_rotate_180)
                auv_height = o.get('auv_height', auv_height)
                auv_height_claw_extended = o.get('auv_height_claw_extended', auv_height_claw_extended)
        except FileNotFoundError:
            self.logger.error(f"{self.name} ERROR: config/hardware.yaml not found, using default octagon hardware values")
        except KeyError:
            self.logger.error(f"{self.name} ERROR: Invalid format in config/hardware.yaml, using default octagon hardware values")

        try:
            with open(os.path.expanduser("~/robosub_software_2026/objects.yaml"), 'r') as file: # read from yaml
                data = yaml.safe_load(file)
                course = data['course']
                oct_cfg = data[course]['octagon']

                self.x_buffer = oct_cfg.get('x_buf', self.x_buffer)
                self.y_buffer = oct_cfg.get('y_buf', self.y_buffer)
                self.z_buffer = oct_cfg.get('z_buf', self.z_buffer)
                self.oct_x = oct_cfg.get('x', self.oct_x)
                self.oct_y = oct_cfg.get('y', self.oct_y)
                self.yaw = oct_cfg.get('yaw', self.yaw)
                self.start_z = oct_cfg.get('start_z', self.start_z)
                self.table_top_z = oct_cfg.get('table_top_z', self.table_top_z)
                self.item_height = oct_cfg.get('item_height', self.item_height)
                self.hover_margin = oct_cfg.get('hover_margin', self.hover_margin)
                self.grab_depth_frac = oct_cfg.get('grab_depth_frac', self.grab_depth_frac)
                self.extend_lift = oct_cfg.get('extend_lift', self.extend_lift)
                self.timeout = oct_cfg.get('timeout', self.timeout)
                self.t_loop = oct_cfg.get('t_loop', self.t_loop)

                self.item_class_ids = list(oct_cfg.get('item_class_ids', self.item_class_ids))
                self.item_to_bin = {int(k): int(v) for k, v in oct_cfg.get('item_to_bin', self.item_to_bin).items()}
                for key in ('basket_a', 'basket_b'):
                    basket = oct_cfg.get(key)
                    if basket and 'bin_id' in basket:
                        self.baskets[int(basket['bin_id'])] = {
                            "x": basket.get('x', 0.0), "y": basket.get('y', 0.0),
                            "face_yaw": basket.get('face_yaw', 0.0),
                        }

                self.conf_strict = oct_cfg.get('conf_strict', self.conf_strict)
                self.stable_frames = oct_cfg.get('stable_frames', self.stable_frames)
                self.stable_iou = oct_cfg.get('stable_iou', self.stable_iou)
                self.center_outlier_iqr = oct_cfg.get('center_outlier_iqr', self.center_outlier_iqr)
                self.class_swap_wait = oct_cfg.get('class_swap_wait', self.class_swap_wait)
                self.anchor_settle = oct_cfg.get('anchor_settle', self.anchor_settle)
                self.max_object_yaml_error = oct_cfg.get('max_object_yaml_error', self.max_object_yaml_error)

                self.empty_frames_trigger = oct_cfg.get('empty_frames_trigger', self.empty_frames_trigger)
                self.descend_step = oct_cfg.get('descend_step', self.descend_step)
                self.reanchor_frac = oct_cfg.get('reanchor_frac', self.reanchor_frac)

                self.x_lineup_tolerance = oct_cfg.get('x_lineup_tolerance', self.x_lineup_tolerance)
                self.y_lineup_tolerance = oct_cfg.get('y_lineup_tolerance', self.y_lineup_tolerance)
                self.align_attempts = oct_cfg.get('align_attempts', self.align_attempts)
                self.grab_retries = oct_cfg.get('grab_retries', self.grab_retries)
                self.grip_settle = oct_cfg.get('grip_settle', self.grip_settle)
                self.surface_pause = oct_cfg.get('surface_pause', self.surface_pause)
                self.rise_check_time = oct_cfg.get('rise_check_time', self.rise_check_time)
                self.carry_max_width = oct_cfg.get('carry_max_width', self.carry_max_width)
                self.carry_ignore_region = oct_cfg.get('carry_ignore_region', self.carry_ignore_region)

                self.place_side = oct_cfg.get('place_side', self.place_side)
                self.place_margin = oct_cfg.get('place_margin', self.place_margin)
                self.place_margin_max = oct_cfg.get('place_margin_max', self.place_margin_max)

                self.finale_turn_degrees = oct_cfg.get('finale_turn_degrees', self.finale_turn_degrees)
                self.icon_scan_step = oct_cfg.get('icon_scan_step', self.icon_scan_step)
                self.icon_timeout = oct_cfg.get('icon_timeout', self.icon_timeout)
                self.icon_deg_per_image = oct_cfg.get('icon_deg_per_image', self.icon_deg_per_image)
                self.icon_yaw_sign = oct_cfg.get('icon_yaw_sign', self.icon_yaw_sign)
                self.rotation_step_timeout = oct_cfg.get('rotation_step_timeout', self.rotation_step_timeout)
                self.task_time_budget = oct_cfg.get('task_time_budget', self.task_time_budget)
                self.dvl_grace = oct_cfg.get('dvl_grace', self.dvl_grace)
                self.max_depth_limit = oct_cfg.get('max_depth_limit', self.max_depth_limit)

        except FileNotFoundError:
            self.logger.error(f"{self.name} ERROR: objects.yaml not found, using default octagon values")
        except KeyError:
            self.logger.error(f"{self.name} ERROR: Invalid data format in objects.yaml, using default octagon values")

        self.helper = OctagonHelpers(shared_memory_object, signal_wrapper, weights_path=model_weights,
                                      claw_offset_body=(claw_offset_x, claw_offset_y), camera_rotate_180=camera_rotate_180,
                                      auv_height=auv_height, auv_height_claw_extended=auv_height_claw_extended,
                                      table_top_z=self.table_top_z, item_height=self.item_height,
                                      hover_margin=self.hover_margin, grab_depth_frac=self.grab_depth_frac,
                                      stable_frames=self.stable_frames, stable_iou=self.stable_iou,
                                      conf_strict=self.conf_strict, class_swap_wait=self.class_swap_wait,
                                      center_outlier_iqr=self.center_outlier_iqr,
                                      carry_max_width=self.carry_max_width, carry_ignore_region=self.carry_ignore_region)

        # RUN PROGRESS--------------------------------------------------------------------------------------------------------------
        self.whitelist = list(self.item_class_ids) # classes still worth searching the table for
        self.blacklist = []                        # grab-verified AND released - drives the finale spin count
        self.skipped = []                          # given up on - NOT in the spin count (spins stay honest)
        self.retries_left = {class_id: self.grab_retries for class_id in self.item_class_ids}
        self.placed_count = {bin_id: 0 for bin_id in self.baskets} # the per-bin first-item milestone log
        self.pending_class = None                  # class id believed to be in the claw
        self.pending_bin = None
        self.pending_aim = None                    # last confirmed aim center (normalized)
        self.move_target = None                    # world (x, y) commanded by the current move
        self.aim_attempts = 0
        self.sweeps = 0                            # completed down-up search sweeps (telemetry)
        self.rise_checking = False                 # RISE_VERIFY sub-mode: anchored check in progress
        self.rise_check_started = 0.0
        self.task_start_time = 0.0
        self.wait_time = 0.0
        self.dvl_invalid_since = None

    # HELPERS----------------------------------------------------------------------------------------------------------------------
    def _floor_z(self) -> float:
        """
        The no-scrape floor for translating states. Without the measured AUV
        heights (hardware.yaml FIXME) this collapses to start_z - safe, but
        the sub can never descend toward the table.
        """
        return self.helper.min_safe_z(fallback_z=self.start_z)

    def _budget_spent(self) -> bool:
        return self.task_start_time > 0 and time.time() - self.task_start_time > self.task_time_budget

    def _abort_to_finale(self, reason: str) -> None:
        """
        Bank what we have: surface, face the icon, spin len(blacklist).
        """
        if self.state in FINALE_STATES:
            return
        self.logger.warning(f"{self.name} aborting to finale: {reason} "
                            f"(blacklist={self.blacklist} skipped={self.skipped} whitelist={self.whitelist})")
        self.next_state(States.FINALE_SURFACE)

    def _placement_offset_body(self, marker_detection) -> tuple:
        """
        First item into a bin lands BESIDE the marker (its left/right edge) so
        the marker stays visible for the second visit; the second item can go
        anywhere - center is fine. Offset = marker half-width (meters at the
        table plane) + place_margin, clamped by place_margin_max.
        FIXME: which physical direction "left" maps to - pool-verify, flip
        place_side if the first drop lands on the wrong side.
        """
        if self.placed_count.get(self.pending_bin, 0) > 0:
            return (0.0, 0.0)
        half_width = 0.0
        if marker_detection is not None:
            half_width = self.helper.detection_width_m(marker_detection, self.table_top_z) / 2.0
        offset = min(half_width + self.place_margin, self.place_margin_max)
        sign = -1.0 if self.place_side == "left" else 1.0
        return (sign * offset, 0.0)

    def _fail_grab(self, reason: str) -> None:
        """
        The rise-watch proved (or the claw never held) - retry or skip.
        The class was never blacklisted, so the spin count stays honest.
        """
        self.helper.open_claw()
        label = CLASS_LABELS.get(self.pending_class, self.pending_class)
        self.retries_left[self.pending_class] = self.retries_left.get(self.pending_class, 0) - 1
        if self.retries_left[self.pending_class] >= 0:
            self.logger.warning(f"{self.name} grab FAILED for {label} ({reason}) - retrying ({self.retries_left[self.pending_class]} left)")
            if self.pending_class not in self.whitelist:
                self.whitelist.insert(0, self.pending_class)
            self.pending_class = self.pending_bin = None
            self.next_state(States.TO_TABLE)
        else:
            self.logger.warning(f"{self.name} grab retries exhausted for {label} - skipping it")
            if self.pending_class in self.whitelist:
                self.whitelist.remove(self.pending_class)
            self.skipped.append(self.pending_class)
            self.pending_class = self.pending_bin = None
            if self.whitelist:
                self.next_state(States.TO_TABLE)
            else:
                self._abort_to_finale("no items left after exhausted retries")

    def _search_ladder(self) -> None:
        """
        The descend-scan: after empty_frames_trigger clean-miss frames, one
        anchored ~0.1m step down; at the no-scrape floor, bounce back to
        start_z and sweep again. Runs until the whitelist empties or the
        budget watchdog fires - the cycle's real terminator.
        """
        floor = self._floor_z()
        current_target = self.shared_memory_object.target_z.value
        if current_target + self.descend_step <= floor:
            self.shared_memory_object.target_z.value = current_target + self.descend_step
            self.helper.anchor(self.anchor_settle) # stop/wait/YOLO - the standardized pause
        else:
            self.sweeps += 1
            self.logger.info(f"{self.name} search floor reached (z={floor:.2f}) - bouncing to start_z (sweep {self.sweeps})")
            self.shared_memory_object.target_z.value = self.start_z
        self.helper.gate.reset()

    # LIFECYCLE--------------------------------------------------------------------------------------------------------------------
    def start(self) -> None:
        """
        Start FSM by enabling and starting processes
        """
        super().start()  # call parent start method

        self.task_start_time = time.time()

        # loud early warnings: missing model classes, missing geometry
        try:
            required = set(self.item_class_ids) | set(self.item_to_bin.values())
            missing = self.helper.verify_model_classes(sorted(required))
            if missing:
                self.logger.error(f"{self.name} MODEL MISSING CLASS IDS {missing} - "
                                  f"weights '{self.helper.weights_path}' can't see those items/bins, update the model!")
        except Exception as error:
            self.logger.error(f"{self.name} could not verify model classes: {error}")
        if not self.helper.geometry_ready():
            self.logger.error(f"{self.name} AUV HEIGHTS NOT SET (config/hardware.yaml octagon: auv_height / "
                              f"auv_height_claw_extended) - staying at start_z, grabs are impossible until measured!")

        # set initial state
        self.next_state(States.TO_OCT)

    def next_state(self, next: States) -> None:
        """
        Change to next state
        """
        if not self.active or self.state == next: return # do nothing if not enabled or no state change

        # STATES-----------------------------------------------------------------------------------------------------------------------
        match(next):
            case States.INIT:
                return # initial state

            case States.TO_OCT: # drive to the octagon center at working depth, hold the task heading
                self.shared_memory_object.target_x.value = self.oct_x
                self.shared_memory_object.target_y.value = self.oct_y
                self.shared_memory_object.target_z.value = self.start_z
                self.shared_memory_object.target_yaw.value = self.yaw
                self.wait_time = time.time()

            case States.EXTEND_CLAW: # once on arrival: open the grip and rise so the fixed claw's tines hang fully open
                self.helper.open_claw()
                self.shared_memory_object.target_z.value = max(0.0, self.start_z - self.extend_lift)
                self.wait_time = time.time()

            case States.SEARCH_ITEM: # frame-gated hunt over the table, highest confidence first
                self.helper.gate.reset()
                self.wait_time = time.time()

            case States.APPROACH_ITEM: # ONE absolute move over the item at the current safe depth
                self.shared_memory_object.target_x.value = self.move_target[0]
                self.shared_memory_object.target_y.value = self.move_target[1]
                self.wait_time = time.time()

            case States.REFINE_ALIGN: # anchored re-measure to kill accumulated drift before sinking
                self.helper.anchor(self.anchor_settle)
                self.helper.gate.reset()
                self.wait_time = time.time()

            case States.SINK_GRAB: # the ONLY state allowed below the no-scrape floor: vertical-only sink
                self.shared_memory_object.target_z.value = self.helper.grab_z(fallback_z=self._floor_z())
                self.wait_time = time.time()

            case States.RISE_VERIFY: # surface with the item, watching for it reappearing below
                self.helper.watch_reset()
                self.rise_checking = False
                self.shared_memory_object.target_z.value = 0.0 # surfacing with each item is scored
                self.wait_time = time.time()

            case States.SORT_TO_BIN: # head for this item's basket, marker upright via face_yaw
                basket = self.baskets.get(self.pending_bin, {"x": 0.0, "y": 0.0, "face_yaw": 0.0})
                self.shared_memory_object.target_x.value = basket["x"]
                self.shared_memory_object.target_y.value = basket["y"]
                self.shared_memory_object.target_z.value = self.start_z
                self.shared_memory_object.target_yaw.value = basket["face_yaw"]
                self.helper.watch_reset()
                self.wait_time = time.time()

            case States.SEARCH_BIN: # frame-gated hunt for the basket marker
                self.helper.gate.reset()
                self.aim_attempts = 0
                self.wait_time = time.time()

            case States.ALIGN_BIN: # anchored refine over the (offset) release point
                self.helper.anchor(self.anchor_settle)
                self.helper.gate.reset()
                self.wait_time = time.time()

            case States.RELEASE: # let go - this is what earns the blacklist entry
                self.helper.open_claw()
                time.sleep(self.grip_settle)
                self.blacklist.append(self.pending_class)
                if self.pending_bin in self.placed_count:
                    self.placed_count[self.pending_bin] += 1
                self.logger.info(f"{self.name} released {CLASS_LABELS.get(self.pending_class, self.pending_class)} "
                                 f"at bin {self.pending_bin} (blacklist={self.blacklist})")
                self.pending_class = self.pending_bin = None

            case States.TO_TABLE: # back over the table for the next item
                self.shared_memory_object.target_x.value = self.oct_x
                self.shared_memory_object.target_y.value = self.oct_y
                self.shared_memory_object.target_z.value = self.start_z
                self.shared_memory_object.target_yaw.value = self.yaw
                self.wait_time = time.time()

            case States.FINALE_SURFACE: # the finale is always attempted
                self.shared_memory_object.target_z.value = 0.0
                self.wait_time = time.time()

            case States.FACE_ICON: # rotate until an icon for the count is seen, stop on it
                self.helper.start_icon_scan()
                self.wait_time = time.time()

            case States.SPIN: # the very last scored action: 360 per blacklisted item
                self.helper.start_rotation(len(self.blacklist), self.finale_turn_degrees)

            case States.COMPLETE:
                self.logger.info(f"{self.name} DONE: placed={self.blacklist} skipped={self.skipped} sweeps={self.sweeps}")
                self.suspend() # finish octagon mode, ready for next mode

            case States.FAIL: # invalid-state landing only - normal failures go through the finale
                self.logger.warning(f"{self.name} FAILED (placed={self.blacklist} skipped={self.skipped})")
                self.suspend()

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
        self.display(0, 0, 255) # update display

        # GLOBAL WATCHDOGS-------------------------------------------------------------------------------------------------------
        # hard depth ceiling, and the anti-scrape floor everywhere except the vertical sink
        if self.shared_memory_object.target_z.value > self.max_depth_limit:
            self.shared_memory_object.target_z.value = self.max_depth_limit
        if self.state not in SINK_EXEMPT_STATES and self.shared_memory_object.target_z.value > self._floor_z():
            self.shared_memory_object.target_z.value = self._floor_z()
        # out of budget -> bank the finale points with whatever the blacklist holds
        if self.state not in FINALE_STATES and self._budget_spent():
            self._abort_to_finale("task time budget spent")
            return
        # navigating without DVL is drift - hold, then go bank the finale
        if self.state not in FINALE_STATES and hasattr(self.shared_memory_object, "dvl_velocity_valid"):
            if not self.shared_memory_object.dvl_velocity_valid.value:
                if self.dvl_invalid_since is None:
                    self.dvl_invalid_since = time.time()
                    stop_vehicle_motion(self.shared_memory_object)
                elif time.time() - self.dvl_invalid_since > self.dvl_grace:
                    self._abort_to_finale("DVL invalid too long")
                    return
            else:
                self.dvl_invalid_since = None

        # TRANSITIONS------------------------------------------------------------------------------------------------------
        match(self.state):
            case States.INIT:
                return

            case States.TO_OCT: # transition: TO_OCT -> EXTEND_CLAW
                if self.reached_xyz(self.oct_x, self.oct_y, self.start_z) or time.time() - self.wait_time > self.timeout:
                    self.next_state(States.EXTEND_CLAW)

            case States.EXTEND_CLAW: # transition: EXTEND_CLAW -> SEARCH_ITEM (once, on arrival)
                if self.shared_memory_object.dvl_z.value <= self.start_z - self.extend_lift + self.z_buffer or time.time() - self.wait_time > self.timeout:
                    self.helper.anchor(self.anchor_settle) # let the tines settle open
                    self.shared_memory_object.target_z.value = self.start_z
                    self.next_state(States.SEARCH_ITEM)

                time.sleep(self.t_loop)

            case States.SEARCH_ITEM: # transition: confirmed -> APPROACH_ITEM; empty streak -> descend ladder
                if not self.whitelist:
                    self._abort_to_finale("whitelist complete")
                    return
                detections = self.helper.get_target_detections(classes=list(self.whitelist))
                accept = self.helper.order_by_conf(detections, self.whitelist)
                verdict = self.helper.gate.feed(detections, accept)

                if verdict["confirmed"]:
                    move_target = self.helper.compute_claw_target(verdict["aim_center"], self.helper.item_plane_z())
                    if self.helper.validate_against_assumed(self.helper.target_world, (self.oct_x, self.oct_y), self.max_object_yaml_error):
                        self.pending_class = verdict["class_id"]
                        self.pending_bin = self.item_to_bin.get(self.pending_class)
                        self.pending_aim = verdict["aim_center"]
                        self.move_target = move_target
                        self.aim_attempts = 0
                        self.logger.info(f"{self.name} item {CLASS_LABELS.get(self.pending_class, self.pending_class)} confirmed "
                                         f"(highest conf, outliers dropped: {verdict['n_outliers']}) - approaching")
                        self.next_state(States.APPROACH_ITEM)
                    else:
                        self.logger.warning(f"{self.name} confirmed item rejected - world estimate too far from the octagon, re-searching")
                        self.helper.gate.reset()
                elif verdict["empty_streak"] >= self.empty_frames_trigger:
                    self._search_ladder()

                time.sleep(self.t_loop)

            case States.APPROACH_ITEM: # transition: arrival or half-screen box -> REFINE_ALIGN
                arrived = self.reached_xy(self.move_target[0], self.move_target[1])
                box_big = False
                detections = self.helper.get_target_detections(classes=[self.pending_class])
                for det in detections:
                    if det[1] == self.pending_class and max(det[6], det[7]) >= self.reanchor_frac:
                        box_big = True # the box fills half the frame - drift has had time to build, re-anchor
                        break
                if arrived or box_big or time.time() - self.wait_time > self.timeout:
                    self.next_state(States.REFINE_ALIGN)

                time.sleep(self.t_loop)

            case States.REFINE_ALIGN: # transition: within tolerance -> SINK_GRAB; drift -> another move; lost -> SEARCH_ITEM
                detections = self.helper.get_target_detections(classes=[self.pending_class])
                verdict = self.helper.gate.feed(detections, [self.pending_class])

                if verdict["confirmed"]:
                    self.pending_aim = verdict["aim_center"]
                    x_err, y_err = self.helper.claw_error_m(verdict["aim_center"], self.helper.item_plane_z())
                    if abs(x_err) <= self.x_lineup_tolerance and abs(y_err) <= self.y_lineup_tolerance:
                        self.next_state(States.SINK_GRAB)
                    else:
                        self.aim_attempts += 1
                        if self.aim_attempts > self.align_attempts:
                            self.logger.warning(f"{self.name} refine cap hit (err {x_err:.2f}, {y_err:.2f}m) - sinking anyway, the rise-check catches a miss")
                            self.next_state(States.SINK_GRAB)
                        else:
                            self.move_target = self.helper.compute_claw_target(verdict["aim_center"], self.helper.item_plane_z())
                            self.next_state(States.APPROACH_ITEM)
                elif time.time() - self.wait_time > self.timeout:
                    self.logger.warning(f"{self.name} item lost during refine - back to searching")
                    self.pending_class = self.pending_bin = None
                    self.next_state(States.SEARCH_ITEM)

                time.sleep(self.t_loop)

            case States.SINK_GRAB: # transition: at grab depth -> grip -> RISE_VERIFY
                if abs(self.shared_memory_object.dvl_z.value - self.shared_memory_object.target_z.value) <= self.z_buffer or time.time() - self.wait_time > self.timeout:
                    self.helper.close_claw()
                    time.sleep(self.grip_settle)
                    self.next_state(States.RISE_VERIFY)

                time.sleep(self.t_loop)

            case States.RISE_VERIFY: # transition: surfaced clean -> SORT_TO_BIN; stable sighting below -> failed grab
                detections = self.helper.get_target_detections(classes=[self.pending_class])
                watch = self.helper.watch_feed(detections, self.pending_class)

                if watch["stable"]:
                    self._fail_grab("item seen stable below while rising")
                    return
                if watch["sighted"] and not self.rise_checking:
                    # single sighting: anchor the ascent (stop, settle) and give the gate its 4 frames
                    self.rise_checking = True
                    self.rise_check_started = time.time()
                    self.helper.anchor(self.anchor_settle)
                elif self.rise_checking and time.time() - self.rise_check_started > self.rise_check_time:
                    # sightings never stabilized - resume the ascent
                    self.rise_checking = False
                    self.helper.watch_reset()
                    self.shared_memory_object.target_z.value = 0.0

                if not self.rise_checking and self.shared_memory_object.dvl_z.value <= self.z_buffer:
                    time.sleep(self.surface_pause) # scored: at the surface holding the item
                    if self.pending_class in self.whitelist:
                        self.whitelist.remove(self.pending_class) # grab verified - stop searching for it
                    self.logger.info(f"{self.name} grab VERIFIED for {CLASS_LABELS.get(self.pending_class, self.pending_class)} - sorting to bin {self.pending_bin}")
                    self.next_state(States.SORT_TO_BIN)

                time.sleep(self.t_loop)

            case States.SORT_TO_BIN: # transition: at the basket -> SEARCH_BIN; carry watch armed the whole way
                detections = self.helper.get_target_detections(classes=[self.pending_class])
                watch = self.helper.watch_feed(detections, self.pending_class)
                if watch["stable"]:
                    world = self.helper.watch_world_position()
                    near_table = world is not None and self.helper.validate_against_assumed(world, (self.oct_x, self.oct_y), self.max_object_yaml_error)
                    if near_table and self.retries_left.get(self.pending_class, 0) > 0:
                        self._fail_grab("carry watch: item back on the table")
                    else:
                        label = CLASS_LABELS.get(self.pending_class, self.pending_class)
                        self.logger.warning(f"{self.name} carry watch: {label} lost mid-carry - writing it off")
                        if self.pending_class in self.whitelist:
                            self.whitelist.remove(self.pending_class)
                        self.skipped.append(self.pending_class)
                        self.pending_class = self.pending_bin = None
                        if self.whitelist:
                            self.next_state(States.TO_TABLE)
                        else:
                            self._abort_to_finale("no items left after a lost carry")
                    return

                basket = self.baskets.get(self.pending_bin, {"x": 0.0, "y": 0.0})
                if self.reached_xyz(basket["x"], basket["y"], self.start_z) or time.time() - self.wait_time > self.timeout:
                    self.next_state(States.SEARCH_BIN)

                time.sleep(self.t_loop)

            case States.SEARCH_BIN: # transition: marker confirmed -> ALIGN_BIN; empty streak -> descend ladder
                detections = self.helper.get_target_detections(classes=[self.pending_bin, self.pending_class])
                verdict = self.helper.gate.feed(detections, [self.pending_bin])
                watch = self.helper.watch_feed(detections, self.pending_class)
                if watch["stable"]:
                    # dropped it near the bins - not recoverable from here, write it off
                    label = CLASS_LABELS.get(self.pending_class, self.pending_class)
                    self.logger.warning(f"{self.name} carry watch: {label} dropped near the bins - writing it off")
                    if self.pending_class in self.whitelist:
                        self.whitelist.remove(self.pending_class)
                    self.skipped.append(self.pending_class)
                    self.pending_class = self.pending_bin = None
                    self.next_state(States.TO_TABLE if self.whitelist else States.FINALE_SURFACE)
                    return

                if verdict["confirmed"]:
                    self.pending_aim = verdict["aim_center"]
                    offset = self._placement_offset_body(self.helper.gate.window[-1] if self.helper.gate.window else None)
                    self.move_target = self.helper.compute_claw_target(verdict["aim_center"], self.table_top_z, offset)
                    self.shared_memory_object.target_x.value = self.move_target[0]
                    self.shared_memory_object.target_y.value = self.move_target[1]
                    self.next_state(States.ALIGN_BIN)
                elif verdict["empty_streak"] >= self.empty_frames_trigger:
                    self._search_ladder()

                time.sleep(self.t_loop)

            case States.ALIGN_BIN: # transition: over the (offset) release point -> RELEASE
                detections = self.helper.get_target_detections(classes=[self.pending_bin])
                verdict = self.helper.gate.feed(detections, [self.pending_bin])

                if verdict["confirmed"]:
                    offset = self._placement_offset_body(self.helper.gate.window[-1] if self.helper.gate.window else None)
                    x_err, y_err = self.helper.claw_error_m(verdict["aim_center"], self.table_top_z, offset)
                    if abs(x_err) <= self.x_lineup_tolerance and abs(y_err) <= self.y_lineup_tolerance:
                        self.next_state(States.RELEASE)
                    else:
                        self.aim_attempts += 1
                        if self.aim_attempts > self.align_attempts:
                            self.logger.warning(f"{self.name} bin refine cap hit - releasing from here, close beats never")
                            self.next_state(States.RELEASE)
                        else:
                            self.move_target = self.helper.compute_claw_target(verdict["aim_center"], self.table_top_z, offset)
                            self.shared_memory_object.target_x.value = self.move_target[0]
                            self.shared_memory_object.target_y.value = self.move_target[1]
                            self.helper.anchor(self.anchor_settle)
                            self.helper.gate.reset()
                elif time.time() - self.wait_time > self.timeout:
                    self.logger.warning(f"{self.name} marker lost during bin align - releasing at the basket coords, close beats never")
                    self.next_state(States.RELEASE)

                time.sleep(self.t_loop)

            case States.RELEASE: # transition: RELEASE -> TO_TABLE (more items) or FINALE_SURFACE
                if self.whitelist:
                    self.next_state(States.TO_TABLE)
                else:
                    self.next_state(States.FINALE_SURFACE)

            case States.TO_TABLE: # transition: TO_TABLE -> SEARCH_ITEM
                if self.reached_xyz(self.oct_x, self.oct_y, self.start_z) or time.time() - self.wait_time > self.timeout:
                    self.next_state(States.SEARCH_ITEM)

                time.sleep(self.t_loop)

            case States.FINALE_SURFACE: # transition: surfaced -> FACE_ICON
                if self.shared_memory_object.dvl_z.value <= self.z_buffer or time.time() - self.wait_time > self.timeout:
                    self.next_state(States.FACE_ICON)

                time.sleep(self.t_loop)

            case States.FACE_ICON: # transition: icon centered (or scan gave up) -> SPIN
                icon_ids = self.helper.get_target_icon_ids(len(self.blacklist))
                status = self.helper.face_icon_scan_step(icon_ids, self.icon_scan_step, deg_per_image=self.icon_deg_per_image, yaw_sign=self.icon_yaw_sign)
                if status == "centered":
                    self.logger.info(f"{self.name} facing icon (vision) - ids {icon_ids}")
                    self.next_state(States.SPIN)
                elif status in ("exhausted", "no_camera") or time.time() - self.wait_time > self.icon_timeout:
                    self.logger.warning(f"{self.name} icon scan {status} - falling back to heading table")
                    self.helper.face_target_icon(icon_ids)
                    self.next_state(States.SPIN)

                time.sleep(self.t_loop)

            case States.SPIN: # transition: all turns done -> COMPLETE
                if self.helper.advance_rotation_step(step_timeout=self.rotation_step_timeout):
                    self.next_state(States.COMPLETE)

                time.sleep(self.t_loop)

            case States.COMPLETE:
                return

            case States.FAIL:
                return

            case _: # do nothing if invalid state
                self.logger.error(f"{self.name} INVALID STATE {self.state}")
