'''
    discord: @kialli
    github: @kchan5071

    Thin wrapper for the torpedo mechanism. Calls into the shared
    USB_Transmitter instead of opening its own serial connection.
'''

class TorpedoWrapper:
    def __init__(self, usb_transmitter):
        self.usb = usb_transmitter

    def arm(self) -> None:
        self.usb.arm_torpedo()

    def fire(self) -> None:
        self.usb.fire_torpedo()
