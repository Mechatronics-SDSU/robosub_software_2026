import serial
# import pyserial
import struct
import time

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
                print(f"Failed to connect on {port}: {e}")

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

def main():
    while True:
        driver = StartButtonDriver()
        driver.send_data([0, 0, 0, 0, 0, 0, 0, 0])
        value = driver.recieve_data()
        if value is not None:
            print(f"Received value: {value}")
            driver.disconnect()
            time.sleep(4)
        else:
            print("No valid data received.")
        # Add a small delay to avoid overwhelming the serial port
        time.sleep(2)

if __name__ == "__main__":
    main()