import serial
# import pyserial
import struct
import time
import os
import socket_send

baud_rate = 115200
usb_port = None

class StartButtonDriver:
    def __init__(self):
        self.srl = None
        for port in ["COM3", "/dev/ttyACM0"]:
            try:
                self.srl = serial.Serial(port, baud_rate)
                usb_port = port
                print(f"Connected on {usb_port}")
                break
            except serial.SerialException as e:
                # print(f"Failed to connect on {port}: {e}")
                pass


    def disconnect(self):
        if self.srl is not None:
            self.srl.close()
            print("Disconnected from serial port.")
        else:
            print("No serial port to disconnect from.")

    def send_data(self,motor_vals):
        # Check if connection was successful
        if self.srl is None:
            print("❌ Unable to connect to any serial port.")
        else:
            # Proceed with transmitting if serial port is valid
            packed_data = b''
            for num in motor_vals:
                packed_data += struct.pack('<i', num)
            self.srl.write(packed_data)

    def clear_socket(self):
        if self.srl is not None:
            self.srl.reset_input_buffer()
            self.srl.reset_output_buffer()
            print("Cleared serial buffers.")
        else:
            print("No serial port to clear buffers from.")


    def recieve_data(self):
        if self.srl is None:
            print("Serial port not initialized.")
            return None
        
        try:
            data = self.srl.read(4)  # Read 4 bytes
            if len(data) < 4:
                print("Incomplete data received.")
                return None
            
            # Unpack the data as an unsigned integer
            value = struct.unpack('I', data)[0]
            return value
        except serial.SerialException as e:
            print(f"Serial error: {e}")
            return None
        except struct.error as e:
            print(f"Struct error: {e}")
            return None

def start_launch():
    os.system(os.path.expanduser("python3 ~/robosub_software_2025/display_manager/start_services.py")) # startup display
    os.system(os.path.expanduser("python3 ~/robosub_software_2025/launch.py")) # run launch

def main():
    socket_send.set_screen((0, 0, 0), "RoboSub", "Starting...")  # Set initial screen state
    while True:
        driver = StartButtonDriver()
        driver.send_data([0, 0, 0, 0, 0, 0, 0, 0])
        value = driver.recieve_data()
        print(value)
        if value is not None and value == 426:
            socket_send.set_screen((0, 150, 0), "RoboSub", "Starting Launch")  # Set screen to green
            # start_launch()
            driver.clear_socket()
            driver.disconnect()
            time.sleep(4)
            continue
        else:
            print("No valid data received.")
        # Add a small delay to avoid overwhelming the serial port
        driver.clear_socket()
        time.sleep(1)

if __name__ == "__main__":
    main()