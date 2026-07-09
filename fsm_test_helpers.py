"""
    Fake input helpers for test_fsm_ctrl.py

    These stand in for real hardware (DVL, modem) so FSMs can be tested
    without the sub being in the water or a modem being plugged in.
    Only used for testing, never imported by the real mission code.
"""
import time

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
        Pretend to receive fake_code once (encoded the same way a real message would be), then go quiet.
        Sleeps briefly like the real M16 driver does, so the background listener thread
        doesn't spin in a tight loop once there is nothing left to receive.
        """
        if self.fake_code is not None and not self._sent:
            self._sent = True
            print(f"[FAKE MODEM] pretending to receive code {self.fake_code}")
            return self.comms.encode_message(self.fake_code)
        time.sleep(min(timeout, 0.5))
        return None

    def clear_buffers(self) -> None:
        pass

    def close(self) -> None:
        print("[FAKE MODEM] closing (nothing to actually close)")


FAKE_TORPEDO_CIRCLE_DATA = {
    # sample circle_data dict for testing the torpedo FSM without a camera/vision pipeline attached
    "wheels": [
        {"x_norm": 0.20, "y_norm": 0.50, "radius": 0.03},
        {"x_norm": 0.80, "y_norm": 0.50, "radius": 0.03},
    ],
    "small_holes": [
        {"x_norm": 0.45, "y_norm": 0.52, "radius": 0.05},
    ],
    "big_holes": [
        {"x_norm": 0.50, "y_norm": 0.50, "radius": 0.08},
    ],
}


# sample vision target box detections for testing dropper/grabber without a camera attached
# format: [class_label, class_id, conf, x_norm, y_norm, depth_m, width, height]
FAKE_DROPPER_DETECTIONS = {
    "survey_and_repair": [["fire", 1, 0.82, 0.50, 0.50, 0.9, 0.20, 0.18]],
    "search_and_rescue": [["blood", 3, 0.82, 0.50, 0.50, 0.9, 0.20, 0.18]],
}

# NOTE: bolt/plug/medicine/bandage/warning/helmet are not real trained vision
# classes yet, see modules/vision/grabber_helpers.py
FAKE_GRABBER_DETECTIONS = {
    "survey_and_repair": [
        ["bolt", 0, 0.82, 0.50, 0.50, 0.9, 0.15, 0.15],
        ["plug", 0, 0.82, 0.50, 0.50, 0.9, 0.15, 0.15],
        ["warning", 0, 0.82, 0.50, 0.50, 0.9, 0.25, 0.20],
    ],
    "search_and_rescue": [
        ["medicine", 0, 0.82, 0.50, 0.50, 0.9, 0.15, 0.15],
        ["bandage", 0, 0.82, 0.50, 0.50, 0.9, 0.15, 0.15],
        ["helmet", 0, 0.82, 0.50, 0.50, 0.9, 0.25, 0.20],
    ],
}


def drift_toward_targets(shared_memory_object, step: float = 0.5) -> None:
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
