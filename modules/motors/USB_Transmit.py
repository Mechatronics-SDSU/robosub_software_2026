import serial
# import pyserial
import struct
import numpy

baud_rate = 115200
usb_port = None
srl = None

'''
    discord: @kialli, @.kech
    github: @kchan5071, @rsunderr
    
    Handles USB transmission from motor wrapper to central microcontroller
    no print debug handle since it only prints once and its pretty useful
'''

class USB_Transmitter:
    def __init__(self):
        for port in ["/dev/ttyACM0"]:
            try:
                self.srl = serial.Serial(port, baud_rate)
                usb_port = port
                print(f"Connected on {usb_port}")
                break
            except serial.SerialException as e:
                print(f"Failed to connect on {port}: {e}")


    def send_data(self,motor_vals: list) -> None:
        # Check if connection was successful
        if self.srl is None:
            print("Unable to connect to any serial port.")
        else:
            # Proceed with transmitting if serial port is valid
            packed_data = b''
            for num in motor_vals:
                packed_data += struct.pack('<i', num)
            self.srl.write(packed_data)

    def kill_motors(self) -> None:
        user_inputs = [
            1500,   # motor 0
            1500,   # motor 1
            1500,   # motor 2
            1500,   # motor 3
            1500,   # motor 4
            1500,   # motor 5
            1500,   # motor 6
            1500,   # motor 7
            1,     # motor kill state (0 = alive, 1 = kill)
            0,     # power off state  (0 = on, 1 = off)
            0,     # servo 1 - pin30
            0,     # servo 2 - pin 29
            1000,     # dropper     (1000 = closed/est, 1400 = open/spinning)
            1500,     # torpedo     (1000 fires right, 1900 fires left, ~1500 is armed/flat)
            int(b'11111111111111', 2) # bitmask (8 bits for motors, 6 bits for other controls)
        ]
        try:
            self.send_data(user_inputs)
        except Exception as e:
            print(f"Error sending kill command: {e}")
    
    def reset_motors(self) -> None:
        user_inputs = [
            1500,   # motor 0
            1500,   # motor 1
            1500,   # motor 2
            1500,   # motor 3
            1500,   # motor 4
            1500,   # motor 5
            1500,   # motor 6
            1500,   # motor 7
            0,     # motor kill state (0 = alive, 1 = kill)
            0,     # power off state  (0 = on, 1 = off)
            1500,     # servo 1 - pin30
            1500,     # servo 2 - pin 29
            1000,     # dropper     (1000 = closed/est, 1400 = open/spinning)
            1500,     # torpedo     (1000 fires right, 1900 fires left, ~1500 is armed/flat)
            int(b'11111111111111', 2) # bitmask (8 bits for motors, 6 bits for other controls)
        ]
        try:
            self.send_data(user_inputs)
        except Exception as e:
            print(f"Error sending reset command: {e}")
    
    def soft_kill(self) -> None:
        self.reset_motors()

if __name__ == "__main__":
    """
    Kill motors if called from main
    """
    transmitter = USB_Transmitter()
    transmitter.kill_motors()