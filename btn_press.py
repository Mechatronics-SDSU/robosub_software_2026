import serial
import struct
import subprocess


# Open COM7 at 921600 baud
ser = serial.Serial('/dev/ttyACM0', 921600, timeout=1)

print("Listening on /dev/ttyACM0 at 921600 baud...")

while True:
    # Look for the header byte 0xAA
    byte = ser.read(1)
    if not byte:
        continue

    if byte[0] == 0xAA:
        # Read the next 10 bytes (rest of the packet)
        packet = ser.read(10)
        if len(packet) != 10:
            continue  # incomplete packet, skip

        # Parse fields
        greenPressed = packet[0]
        bluePressed  = packet[1]
        extKillState = packet[2]
        intKillState = packet[3]
        depth_bytes  = packet[4:8]

        # Unpack little-endian float
        depth = struct.unpack('<f', depth_bytes)[0]

        # Optional: check packet terminator
        if packet[8:] != b'\r\n':
            continue  # bad packet, skip
        
        if (int(greenPressed) == 1): 
            subprocess.run(["python3", "launch.py"])

        # Print neatly
        print(f"Green: {greenPressed}, Blue: {bluePressed}, ExtKill: {extKillState}, IntKill: {intKillState}, Depth: {depth:.6f} m")
        
