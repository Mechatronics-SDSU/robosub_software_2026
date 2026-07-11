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
"""

FRAME_LISTEN_TIMEOUT = 15.0  # seconds to wait for a valid frame before giving up

class States(Enum):
    """
    Enumeration for FSM states
    """
    INIT        = "INIT"
    SEND_DATA   = "SEND_DATA"
    AWAIT_ACK   = "AWAIT_ACK"
    LISTEN_DATA = "LISTEN_DATA"
    SEND_ACK    = "SEND_ACK"
    DONE        = "DONE"

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
            case States.AWAIT_ACK: # transition: AWAIT_ACK -> DONE (success or timeout)
                frame = self.comms.get_latest_frame()
                if frame is not None:
                    self.logger.info(f"{self.name} received ack: {frame}")
                    self.success = True
                    self.next_state(States.DONE)
                elif monotonic() - self._state_entry_time > FRAME_LISTEN_TIMEOUT:
                    self.logger.warning(f"{self.name} no ack received, giving up")
                    self.success = False
                    self.next_state(States.DONE)
            case States.LISTEN_DATA: # transition: LISTEN_DATA -> SEND_ACK. No timeout here:
                # this is the idle state the listener starts in at launch and should sit in
                # indefinitely, the same way it will on the real vehicle, until a data frame
                # actually arrives -- not a bounded test window.
                frame = self.comms.get_latest_frame()
                if frame is not None:
                    self.received_frame = frame
                    self.logger.info(f"{self.name} received data frame: {frame}")
                    self.comms.stop_frame_listener()
                    self.next_state(States.SEND_ACK)
            case States.SEND_ACK: # transition: SEND_ACK -> DONE
                self.next_state(States.DONE)
            case States.DONE: # transition: DONE -> off
                self.suspend()
            case _: # do nothing if invalid state
                self.logger.error(f"{self.name} INVALID STATE {self.state}")
