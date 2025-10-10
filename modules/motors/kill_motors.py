import serial
import struct

BAUD_RATE = 115200
USB_PORT = None

DATA = [0, 0, 0, 0, 0, 0, 0, 0]

"""
    discord: @kialli
    github: @kchan5071

    quick and dirty way to kill motors, this can honestly be done in a single function
    but it was copy pasted from start_button.py
"""


class MotorKill:
    def __init__(self):
        for port in ["/dev/ttyACM0"]:
            try:
                self.srl = serial.Serial(port, BAUD_RATE)
                USB_PORT = port
                print(f"Connected on {USB_PORT}")
                break
            except serial.SerialException as e:
                print(f"Failed to connect on {port}: {e}")


    def send_data(self,motor_vals: list) -> None:
        # Check if connection was successful
        if self.srl is None:
            print("❌ Unable to connect to any serial port.")
        else:
            # Proceed with transmitting if serial port is valid
            packed_data = b''
            for num in motor_vals:
                packed_data += struct.pack('<i', num)
            self.srl.write(packed_data)

def kill_motors():
    motor_kill = MotorKill()
    motor_kill.send_data(DATA)



if __name__ == "__main__":
    motor_kill = MotorKill()
    motor_kill.send_data(DATA)
