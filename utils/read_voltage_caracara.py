import subprocess
try:
    device_path = '/dev/ttyACM1'
    subprocess.run(["sudo", "chmod", "777", device_path], check=True)
    print(f"Permissions changed for {device_path}")
except subprocess.CalledProcessError as e:
    print(f"ERROR: Permissions fix failed (subprocess error): {e}")
except FileNotFoundError as e:
    print(f"ERROR: Permissions fix failed (command or device not found): {e}")
except PermissionError as e:
    print(f"ERROR: Permissions fix failed (permission denied): {e}")
except OSError as e:
    print(f"ERROR: Permissions fix failed (OS error): {e}")

import time
from usb_battery_receiver_caracara import USB_Battery_Receiver_Caracara

battery = USB_Battery_Receiver_Caracara()

while True:
    voltage = battery.read_voltage()

    if voltage is not None:
        print(f"Battery voltage: {voltage:.2f} V")
    
    #Delay in seconds
    time.sleep(1)