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
    def __init__(self, comms, fake_data_frame: dict = None):
        self.comms = comms                     # real ModemComms instance, used to pack the fake frame
        self.fake_data_frame = fake_data_frame  # dict with frame_number/frame_type/color_flag/task_code to pretend
                                                 # to receive once, or None to never receive anything
        self._sent = False

    def send_raw_bytes(self, data: bytes) -> int:
        """
        Pretend to send raw bytes over the modem
        """
        print(f"[FAKE MODEM] pretending to send bytes: {data!r}")
        return len(data)

    def clear_buffers(self) -> None:
        pass

    def read_packet(self):
        """
        Pretend to receive fake_data_frame once (packed the same way a real frame would be), then go quiet.
        Sleeps briefly like the real M16 driver's read_packet timeout, so the
        background listener thread doesn't spin in a tight loop once there is
        nothing left to receive.
        """
        if self.fake_data_frame is not None and not self._sent:
            self._sent = True
            print(f"[FAKE MODEM] pretending to receive frame: {self.fake_data_frame}")
            return self.comms.pack_frame(**self.fake_data_frame)
        time.sleep(0.5)
        return None

    def close(self) -> None:
        print("[FAKE MODEM] closing (nothing to actually close)")


class FakeDropper:
    """
    Stand-in for DropperWrapper (modules/dropper/DropperWrapper.py). Prints
    instead of sending real USB commands, so the tester can safely exercise
    the FSM -> helper -> wrapper call path without hardware attached.
    """
    def open(self) -> None:
        print("FAKE DROPPER OPEN")

    def close(self) -> None:
        print("FAKE DROPPER CLOSE")


class FakeTorpedo:
    """
    Stand-in for TorpedoWrapper (modules/torpedo/TorpedoWrapper.py). Prints
    instead of sending real USB commands, so the tester can safely exercise
    the FSM -> helper -> wrapper call path without hardware attached.
    """
    def arm(self) -> None:
        print("FAKE TORPEDO ARM")

    def fire(self) -> None:
        print("FAKE TORPEDO FIRE")


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
#
# Dropper's x_norm/y_norm (0.506/0.528) are chosen so the metric back-projection
# in target_box_helpers.py (using objects.yaml's placeholder target_depth=1.0 and
# a default sub_depth of 0) lands within X_TOLERANCE_M/Y_TOLERANCE_M (~2cm error),
# demonstrating a small real correction instead of a flat 0.0 every tick. depth_m
# is unused by dropper now (it uses the pressure sensor, not vision depth) but
# still read by grabber below.
FAKE_DROPPER_DETECTIONS = {
    "survey_and_repair": [["fire", 1, 0.82, 0.506, 0.528, 0.3, 0.20, 0.18]],
    "search_and_rescue": [["blood", 3, 0.82, 0.506, 0.528, 0.3, 0.20, 0.18]],
}

# NOTE: bolt/plug/medicine/bandage/warning/helmet are not real trained vision
# classes yet, see modules/grabber/grabber_helpers.py
FAKE_GRABBER_DETECTIONS = {
    "survey_and_repair": [
        ["bolt", 0, 0.82, 0.47, 0.52, 0.3, 0.15, 0.15],
        ["plug", 0, 0.82, 0.47, 0.52, 0.3, 0.15, 0.15],
        ["warning", 0, 0.82, 0.47, 0.52, 0.3, 0.25, 0.20],
    ],
    "search_and_rescue": [
        ["medicine", 0, 0.82, 0.47, 0.52, 0.3, 0.15, 0.15],
        ["bandage", 0, 0.82, 0.47, 0.52, 0.3, 0.15, 0.15],
        ["helmet", 0, 0.82, 0.47, 0.52, 0.3, 0.25, 0.20],
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
