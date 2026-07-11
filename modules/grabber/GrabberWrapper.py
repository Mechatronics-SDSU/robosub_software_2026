'''
    discord: @kialli
    github: @kchan5071

    Thin wrapper for the grabber servos. Calls into the shared
    USB_Transmitter instead of opening its own serial connection.
'''

class GrabberWrapper:
    def __init__(self, usb_transmitter):
        self.usb = usb_transmitter

    def set_servos(self, servo1: int, servo2: int) -> None:
        self.usb.set_grabber_servos(servo1, servo2)
