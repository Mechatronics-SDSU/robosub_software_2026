import time
import serial
import serial.tools.list_ports

BAUD_RATE = 115200
DEVICE_ID = "BATTERY_MONITOR_V1"


class USB_Battery_Receiver_Caracara:
    def __init__(self):
        self.srl = None
        self.port = None

    def find_serial_ports(self):
        ports = []

        for port in serial.tools.list_ports.comports():
            if port.device != "/dev/ttyACM0":  # Ignore bad linux port
                ports.append(port.device)

        return ports

    def connect(self):
        if self.srl is not None:
            return True

        ports = self.find_serial_ports()

        for port in ports:
            try:
                test_srl = serial.Serial(port, BAUD_RATE, timeout=1)
                print(f"Testing port {port}...")

                time.sleep(2)
                test_srl.reset_input_buffer()

                for _ in range(5):
                    line = test_srl.readline().decode(errors="ignore").strip()
                    print(f"Handshake line: {repr(line)}")

                    if line.startswith(DEVICE_ID):
                        self.srl = test_srl
                        self.port = port
                        print(f"Connected to battery monitor on {port}")
                        return True

                test_srl.close()

            except serial.SerialException as e:
                print(f"Failed to connect on {port}: {e}")

        return False

    def disconnect(self):
        if self.srl is not None:
            try:
                self.srl.close()
            except serial.SerialException:
                pass

        print("Battery monitor disconnected")
        self.srl = None
        self.port = None

    def read_voltage(self):
        if self.srl is None:
            self.connect()
            return None

        try:
            line = self.srl.readline().decode(errors="ignore").strip()

            if not line:
                return None

            if not line.startswith(DEVICE_ID):
                return None

            parts = line.split(",")

            for part in parts:
                if part.startswith("BAT:"):
                    return float(part.split(":", 1)[1])

            return None

        except (serial.SerialException, OSError):
            self.disconnect()
            return None

        except ValueError:
            return None