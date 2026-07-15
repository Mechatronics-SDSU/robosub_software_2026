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


def drift_toward_targets(shared_memory_object, step: float = 0.5, yaw_step: float = 3.0) -> None:
    """
    Fake DVL movement: nudges dvl_x/y/z a little closer to target_x/y/z, and
    dvl_yaw a little closer to target_yaw (shortest direction, wraparound
    aware), every call. Lets position/heading based FSMs (gate, prequal,
    return, modem's wiggle, etc.) reach their targets during testing
    without a real DVL attached.
    """
    for axis in ("x", "y", "z"):
        dvl    = getattr(shared_memory_object, f"dvl_{axis}")
        target = getattr(shared_memory_object, f"target_{axis}")
        if dvl.value < target.value:
            dvl.value = min(dvl.value + step, target.value)
        elif dvl.value > target.value:
            dvl.value = max(dvl.value - step, target.value)

    yaw_error = ((shared_memory_object.target_yaw.value - shared_memory_object.dvl_yaw.value + 180) % 360) - 180
    if abs(yaw_error) <= yaw_step:
        shared_memory_object.dvl_yaw.value = shared_memory_object.target_yaw.value
    else:
        shared_memory_object.dvl_yaw.value += yaw_step if yaw_error > 0 else -yaw_step
