
from modem_driver import M16

# For testing
PORT = input("Please input the port where the modem is connected (e.g. COM3 or /dev/ttyUSB0): ")

CHANNEL = 1
# POWER_LEVEL always 1
# No need to change
POWER_LEVEL = 1
DIAGNOSTIC_MODE = False

# Initialize the modem
modem = M16(PORT, baudrate=9600, channel=CHANNEL, level=POWER_LEVEL, diagnostic=DIAGNOSTIC_MODE)

print(f"Starting loop, \nexit with ctrl + c")
while True:
    packet = modem.read_packet()
    if packet is not None:    
        print(f"Received: {str(packet)}")
