'''
    discord: @kialli
    github: @kchan5071

    Thin wrapper for the dropper mechanism. Calls into the shared
    USB_Transmitter instead of opening its own serial connection.
'''

class DropperWrapper:
    def __init__(self, usb_transmitter):
        self.usb = usb_transmitter

    def open(self) -> None:
        self.usb.open_dropper()

    def close(self) -> None:
        self.usb.close_dropper()
