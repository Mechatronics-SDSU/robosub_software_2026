from fsm.fsm import FSM_Template
from utils.socket_send import set_screen
from enum import Enum
import os, yaml, time

"""
    Grabber FSM for RoboSub 2026.

    General idea:
    1. Drive to an approximate item/table location using map/object coordinates.
    2. Use the downward-facing camera to find the target item.
    3. Center the robot/claw over the item using camera error.
    4. Descend to the configured grab depth while continuing to center.
    5. Close the claw to grab the item.
    6. Verify the item was grabbed using future claw feedback and/or vision.
    7. Lift to a safe carry depth and hold the item while the next FSM runs.

    This file is intentionally written with placeholder comments for the future
    camera interface and grabber/claw interface. The FSM flow should be usable
    before those interfaces are finished.
"""


class States(Enum):
    """
    Enumeration for Grabber FSM states.
    """
    INIT        = "INIT"
    TO_TABLE    = "TO_TABLE"
    SEARCH      = "SEARCH"
    CENTER      = "CENTER"
    DESCEND     = "DESCEND"
    GRAB        = "GRAB"
    VERIFY      = "VERIFY"
    LIFT        = "LIFT"
    HOLD        = "HOLD"
    EXIT        = "EXIT"

    def __str__(self) -> str:
        return self.value


class Grabber_FSM(FSM_Template):
    """
    FSM for picking up and holding a RoboSub 2026 Resupply item with a claw.

    This assumes the robot already knows an approximate table/item location from
    objects.yaml, then uses the downward-facing camera for final alignment.
    The real camera/grabber calls should be added where the placeholder comments
    are marked.
    """

    def __init__(self, shared_memory_object, run_list: list):
        """
        Grabber FSM constructor.
        """
        super().__init__(shared_memory_object, run_list)
        self.name: str = "GRABBER"
        self.state: States = States.INIT

        # TARGET / CONFIG VALUES ----------------------------------------------------------------------
        # These defaults let the FSM load even if objects.yaml is missing fields.
        self.target_x = 0.0              # approximate field/global x position of table/item
        self.target_y = 0.0              # approximate field/global y position of table/item
        self.travel_depth = 0.0          # depth used while traveling toward the table/item
        self.grab_depth = 0.0            # depth where the claw should close around the item
        self.carry_depth = 0.0           # safer depth after grabbing the item
        self.x_buffer = 0.0              # acceptable field/global x error for TO_TABLE
        self.y_buffer = 0.0              # acceptable field/global y error for TO_TABLE
        self.z_buffer = 0.0              # acceptable depth error for DESCEND/LIFT

        # Vision alignment tuning.
        # camera_center_x/y are normalized image coordinates. 0.5 means center of image.
        self.camera_center_x = 0.5
        self.camera_center_y = 0.5
        self.center_buffer = 0.05        # normalized image error allowed before descending/grabbing
        self.min_confidence = 0.70       # minimum detection confidence to trust the item
        self.stable_frames_required = 8  # frames in a row centered before descending/grabbing
        self.search_timeout = 8.0        # seconds before giving up if item is not found

        # Claw timing / tuning.
        # These are time-based because the claw hardware feedback is not defined yet.
        self.open_time = 0.50            # seconds to wait after opening claw
        self.close_time = 0.75           # seconds to wait after closing claw
        self.verify_timeout = 2.0        # seconds to wait for pickup verification
        self.hold_after_pickup = True    # True means FSM ends with claw closed and item held

        # Runtime state.
        self.search_start_time = 0.0
        self.grab_start_time = 0.0
        self.verify_start_time = 0.0
        self.centered_frames = 0
        self.has_item = False

        try:
            with open(os.path.expanduser("~/robosub_software_2026/objects.yaml"), "r") as file:
                data = yaml.safe_load(file)
                course = data["course"]

                # Expected objects.yaml shape:
                #
                # course: TRANSDEC
                # TRANSDEC:
                #   grabber:
                #     x: 0
                #     y: 0
                #     travel_depth: 1.0
                #     grab_depth: 1.6
                #     carry_depth: 1.0
                #     x_buf: 0.2
                #     y_buf: 0.2
                #     z_buf: 0.1
                #     center_buf: 0.05
                #     min_confidence: 0.70
                #     stable_frames: 8
                #     search_timeout: 8.0
                #     open_time: 0.50
                #     close_time: 0.75
                #     verify_timeout: 2.0
                grabber_data = data[course]["grabber"]

                self.target_x = grabber_data["x"]
                self.target_y = grabber_data["y"]
                self.travel_depth = grabber_data["travel_depth"]
                self.grab_depth = grabber_data["grab_depth"]
                self.carry_depth = grabber_data["carry_depth"]
                self.x_buffer = grabber_data["x_buf"]
                self.y_buffer = grabber_data["y_buf"]
                self.z_buffer = grabber_data["z_buf"]

                self.center_buffer = grabber_data.get("center_buf", self.center_buffer)
                self.min_confidence = grabber_data.get("min_confidence", self.min_confidence)
                self.stable_frames_required = grabber_data.get("stable_frames", self.stable_frames_required)
                self.search_timeout = grabber_data.get("search_timeout", self.search_timeout)

                self.open_time = grabber_data.get("open_time", self.open_time)
                self.close_time = grabber_data.get("close_time", self.close_time)
                self.verify_timeout = grabber_data.get("verify_timeout", self.verify_timeout)
                self.hold_after_pickup = grabber_data.get("hold_after_pickup", self.hold_after_pickup)

        except (FileNotFoundError, KeyError, TypeError):
            print("ERROR: Invalid or missing grabber data in objects.yaml, using default values")

    def start(self) -> None:
        """
        Start FSM by enabling and starting processes.
        """
        super().start()
        self.centered_frames = 0
        self.has_item = False

        # Start with the claw open so the robot is ready to descend around the item.
        # TODO: call the real grabber interface here if the claw should open immediately.
        self._open_claw()

        self.next_state(States.TO_TABLE)

    def next_state(self, next: States) -> None:
        """
        Change to next state and perform one-time setup for that state.
        """
        if not self.active or self.state == next:
            return

        match(next):
            case States.INIT:
                return

            case States.TO_TABLE:
                # Drive to the approximate table/item position from objects.yaml.
                # This gets the item somewhere inside the downward camera view.
                self.shared_memory_object.target_x.value = self.target_x
                self.shared_memory_object.target_y.value = self.target_y
                self.shared_memory_object.target_z.value = self.travel_depth

            case States.SEARCH:
                # Begin looking for the target item with the downward-facing camera.
                # TODO: camera interface should start/enable the correct model here if needed.
                self.search_start_time = time.time()
                self.centered_frames = 0

            case States.CENTER:
                # We have a detection and are now trying to place it at image center.
                self.centered_frames = 0

            case States.DESCEND:
                # Move to grab depth while still using the camera to stay centered.
                self.shared_memory_object.target_z.value = self.grab_depth

            case States.GRAB:
                # Stop small alignment commands before closing so the claw does not drag the item.
                # TODO: call movement interface to zero local x/y velocity here if needed.
                self.grab_start_time = time.time()
                self._close_claw()

            case States.VERIFY:
                # Give the claw/vision system time to confirm the item is actually captured.
                self.verify_start_time = time.time()

            case States.LIFT:
                # Lift away from the table while keeping the claw closed.
                self.shared_memory_object.target_z.value = self.carry_depth

            case States.HOLD:
                # The claw should stay closed. The next mission FSM can take over motion.
                self.has_item = True

                # TODO: optionally write a shared-memory flag so other FSMs know an item is attached.
                # Example pseudocode:
                #   self.shared_memory_object.grabber_has_item.value = True

                if not self.hold_after_pickup:
                    self.next_state(States.EXIT)
                    return

            case States.EXIT:
                # Do NOT open the claw here if the goal is to keep holding the item.
                # Only stop actuator motion. The claw remains in its current position.
                self._stop_claw()
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

        self.display(255, 128, 0)

        match(self.state):
            case States.INIT | States.EXIT:
                return

            case States.TO_TABLE:
                # Once we are near the approximate table/item position, switch to camera alignment.
                if self.reached_xy(self.target_x, self.target_y):
                    self.next_state(States.SEARCH)

            case States.SEARCH:
                detection = self._get_item_detection()

                if self._valid_detection(detection):
                    self.next_state(States.CENTER)
                    return

                # TODO: Add a search pattern if the item is not visible.
                # Example ideas:
                #   - small x/y lawnmower pattern around the expected table location
                #   - rise slightly if too close to see the full item
                #   - use table detection first, then item detection inside the table area

                if time.time() - self.search_start_time > self.search_timeout:
                    print(f"{self.name}: item not found, exiting grabber mode")
                    self.next_state(States.EXIT)

            case States.CENTER:
                detection = self._get_item_detection()

                if not self._valid_detection(detection):
                    # Lost the target, go back to search instead of grabbing blindly.
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
                detection = self._get_item_detection()

                if self._valid_detection(detection):
                    # Keep correcting x/y while descending so current does not drift us off target.
                    self._track_target_with_camera(detection)
                else:
                    # Do not close the claw if we cannot see the item anymore.
                    self.next_state(States.SEARCH)
                    return

                if self._at_grab_depth() and self._target_is_centered(detection):
                    self.next_state(States.GRAB)

            case States.GRAB:
                # Wait for the claw to finish closing before checking pickup.
                # TODO: replace timer with grabber_interface.is_closed() if hardware supports it.
                if time.time() - self.grab_start_time >= self.close_time:
                    self.next_state(States.VERIFY)

            case States.VERIFY:
                # The best verification later is actuator feedback:
                #   - limit switch showing claw closed around object but not fully empty
                #   - motor current spike
                #   - encoder position not reaching fully closed angle
                #   - force sensor/contact switch
                # A backup vision check can also be used after lifting slightly.
                if self._pickup_verified():
                    self.next_state(States.LIFT)
                    return

                if time.time() - self.verify_start_time > self.verify_timeout:
                    print(f"{self.name}: pickup not verified, exiting grabber mode")
                    self.next_state(States.EXIT)

            case States.LIFT:
                # Once lifted to carry depth, hold the item and let the mission continue.
                if self._at_carry_depth():
                    self.next_state(States.HOLD)

            case States.HOLD:
                # Keep holding the item. The next FSM can use navigation to reach the basket/octagon.
                # TODO: if needed, monitor claw feedback and exit/fail if the item is dropped.
                return

            case _:
                print(f"{self.name} INVALID STATE {self.state}")
                return

    # CAMERA PLACEHOLDERS -----------------------------------------------------------------------------

    def _get_item_detection(self):
        """
        Read the downward-facing camera target item detection.

        TODO: Replace this with the real camera interface.

        Expected detection shape:
            {
                "seen": True,
                "x": 0.50,          # normalized center x of item in image, 0 left to 1 right
                "y": 0.50,          # normalized center y of item in image, 0 bottom to 1 top
                "confidence": 0.90,
                "label": "item"     # optional object class from the model
            }

        Possible real calls later:
            detection = downward_camera.get_detection("resupply_item")
            detection = vision_interface.get_object("grabber_item")
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
        Return True when the item center is close enough to image center.
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

    # GRABBER / CLAW PLACEHOLDERS ---------------------------------------------------------------------

    def _open_claw(self) -> None:
        """
        Open the claw before descending around the item.

        TODO: Replace this with the real grabber interface.
        """
        # Example pseudocode:
        #   grabber_interface.open()
        #   self.shared_memory_object.claw_command.value = "OPEN"
        pass

    def _close_claw(self) -> None:
        """
        Close the claw to grab the item.

        TODO: Replace this with the real grabber interface.
        """
        # Example pseudocode:
        #   grabber_interface.close()
        #   self.shared_memory_object.claw_command.value = "CLOSE"
        pass

    def _stop_claw(self) -> None:
        """
        Stop claw actuator motion without changing whether the claw is open or closed.

        TODO: Replace this with the real grabber interface.
        """
        # Example pseudocode:
        #   grabber_interface.stop()
        #   self.shared_memory_object.claw_command.value = "STOP"
        pass

    def _pickup_verified(self) -> bool:
        """
        Return True if the item appears to be held by the claw.

        TODO: Replace this with real sensor or vision feedback.

        Good future checks:
            - claw encoder says it stopped before fully closed, meaning an object is inside
            - claw motor current increases while closing
            - limit/contact switch is pressed
            - after a small lift, downward camera no longer sees the item on the table
            - a dedicated claw camera sees the item in the claw
        """
        # For now this returns True after close_time so the skeleton can move forward.
        # Change this to False by default if you want hardware feedback before lifting.
        return time.time() - self.grab_start_time >= self.close_time

    # POSITION HELPERS --------------------------------------------------------------------------------

    def _at_grab_depth(self) -> bool:
        """
        Check if the robot is at the configured grab depth.
        """
        return abs(self.shared_memory_object.dvl_z.value - self.grab_depth) <= self.z_buffer

    def _at_carry_depth(self) -> bool:
        """
        Check if the robot is at the configured carry depth.
        """
        return abs(self.shared_memory_object.dvl_z.value - self.carry_depth) <= self.z_buffer
