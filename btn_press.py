import serial
import struct
import subprocess

# permissions fix
device_path = ""
try:
    device_path = '/dev/ttyACM0'
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


P_DEBUG = False

# Open COM7 at 921600 baud
ser = serial.Serial(device_path, 921600, timeout=1)

print("Listening on /dev/ttyACM0 at 921600 baud...")

while True:
    # Look for the header byte 0xAA
    byte = ser.read(1)
    if not byte:
        if P_DEBUG:
            print("No data received. Retrying...")
        continue
    else:
        if P_DEBUG:
            print(f"Received byte: {byte.hex()}")  # Print the received byte in hex format
        

    if byte[0] == 0xAA:
        if P_DEBUG:
            print("Header byte 0xAA detected. Reading packet...")
        # Read the next 10 bytes (rest of the packet)
        pkt_len = 10
        packet = ser.read(pkt_len)
        # if len(packet) != pkt_len:
        #     print(f"Packet length of {len(packet)} is not {pkt_len} bytes, skipping...")
        #     continue  # incomplete packet, skip

        # Parse fields
        greenPressed = packet[0]
        extKillState = packet[1]
        intKillState = packet[2]
        depth_bytes  = packet[3:7]
        carriage_return = packet[7]
        newline = packet[8]

        # Unpack little-endian float
        depth = struct.unpack('<f', depth_bytes)[0]

        # # Optional: check packet terminator
        # if packet[7:] != b'\r\n':
        #     continue  # bad packet, skip
        
        if (int(greenPressed) == 1): 
            if P_DEBUG:
                print(f"Green: {greenPressed}, ExtKill: {extKillState}, IntKill: {intKillState}, Depth: {depth:.6f} m")
            print("Green button pressed, launching launch.py...")
            try:
                subprocess.run(["python3", "launch.py"])
            except:
                pass
        else:
            if P_DEBUG:
                print(f"Green: {greenPressed}, ExtKill: {extKillState}, IntKill: {intKillState}, Depth: {depth:.6f} m")
        
