import struct

from modules.USB_Transmit import USB_Transmitter

"""
    discord: @kialli
    github: @kchan5071

    Dry-run test for modules/USB_Transmit.py's USB_Transmitter.
    Uses a fake serial stand-in so this never touches real hardware, even
    if run on a machine with the sub's USB connection actually attached.
"""

class FakeSerial:
    """
    Stand-in for serial.Serial, records writes instead of sending them.
    """
    def __init__(self):
        self.last_write = None

    def write(self, data: bytes) -> None:
        self.last_write = data


def build_test_transmitter() -> USB_Transmitter:
    """
    Builds a USB_Transmitter, then swaps in a fake serial connection so
    this test never sends real bytes to the firmware.
    """
    usb = USB_Transmitter()
    usb.srl = FakeSerial() # force a fake connection, ignore whatever __init__ found
    return usb


def test_packet_length() -> None:
    usb = build_test_transmitter()
    packet = usb.build_packet()
    assert len(packet) == 56, f"expected 56 bytes, got {len(packet)}"
    print("packet length OK (56 bytes)")


def test_default_values() -> None:
    usb = build_test_transmitter()
    values = struct.unpack('<14i', usb.build_packet())
    expected = (1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1, 0, 1500, 1500, 1, 0)
    assert values == expected, f"expected {expected}, got {values}"
    print("default packet values OK")


def test_send_data_backward_compat() -> None:
    usb = build_test_transmitter()
    old_style_list = [1600, 1600, 1600, 1600, 1600, 1600, 1600, 1600, 0, 0, 0, 255, 0] # old 13-value motor+controls list
    usb.send_data(old_style_list)
    assert usb.motor_vals == [1600] * 8, f"expected motor_vals updated, got {usb.motor_vals}"
    print("send_data() backward compatibility OK")


def test_kill_unkill() -> None:
    usb = build_test_transmitter()
    usb.unkill()
    assert usb.kill_state == 0
    usb.kill()
    assert usb.kill_state == 1
    print("kill/unkill OK")


def test_dropper() -> None:
    usb = build_test_transmitter()
    usb.open_dropper()
    assert usb.dropper == 0
    usb.close_dropper()
    assert usb.dropper == 1
    print("dropper open/close OK")


def test_torpedo() -> None:
    usb = build_test_transmitter()
    usb.arm_torpedo()
    assert usb.torpedo == 0
    usb.fire_torpedo()
    assert usb.torpedo == 1
    print("torpedo arm/fire OK")


def test_grabber_servos() -> None:
    usb = build_test_transmitter()
    usb.set_grabber_servos(1200, 1800)
    assert usb.servo1 == 1200 and usb.servo2 == 1800
    print("grabber servo commands OK")


if __name__ == '__main__':
    test_packet_length()
    test_default_values()
    test_send_data_backward_compat()
    test_kill_unkill()
    test_dropper()
    test_torpedo()
    test_grabber_servos()
    print("ALL USB PACKET TESTS PASSED")
