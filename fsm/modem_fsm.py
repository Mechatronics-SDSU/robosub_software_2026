from fsm.fsm                                    import FSM_Template
from modules.logger.logger                      import Logger
from modules.modem.modem_comms                  import ModemComms
from enum                                        import Enum

"""
    FSM for sub-to-sub communication over the M16 acoustic modem.
    Runs as either a sender (sends one message code) or a listener
    (waits for an incoming message).
"""
class States(Enum):
    """
    Enumeration for FSM states
    """
    INIT    = "INIT"
    SEND    = "SEND"
    LISTEN  = "LISTEN"
    DONE    = "DONE"

    def __str__(self) -> str: # make elegant string
        return self.value

class Modem_FSM(FSM_Template):
    """
    FSM for modem mode - sending or listening for a message over the M16 modem
    """
    def __init__(self, shared_memory_object, run_list: list, role: str, port: str, message: int = 0,
                 channel: int = 1, power_level: int = 1):
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
        self.message = message
        self.channel = channel
        self.power_level = power_level

        self.comms = ModemComms()
        self.modem = None
        self.received_message = None

    def start(self) -> None:
        """
        Start FSM by enabling and starting processes
        """
        super().start()  # call parent start method

        self.modem = self.comms.open_modem(self.port, channel=self.channel, power_level=self.power_level)

        # set initial state
        if self.role == "sender":
            self.next_state(States.SEND)
        elif self.role == "listener":
            self.next_state(States.LISTEN)
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
            case States.SEND: # send one message, half-duplex so no listener running here
                self.comms.send_message(self.modem, self.message)
            case States.LISTEN: # start background listener for incoming messages
                self.comms.start_listener(self.modem)
            case States.DONE: # stop listening (if needed) and close the modem
                self.comms.stop_listener()
                self.modem.close()
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
        self.display(0, 150, 255) # update display

        # TRANSITIONS------------------------------------------------------------------------------------------------------
        match(self.state):
            case States.INIT: return
            case States.SEND: # transition: SEND -> DONE
                self.next_state(States.DONE)
            case States.LISTEN: # transition: LISTEN -> DONE
                received = self.comms.get_latest_message()
                if received is not None:
                    self.received_message = received
                    self.logger.info(f"{self.name} received message: {received}")
                    self.next_state(States.DONE)
            case States.DONE: # transition: DONE -> off
                self.suspend()
            case _: # do nothing if invalid state
                self.logger.error(f"{self.name} INVALID STATE {self.state}")
