import numpy                                as np
from numpy.typing                           import NDArray
from shared_memory                          import SharedMemoryWrapper
from typing                                 import Union
import os, yaml, time


#this is to handle errors in using the CLI for testing motors
try:
    from modules.motors.USB_Transmit        import USB_Transmitter
except:
    pass

"""
    discord: @.kech
    github: @rsunderr
    
    This class is a wrapper for the various non-motor signals for the sub.
    
    user_inputs = [
            1600, # motor 0
            1500,  # motor 1
            1500,  # motor 2
            1500,  # motor 3
            1500,  # motor 4
            1500,  # motor 5
            1500,  # motor 6
            1500,  # motor 7
            0,     # motor kill state (0 = alive, 1 = kill)
            0,     # power off state  (0 = on, 1 = off)
            0,     # servo 1 - pin30
            0,     # servo 2 - pin 29
            1000,     # dropper     (1000 = closed/est, 1400 = open)
            1500,     # torpedo     (1000 fires right, 1900 fires left, ~1500 is armed/flat)
            int(b'00000011111111', 2) # int(b'00000011111111', 2) bitmask (8 bits for motors, 6 bits for other controls)
        ]
"""
class SignalWrapper:
    def __init__(self, usb_object):
        self.usb_object = usb_object
    
    def spin_dropper(self, duration: float = 0.5, pulsewidth: int = 1400) -> None:
        """
        Spins the dropper at the specified pulse width.
        Pulse width should be between 1000 (closed/est) and 1400 (open/spinning).
        """
        message: list   = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] # default values for signals
        message[14]     = int(b'01000000000000', 2)  # unmask dropper only
        message[12]     = pulsewidth
        try:
            self.usb_object.send_data(message)
            
            # pause while it spins
            time.sleep(duration)
            
            # stop spinning
            message[12] = 1000  # Reset dropper to closed after spinning
            self.usb_object.send_data(message)
        except Exception as e:
            print(f"SIGNAL WRAPPER: Error calling dropper: {e}")
    
    def fire_torpedo(self, index: int = 1) -> None:
        """
        Fires the torpedo at the specified pulse width.
        Pulse width should be 1000 (fires right) or 1900 (fires left).
        """
        message: list   = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] # default values for signals
        message[14]     = int(b'10000000000000', 2) # unmask for torpedo only
        message[13]     = 1000  # Set torpedo pulse width to fire right
        duration: float = 0.5  # default duration to wait for torpedo to fire
        left_pw: int    = 1900  # pulse width to fire left
        right_pw: int   = 1000  # pulse width to fire right
        center_pw: int  = 1500  # pulse width to reset to center/armed
        try:
            if index == 1:
                message[13] = right_pw  # Set torpedo pulse width to fire right
                self.usb_object.send_data(message)
                time.sleep(duration)
                message[13] = center_pw  # Reset torpedo to armed/flat after firing
                self.usb_object.send_data(message)
            elif index == 2:
                message[13] = left_pw  # Set torpedo pulse width to fire left
                self.usb_object.send_data(message)
                time.sleep(duration)
                message[13] = center_pw  # Reset torpedo to armed/flat after firing
                self.usb_object.send_data(message)
            else:
                print("SINGAL WRAPPER: Invalid index for fire_torpedo. Must be 1 or 2 (default of 1)")
        except Exception as e:
            print(f"SIGNAL WRAPPER: Error calling torpedo: {e}")
    
    def lower_claw(self):
        """
        Lowers the claw by setting the appropriate pulse width.
        """
        message: list   = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] # default values for signals
        message[14]     = int(b'00010000000000', 2) # unmask for servo 1 only
        max_pw: int     = 1900  # pulse width to lower claw
        message[10]     = max_pw  # Set claw pulse width to lower it
        self.usb_object.send_data(message)
    
    def grab_claw(self):
        """
        Grabs with claw by setting the appropriate pulse width.
        """
        message: list   = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] # default values for signals
        message[14]     = int(b'00100000000000', 2) # unmask for servo 2 only
        max_pw: int     = 1900  # pulse width to close the claw on an item
        message[11]     = max_pw  # Set claw pulse width to grab
        self.usb_object.send_data(message)
        time.sleep(0.5)

    def release_claw(self):
        """
        Opens the claw (releases a held item) by setting the appropriate pulse width.
        """
        message: list   = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] # default values for signals
        message[14]     = int(b'00100000000000', 2) # unmask for servo 2 only
        min_pw: int     = 1000  # pulse width to open the claw
        message[11]     = min_pw  # Set claw pulse width to release
        self.usb_object.send_data(message)
        time.sleep(0.5)
    
    def raise_claw(self):
        """
        Raises the claw by setting the appropriate pulse width.
        """
        message: list   = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] # default values for signals
        message[14]     = int(b'00010000000000', 2) # unmask for servo 1 only
        min_pw: int     = 1000  # pulse width to lower claw
        message[10]     = min_pw  # Set claw pulse width to lower it
        self.usb_object.send_data(message)
    
    def run_loop(self):
        pass