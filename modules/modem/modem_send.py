from modem_driver import M16
from time import sleep
from datetime import datetime

# For testing
PORT = input("Please input the port where the modem is connected (e.g. COM3 or /dev/ttyUSB0): ")

CHANNEL = 1
POWER_LEVEL = 1
DIAGNOSTIC_MODE = False

# Initialize the modem
modem = M16(PORT, baudrate=9600, channel=CHANNEL, level=POWER_LEVEL, diagnostic=DIAGNOSTIC_MODE)

# Send a message with the modem
msg = str(datetime.today())
modem.send_msg(msg)
print(f"Sent {msg} on channel {CHANNEL}")

# Close the modem
modem.close()