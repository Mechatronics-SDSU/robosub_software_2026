from fsm.fsm import FSM_Template
from utils.socket_send import set_screen
from enum import Enum
import os, yaml, time

"""
    Dropper FSM for RoboSub 2026.

    General idea:
    1. Drive to an approximate basket/bin location using map/object coordinates.
    2. Use the downward-facing camera to find the basket/bin.
    3. Center the robot over the target using camera error.
    4. Descend to the configured drop depth while continuing to center.
    5. Spin the brushless dropper motor to release the metal ball/marker.
    6. Optionally repeat for a second ball, then exit the mode.

    This file is intentionally written with placeholder comments for the future
    camera interface and dropper interface. The FSM flow should be usable before
    those interfaces are finished.
"""


class States(Enum):
    """
    Enumeration for Dropper FSM states.
    """
    INIT        = "INIT"
    TO_TARGET   = "TO_TARGET"
    SEARCH      = "SEARCH"
    CENTER      = "CENTER"
    DESCEND     = "DESCEND"
    DROP        = "DROP"
    REARM       = "REARM"
    EXIT        = "EXIT"

    def __str__(self) -> str:
        return self.value


class Dropper_FSM(FSM_Template):
    """
    FSM for dropping metal balls/markers into a RoboSub 2026 basket/bin target.

    This assumes the robot already knows an approximate target location from
    objects.yaml, then uses the downward-facing camera for final alignment.
    The real camera/dropper calls should be added where the placeholder comments
    are marked.
    """

    def __init__(self, shared_memory_object, run_list: list):
        """
        Dropper FSM constructor.
        """
        super().__init__(shared_memory_object, run_list)
        self.name: str = "DROPPER"
        self.state: States = States.INIT

        # TARGET / CONFIG VALUES ----------------------------------------------------------------------
        # These defaults let the FSM load even if objects.yaml is missing fields.
        self.target_x = 0.0              # approximate field/global x position of basket/bin
        self.target_y = 0.0              # approximate field/global y position of basket/bin
        self.travel_depth = 0.0          # depth used while traveling toward the target
        self.drop_depth = 0.0            # depth used during the actual drop
        self.x_buffer = 0.0              # acceptable field/global x error for TO_TARGET
        self.y_buffer = 0.0              # acceptable field/global y error for TO_TARGET
        self.z_buffer = 0.0              # acceptable depth error for DESCEND

        # Vision alignment tuning.
        # camera_center_x/y are normalized image coordinates. 0.5 means center of image.
        self.camera_center_x = 0.5
        self.camera_center_y = 0.5
        self.center_buffer = 0.05        # normalized image error allowed before dropping
        self.min_confidence = 0.70       # minimum detection confidence to trust the target
        self.stable_frames_required = 8  # frames in a row centered before descending/dropping
        self.search_timeout = 8.0        # seconds before giving up if basket/bin is not found

        # Dropper motor tuning.
        # For a brushless motor/ESC, this will usually be power + time based.
        self.drop_motor_power = 0.35     # placeholder motor power, replace after testing
        self.drop_spin_time = 0.50       # seconds to spin open/release one ball
        self.rearm_time = 0.25           # optional pause after each drop
        self.num_balls = 1               # set to 2 if this mission should drop two balls

        # Runtime state.
        self.search_start_time = 0.0
        self.drop_start_time = 0.0
        self.rearm_start_time = 0.0
        self.centered_frames = 0
        self.balls_dropped = 0

        try:
            with open(os.path.expanduser("~/robosub_software_2026/objects.yaml"), "r") as file:
                data = yaml.safe_load(file)
                course = data["course"]

                # Expected objects.yaml shape:
                #
                # course: TRANSDEC
                # TRANSDEC:
                #   dropper:
                #     x: 0
                #     y: 0
                #     travel_depth: 1.0
                #     drop_depth: 1.4
                #     x_buf: 0.2
                #     y_buf: 0.2
                #     z_buf: 0.1
                #     center_buf: 0.05
                #     min_confidence: 0.70
                #     stable_frames: 8
                #     search_timeout: 8.0
                #     drop_motor_power: 0.35
                #     drop_spin_time: 0.50
                #     rearm_time: 0.25
                #     num_balls: 1
                dropper_data = data[course]["dropper"]

                self.target_x = dropper_data["x"]
                self.target_y = dropper_data["y"]
                self.travel_depth = dropper_data["travel_depth"]
                self.drop_depth = dropper_data["drop_depth"]
                self.x_buffer = dropper_data["x_buf"]
                self.y_buffer = dropper_data["y_buf"]
                self.z_buffer = dropper_data["z_buf"]

                self.center_buffer = dropper_data.get("center_buf", self.center_buffer)
                self.min_confidence = dropper_data.get("min_confidence", self.min_confidence)
                self.stable_frames_required = dropper_data.get("stable_frames", self.stable_frames_required)
                self.search_timeout = dropper_data.get("search_timeout", self.search_timeout)

                self.drop_motor_power = dropper_data.get("drop_motor_power", self.drop_motor_power)
                self.drop_spin_time = dropper_data.get("drop_spin_time", self.drop_spin_time)
                self.rearm_time = dropper_data.get("rearm_time", self.rearm_time)
                self.num_balls = dropper_data.get("num_balls", self.num_balls)

        except (FileNotFoundError, KeyError, TypeError):
            print("ERROR: Invalid or missing dropper data in objects.yaml, using default values")

    def start(self) -> None:
        """
        Start FSM by enabling and starting processes.
        """
        super().start()
        self.balls_dropped = 0
        self.centered_frames = 0
        self.next_state(States.TO_TARGET)

    def next_state(self, next: States) -> None:
        """
        Change to next state and perform one-time setup for that state.
        """
        if not self.active or self.state == next:
            return

        match(next):
            case States.INIT:
                return

            case States.TO_TARGET:
                # Drive to the approximate basket/bin position from objects.yaml.
                # This gets the target somewhere inside the downward camera view.
                self.shared_memory_object.target_x.value = self.target_x
                self.shared_memory_object.target_y.value = self.target_y
                self.shared_memory_object.target_z.value = self.travel_depth

            case States.SEARCH:
                # Begin looking for the basket/bin with the downward-facing camera.
                # TODO: camera interface should start/enable the correct model here if needed.
                self.search_start_time = time.time()
                self.centered_frames = 0

            case States.CENTER:
                # We have a detection and are now trying to place it at image center.
                self.centered_frames = 0

            case States.DESCEND:
                # Move to drop depth while still using the camera to stay centered.
                self.shared_memory_object.target_z.value = self.drop_depth

            case States.DROP:
                # Start the brushless motor release.
                self.drop_start_time = time.time()
                self._start_dropper_motor()

            case States.REARM:
                # Optional delay/state after one ball drops before trying another drop.
                self.rearm_start_time = time.time()
                self._stop_dropper_motor()

            case States.EXIT:
                # Make sure the dropper motor is off and end this mission mode.
                self._stop_dropper_motor()
                self.suspend()

            case _:
                print(f"{self.name} INVALID NEXT STATE {next}")
                return

        self.state = next
        print(f"{self.name}:{self.state}")

    def loop(self) -> None:
        """
        Loop function. This should be called repeatedly by the main FSM runner.
        """
        if not self.active:
            return

        self.display(0, 255, 0)

        match(self.state):
            case States.INIT | States.EXIT:
                return

            case States.TO_TARGET:
                # Once we are near the approximate target position, switch to camera alignment.
                if self.reached_xy(self.target_x, self.target_y):
                    self.next_state(States.SEARCH)

            case States.SEARCH:
                detection = self._get_basket_detection()

                if self._valid_detection(detection):
                    self.next_state(States.CENTER)
                    return

                # TODO: Add a search pattern if the basket/bin is not visible.
                # Example ideas:
                #   - slowly yaw in place if the downward camera view is partly blocked
                #   - small x/y lawnmower pattern around the expected location
                #   - rise slightly if too close to the target to see the full basket/bin

                if time.time() - self.search_start_time > self.search_timeout:
                    print(f"{self.name}: target not found, exiting dropper mode")
                    self.next_state(States.EXIT)

            case States.CENTER:
                detection = self._get_basket_detection()

                if not self._valid_detection(detection):
                    # Lost the target, go back to search instead of dropping blindly.
                    self.next_state(States.SEARCH)
                    return

                # Use camera error to command small x/y corrections.
                self._track_target_with_camera(detection)

                if self._target_is_centered(detection):
                    self.centered_frames += 1
                else:
                    self.centered_frames = 0

                if self.centered_frames >= self.stable_frames_required:
                    self.next_state(States.DESCEND)

            case States.DESCEND:
                detection = self._get_basket_detection()

                if self._valid_detection(detection):
                    # Keep correcting x/y while descending so current does not drift us off target.
                    self._track_target_with_camera(detection)
                else:
                    # Do not drop if we cannot see the basket/bin anymore.
                    self.next_state(States.SEARCH)
                    return

                if self._at_drop_depth() and self._target_is_centered(detection):
                    self.next_state(States.DROP)

            case States.DROP:
                # For a brushless motor, the simplest release is usually:
                #   run motor at drop_motor_power for drop_spin_time seconds, then stop.
                # If the mechanism later has an encoder or limit switch, replace this
                # timer with real feedback.
                if time.time() - self.drop_start_time >= self.drop_spin_time:
                    self._stop_dropper_motor()
                    self.balls_dropped += 1

                    if self.balls_dropped >= self.num_balls:
                        self.next_state(States.EXIT)
                    else:
                        self.next_state(States.REARM)

            case States.REARM:
                # Give the mechanism time to settle or rotate to the next ball.
                # TODO: replace timer with dropper_interface.ready() if hardware supports it.
                if time.time() - self.rearm_start_time >= self.rearm_time:
                    self.next_state(States.CENTER)

            case _:
                print(f"{self.name} INVALID STATE {self.state}")
                return

    # CAMERA PLACEHOLDERS -----------------------------------------------------------------------------

    def _get_basket_detection(self):
        """
        Read the downward-facing camera target detection.

        TODO: Replace this with the real camera interface.

        Expected detection shape:
            {
                "seen": True,
                "x": 0.50,          # normalized center x of basket/bin in image, 0 left to 1 right
                "y": 0.50,          # normalized center y of basket/bin in image, 0 bottom to 1 top
                "confidence": 0.90
            }

        Possible real calls later:
            detection = downward_camera.get_detection("basket")
            detection = vision_interface.get_object("dropper_basket")
            detection = self.shared_memory_object.down_cam_target.value
        """
        return None

    def _valid_detection(self, detection) -> bool:
        """
        Check if the camera detection is good enough to trust.
        """
        if detection is None:
            return False

        return (
            detection.get("seen", False)
            and detection.get("confidence", 0.0) >= self.min_confidence
            and "x" in detection
            and "y" in detection
        )

    def _target_is_centered(self, detection) -> bool:
        """
        Return True when the basket/bin center is close enough to image center.
        """
        x_error = detection["x"] - self.camera_center_x
        y_error = detection["y"] - self.camera_center_y

        return abs(x_error) <= self.center_buffer and abs(y_error) <= self.center_buffer

    def _track_target_with_camera(self, detection) -> None:
        """
        Convert image error into small movement commands.

        TODO: Replace this with the real movement interface.

        Important:
            The sign of x_error/y_error depends on how the downward camera is mounted.
            Test this in the pool before trusting the direction.
        """
        x_error = detection["x"] - self.camera_center_x
        y_error = detection["y"] - self.camera_center_y

        # Placeholder control logic:
        #   - x_error > 0 means target appears right of center
        #   - y_error > 0 means target appears above center
        #
        # Possible implementation options:
        #   1. Write x/y velocity commands into shared memory.
        #   2. Convert normalized image error into local x/y offsets using camera FOV and depth.
        #   3. Call a vision PID controller that owns the translation math.
        #
        # Example pseudocode:
        #   correction_x = camera_pid_x.update(x_error)
        #   correction_y = camera_pid_y.update(y_error)
        #   movement_interface.set_local_xy_velocity(correction_x, correction_y)
        #
        # Current skeleton does not command motion because the real interface is not defined yet.
        _ = x_error
        _ = y_error

    # DROPPER PLACEHOLDERS ----------------------------------------------------------------------------

    def _start_dropper_motor(self) -> None:
        """
        Start spinning the brushless motor to release one ball/marker.

        TODO: Replace this with the real dropper interface.
        """
        # Example pseudocode:
        #   dropper_interface.spin(power=self.drop_motor_power)
        #   self.shared_memory_object.dropper_motor_power.value = self.drop_motor_power
        #   self.shared_memory_object.dropper_command.value = "DROP"
        pass

    def _stop_dropper_motor(self) -> None:
        """
        Stop the brushless dropper motor.

        TODO: Replace this with the real dropper interface.
        """
        # Example pseudocode:
        #   dropper_interface.stop()
        #   self.shared_memory_object.dropper_motor_power.value = 0.0
        #   self.shared_memory_object.dropper_command.value = "STOP"
        pass

    # POSITION HELPERS --------------------------------------------------------------------------------

    def _at_drop_depth(self) -> bool:
        """
        Check if the robot is at the configured drop depth.
        """
        return abs(self.shared_memory_object.dvl_z.value - self.drop_depth) <= self.z_buffer
