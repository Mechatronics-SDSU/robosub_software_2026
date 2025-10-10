import serial, struct, os, time

usb_port = 'COM6'  # Update this to your port
baud_rate = 115200 #921600

class ButtonInterface:
    def __init__(self, shared_memory_object):
        self.shared_memory_object = shared_memory_object
        self.ser = serial.Serial(usb_port, baud_rate, timeout=1)
        self.delay = 0.001
    
    def read_packet(self):
        """
        Reads data packet from electrical system
        """
        while True:
            byte = self.ser.read(1)
            if not byte:
                continue

            if byte[0] == 0xAA:  # Found header
                # Read remaining 10 bytes of the packet
                data = self.ser.read(10)
                if len(data) < 10:
                    continue  # incomplete packet, discard and resync
                
                greenPressed = data[0]
                bluePressed = data[1]
                extKillState = data[2]
                intKillState = data[3]
                depth_bytes = data[4:8]

                depth = struct.unpack('<f', depth_bytes)[0]

                # Optionally verify trailing \r\n
                if data[8] != 13 or data[9] != 10:
                    print("Warning: packet missing expected newline characters")

                return greenPressed, bluePressed, extKillState, intKillState, depth
        
    def run_loop(self):
        """
        Check if green button is pressed
        """
        if self.read_packet()[0]: # if green pressed
            os.system(os.path.expanduser("python3 ~/robosub_software_2025/display_manager/start_services.py")) # startup display
            os.system(os.path.expanduser("python3 ~/robosub_software_2025/launch.py")) # run launch
        time.sleep(self.delay) # delay

    
    def print_data(self):
        """
        Prints data read from button USB
        """
        gp, bp, ek, ik, depth = self.read_packet()
        print(f"Green: {gp}, Blue: {bp}, ExtKill: {ek}, IntKill: {ik}, Depth: {depth}")

    def close(self):
        """
        Close serial connection
        """
        self.ser.close()