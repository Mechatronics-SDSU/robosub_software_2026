"""
    Fake input helpers for test_fsm_ctrl.py

    These stand in for real hardware (DVL, modem) so FSMs can be tested
    without the sub being in the water or a modem being plugged in.
    Only used for testing, never imported by the real mission code.
"""

class FakeModem:
    """
    Stand-in for the real M16 modem (modules/modem/modem_driver.py).
    Passed to Modem_FSM in place of a real serial connection so the FSM
    can be run without modem hardware attached.
    """
    def __init__(self, comms, fake_code: int = None):
        self.comms = comms         # real ModemComms instance, used to encode the fake message
        self.fake_code = fake_code # code to pretend to receive once, or None to never receive anything
        self._sent = False

    def send_two_bytes(self, data: bytes) -> int:
        """
        Pretend to send bytes over the modem
        """
        print(f"[FAKE MODEM] pretending to send bytes: {data!r}")
        return 2

    def read_two_bytes(self, timeout: float = 30.0):
        """
        Pretend to receive fake_code once (encoded the same way a real message would be), then go quiet
        """
        if self.fake_code is not None and not self._sent:
            self._sent = True
            print(f"[FAKE MODEM] pretending to receive code {self.fake_code}")
            return self.comms.encode_message(self.fake_code)
        return None

    def clear_buffers(self) -> None:
        pass

    def close(self) -> None:
        print("[FAKE MODEM] closing (nothing to actually close)")


def drift_toward_targets(shared_memory_object, step: float = 0.1) -> None:
    """
    Fake DVL movement: nudges dvl_x/y/z a little closer to target_x/y/z
    every call. Lets position based FSMs (gate, prequal, return, etc.)
    reach their targets during testing without a real DVL attached.
    """
    for axis in ("x", "y", "z"):
        dvl    = getattr(shared_memory_object, f"dvl_{axis}")
        target = getattr(shared_memory_object, f"target_{axis}")
        if dvl.value < target.value:
            dvl.value = min(dvl.value + step, target.value)
        elif dvl.value > target.value:
            dvl.value = max(dvl.value - step, target.value)
