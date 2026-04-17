from modem_driver import M16
from time import sleep

# PORT = input("Please input the port where the modem is connected (e.g. COM3 or /dev/ttyUSB0): ")

PORT = "COM9"
CHANNEL = 1
POWER_LEVEL = 1
DIAGNOSTIC_MODE = False

# Initialize the modem
modem = M16(PORT, baudrate=9600, channel=CHANNEL, level=POWER_LEVEL, diagnostic=DIAGNOSTIC_MODE)

# Send two bytes with the modem
binary = 0b00001
bytes = (binary << 10) | (binary << 5) | (binary << 1) | 1

# bytes = (binary << 10) | (0b01001 << 5) | 0b00001

two_bytes = bytes.to_bytes(2, byteorder='big')
modem.send_two_bytes(two_bytes)
print(f"Sent {two_bytes} on channel {CHANNEL}")

# Close the modem
modem.close()