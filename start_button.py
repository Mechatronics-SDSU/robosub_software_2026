import serial
import struct
import time
import os
import utils.socket_send as socket_send

baud_rate = 115200
usb_port = None

"""
    discord: @.kech, @kialli
    github: @rsunderr, @kchan5071

    Handles the start button input from the central microcontroller
    the button colors are as follows:
    red: power flush
    green: ready to launch
    blue: debug mode (tbd)
"""

#these codes are sent from the microcontroller to indicate button presses
#from what I can tell, they are just arbitrary values
DEBUG_MODE_CODE = 65706
START_LAUNCH_CODE = 426

DEBUG_MODE_COLOR = (0, 0, 150) # blue
START_LAUNCH_COLOR = (0, 150, 0) # green
STARTUP_COLOR = (0, 0, 0) # black
DISPLAY_ON = False # whether or not to run display code

TIMEOUT = 1  # seconds

P_DEBUG = False  # set to true to enable print debugging for this file

class StartButtonDriver:
    def __init__(self):
        self.srl = None
        for port in ["COM3", "/dev/ttyACM0"]:
            try:
                self.srl = serial.Serial(port, baud_rate)
                usb_port = port
                if P_DEBUG:
                    print(f"Connected on {usb_port}")
                break
            except serial.SerialException as e:
                if P_DEBUG:
                    print(f"Failed to connect on {port}: {e}")
                pass


    def disconnect(self):
        """
        Disconnects from the serial port if connected.
        """
        if self.srl is not None:
            self.srl.close()
            if P_DEBUG:
                print("Disconnected from serial port.")
        else:
            if P_DEBUG:
                print("No serial port to disconnect from.")

    def send_data(self,motor_vals):
        """
        sends motor values and extra commands to the microcontroller via serial communication
        (see /modules/motors/new_motor_format.txt for more details)
        """
        # Check if connection was successful
        if self.srl is None:
            if P_DEBUG:
                print("❌ Unable to connect to any serial port.")
        else:
            # Proceed with transmitting if serial port is valid
            packed_data = b''
            for num in motor_vals:
                packed_data += struct.pack('<i', num)
            self.srl.write(packed_data)

    def clear_socket(self):
        """
        clears the serial buffer to avoid overflow
        """
        if self.srl is not None:
            self.srl.reset_input_buffer()
            self.srl.reset_output_buffer()
            if P_DEBUG:
                print("Cleared serial buffers.")
        else:
            if P_DEBUG:
                print("No serial port to clear buffers from.")


    def recieve_data(self):
        """
        receives data from the microcontroller via serial communication, expects a 4 byte unsigned int
        """
        if self.srl is None:
            if P_DEBUG:
                print("Serial port not initialized.")
            return None
        
        try:
            data = self.srl.read(4)  # Read 4 bytes
            if len(data) < 4:
                if P_DEBUG:
                    print("Incomplete data received.")
                return None
            
            # Unpack the data as an unsigned integer
            value = struct.unpack('I', data)[0]
            return value
        except serial.SerialException as e:
            if P_DEBUG:
                print(f"Serial error: {e}")
            return None
        except struct.error as e:
            if P_DEBUG:
                print(f"Struct error: {e}")
            return None

def start_launch():
    """
    Starts the launch sequence by running the necessary scripts.
    launch.py starts the main sub code
    start_services.py starts the background services,in this case just the display manager
    """
    if DISPLAY_ON:
        os.system(os.path.expanduser("python3 ~/robosub_software_2025/display_manager/start_services.py")) # startup display
    os.system(os.path.expanduser("python3 ~/robosub_software_2025/launch.py")) # run launch

def main():
    """
    Main function to handle start button input and trigger launch or debug mode.
    """
    print("Starting start button handler...")
    #start screen
    if DISPLAY_ON:
        socket_send.set_screen(STARTUP_COLOR, "RoboSub", "Starting...")  # Set initial screen state

    #this next loop should never exit, it will just keep trying to connect to the start button
    while True:
        driver = StartButtonDriver()
        driver.send_data([0, 0, 0, 0, 0, 0, 0, 0])
        value = driver.recieve_data()
        # check what value was received
        if value is not None and value == START_LAUNCH_CODE:
            if DISPLAY_ON:
                socket_send.set_screen(START_LAUNCH_COLOR, "RoboSub", "Starting Launch")  # Set screen to green
            start_launch()
            driver.clear_socket()
            driver.disconnect()
            time.sleep(TIMEOUT)
            continue
        elif value is not None and value == DEBUG_MODE_CODE:
            if DISPLAY_ON:
                socket_send.set_screen(DEBUG_MODE_COLOR, "RoboSub", "Debug Mode")  # Set screen to blue
            # we should figure out what to do in debug mode and put it here
            # -------------
            # start_launch()
            # -------------
            driver.clear_socket()
            driver.disconnect()
            time.sleep(TIMEOUT)
        else:
            driver.clear_socket()
        time.sleep(1)

if __name__ == "__main__":
    main()