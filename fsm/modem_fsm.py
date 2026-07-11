from fsm.fsm                                    import FSM_Template
from modules.logger.logger                      import Logger
from modules.modem.modem_comms                  import ModemComms, FRAME_TYPE_DATA, FRAME_TYPE_ACK
from enum                                        import Enum
from time                                        import monotonic

"""
    FSM for sub-to-sub communication over the M16 acoustic modem.
    Runs as either a sender (transmits one data frame, then waits for an ack)
    or a listener (waits for a data frame, then sends an ack back).

    Frame format (5 bits, repeated 3x + 1 padding bit = 2 bytes on the wire):
        frame_number(1) | frame_type(1, 0=DATA/1=ACK) | color_flag(1) | task_code(2)

    Reliability comes from sending each frame twice back-to-back
    (unconditional redundancy) rather than a conditional retry, so there's
    no attempt-counter state to track. The listening side just listens
    continuously over one window long enough to catch either transmission.

    A "wiggle" (turn +45 deg from heading, back to center, then -45 deg) is
    a visible confirmation that a frame was received: once after the
    listener gets the DATA frame (before sending its ack), and once after
    the sender gets the ACK back. It never overlaps with modem traffic --
    the background frame listener is always stopped before a wiggle starts,
    and no further modem send/listen begins until all 3 legs finish, so
    movement and modem communication are strictly sequenced, never
    concurrent. Movement needs a PID process running (pass
    [pid_object, dvl_object] as run_list) or target_yaw updates go nowhere.

    Each leg ramps target_yaw by wall-clock time (not by how many loop()
    ticks occur), so the wiggle takes the same ~WIGGLE_TOTAL_DURATION
    seconds regardless of loop rate -- this test harness sleeps 0.2s/tick,
    but launch.py's real mission loop has no delay between ticks at all.
    FRAME_LISTEN_TIMEOUT is sized to comfortably cover the other side
    doing a full wiggle + sending its ack before giving up.
"""

FRAME_LISTEN_TIMEOUT = 35.0  # seconds to wait for a valid frame before giving up

WIGGLE_ANGLE_DEG = 45.0                          # how far each leg turns from the base heading
WIGGLE_TOTAL_DURATION = 12.0                     # target wall-clock time for all 3 legs combined, 3s/leg
WIGGLE_LEG_DURATION = WIGGLE_TOTAL_DURATION / 3  # time budget per leg
WIGGLE_TOLERANCE_DEG = 5.0                       # lets a leg finish early if dvl_yaw already caught up

class States(Enum):
    """
    Enumeration for FSM states
    """
    INIT          = "INIT"
    SEND_DATA     = "SEND_DATA"
    AWAIT_ACK     = "AWAIT_ACK"
    LISTEN_DATA   = "LISTEN_DATA"
    WIGGLE_LEFT   = "WIGGLE_LEFT"
    WIGGLE_CENTER = "WIGGLE_CENTER"
    WIGGLE_RIGHT  = "WIGGLE_RIGHT"
    SEND_ACK      = "SEND_ACK"
    DONE          = "DONE"

    def __str__(self) -> str: # make elegant string
        return self.value

class Modem_FSM(FSM_Template):
    """
    FSM for modem mode - exchanging one data/ack frame pair over the M16 modem
    """
    def __init__(self, shared_memory_object, run_list: list, role: str, port: str,
                 task_code: int = 0, color_flag: bool = False,
                 channel: int = 1, power_level: int = 4):
        """
        Modem FSM constructor
        """
        # call parent constructor
        super().__init__(shared_memory_object, run_list)
        self.name: str      = "MODEM"
        self.state: States  = States.INIT  # initial state
        self.logger = Logger()

        # MODEM SETTINGS-----------------------------------------------------------------------------------------------------------------------
        self.role = role # "sender" or "listener"
        self.port = port
        self.task_code = task_code
        self.color_flag = int(bool(color_flag))
        self.frame_number = 0 # arbitrary; the listener doesn't use it for duplicate detection
        self.channel = channel
        self.power_level = power_level

        self.comms = ModemComms()
        self.modem = None
        self.received_frame = None  # the DATA frame this FSM received, if role == "listener"
        self.success = False        # whether the data/ack exchange completed
        self._state_entry_time = None

        # WIGGLE STATE---------------------------------------------------------------------------------------------------------------------
        self._wiggle_base_yaw = None  # heading captured at the start of the wiggle sequence
        self._post_wiggle_state = None  # state to enter once all 3 wiggle legs finish

    def start(self) -> None:
        """
        Start FSM by enabling and starting processes
        """
        super().start()  # call parent start method

        self.modem = self.comms.open_modem(self.port, channel=self.channel, power_level=self.power_level)

        # set initial state
        if self.role == "sender":
            self.next_state(States.SEND_DATA)
        elif self.role == "listener":
            self.next_state(States.LISTEN_DATA)
        else:
            self.logger.error(f"{self.name} INVALID ROLE {self.role}")
            self.suspend()

    def next_state(self, next: States) -> None:
        """
        Change to next state
        """
        if not self.active or self.state == next: return # do nothing if not enabled or no state change
        # STATES-----------------------------------------------------------------------------------------------------------------------
        match(next):
            case States.INIT: return # initial state
            case States.SEND_DATA: # send the data frame twice, half-duplex so no listener running here
                self.comms.send_frame_redundant(self.modem, self.frame_number, FRAME_TYPE_DATA, self.color_flag, self.task_code)
                self._state_entry_time = monotonic()
            case States.AWAIT_ACK: # start background listener, filtered to ACK frames only
                self.comms.start_frame_listener(self.modem, expected_frame_type=FRAME_TYPE_ACK)
                self._state_entry_time = monotonic()
            case States.LISTEN_DATA: # start background listener, filtered to DATA frames only
                self.comms.start_frame_listener(self.modem, expected_frame_type=FRAME_TYPE_DATA)
                self._state_entry_time = monotonic()
            case States.WIGGLE_LEFT: # first wiggle leg: capture the heading to wiggle around
                self._wiggle_base_yaw = self.shared_memory_object.dvl_yaw.value
                self._state_entry_time = monotonic()
            case States.WIGGLE_CENTER | States.WIGGLE_RIGHT: # later legs just reset the per-leg timer
                self._state_entry_time = monotonic()
            case States.SEND_ACK: # echo the received frame's fields back twice as an ack
                frame = self.received_frame
                self.comms.send_frame_redundant(self.modem, frame["frame_number"], FRAME_TYPE_ACK, frame["color_flag"], frame["task_code"])
                self.success = True
            case States.DONE: # stop listening (if needed) and close the modem
                self.comms.stop_frame_listener()
                self.modem.close()
            case _: # do nothing if invalid state
                self.logger.error(f"{self.name} INVALID NEXT STATE {next}")
                return
        old_state = self.state
        self.state = next
        self.logger.info(f"State changed: {old_state} -> {self.state}")
        self.display(0, 150, 255) # update display -- only on actual transitions, DVL/TGT position
                                   # is meaningless for a stationary modem handshake and doesn't
                                   # need to be logged every tick

    def loop(self) -> None:
        """
        Loop function, mostly state transitions within conditionals
        """
        if not self.active: return # do nothing if not enabled

        # TRANSITIONS------------------------------------------------------------------------------------------------------
        match(self.state):
            case States.INIT: return
            case States.SEND_DATA: # transition: SEND_DATA -> AWAIT_ACK
                self.next_state(States.AWAIT_ACK)
            case States.AWAIT_ACK: # transition: AWAIT_ACK -> WIGGLE_LEFT (success) or DONE (timeout)
                frame = self.comms.get_latest_frame()
                if frame is not None:
                    self.logger.info(f"{self.name} received ack: {frame}")
                    self.success = True
                    self.comms.stop_frame_listener() # done with modem traffic before we start moving
                    self._post_wiggle_state = States.DONE
                    self.next_state(States.WIGGLE_LEFT)
                elif monotonic() - self._state_entry_time > FRAME_LISTEN_TIMEOUT:
                    self.logger.warning(f"{self.name} no ack received, giving up")
                    self.success = False
                    self.next_state(States.DONE) # no wiggle on failure
            case States.LISTEN_DATA: # transition: LISTEN_DATA -> WIGGLE_LEFT. No timeout here:
                # this is the idle state the listener starts in at launch and should sit in
                # indefinitely, the same way it will on the real vehicle, until a data frame
                # actually arrives -- not a bounded test window.
                frame = self.comms.get_latest_frame()
                if frame is not None:
                    self.received_frame = frame
                    self.logger.info(f"{self.name} received data frame: {frame}")
                    self.comms.stop_frame_listener() # done with modem traffic before we start moving
                    self._post_wiggle_state = States.SEND_ACK
                    self.next_state(States.WIGGLE_LEFT)
            case States.WIGGLE_LEFT: # transition: WIGGLE_LEFT -> WIGGLE_CENTER
                if self._step_wiggle_leg(self._wiggle_base_yaw, self._wiggle_base_yaw + WIGGLE_ANGLE_DEG):
                    self.next_state(States.WIGGLE_CENTER)
            case States.WIGGLE_CENTER: # transition: WIGGLE_CENTER -> WIGGLE_RIGHT
                if self._step_wiggle_leg(self._wiggle_base_yaw + WIGGLE_ANGLE_DEG, self._wiggle_base_yaw):
                    self.next_state(States.WIGGLE_RIGHT)
            case States.WIGGLE_RIGHT: # transition: WIGGLE_RIGHT -> post-wiggle state (SEND_ACK or DONE)
                if self._step_wiggle_leg(self._wiggle_base_yaw, self._wiggle_base_yaw - WIGGLE_ANGLE_DEG):
                    self.next_state(self._post_wiggle_state)
            case States.SEND_ACK: # transition: SEND_ACK -> DONE
                self.next_state(States.DONE)
            case States.DONE: # transition: DONE -> off
                self.suspend()
            case _: # do nothing if invalid state
                self.logger.error(f"{self.name} INVALID STATE {self.state}")

    def _step_wiggle_leg(self, start_deg: float, end_deg: float) -> bool:
        """
        Ramp target_yaw linearly from start_deg to end_deg over
        WIGGLE_LEG_DURATION seconds of wall-clock time (not tied to how
        often loop() gets called), so the whole wiggle takes a predictable
        ~WIGGLE_TOTAL_DURATION seconds no matter the loop rate. Finishes
        early if dvl_yaw is already within WIGGLE_TOLERANCE_DEG of end_deg
        (lets it snap ahead if the sub keeps up with the ramp); otherwise
        the leg's time budget is itself the safety net in case yaw feedback
        never arrives (e.g. no DVL attached). Returns True once this leg is
        done, signalling the caller to move on to the next leg.
        """
        elapsed = monotonic() - self._state_entry_time
        fraction = min(elapsed / WIGGLE_LEG_DURATION, 1.0)
        self.shared_memory_object.target_yaw.value = start_deg + fraction * self._yaw_error(end_deg, start_deg)

        current_yaw = self.shared_memory_object.dvl_yaw.value
        reached = abs(self._yaw_error(end_deg, current_yaw)) <= WIGGLE_TOLERANCE_DEG

        if fraction >= 1.0 and not reached:
            self.logger.warning(f"{self.name} wiggle leg time budget elapsed before reaching {end_deg:.1f} deg")

        return reached or fraction >= 1.0

    def _yaw_error(self, target_deg: float, current_deg: float) -> float:
        """
        Shortest signed angular difference (target - current), wrapped to
        [-180, 180] so a wraparound at 0/360 doesn't look like a huge turn.
        """
        return ((target_deg - current_deg + 180) % 360) - 180
