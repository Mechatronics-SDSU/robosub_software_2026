# Modems
Program to control the M16 modem, which is used for communication between the subs.

### Outline

- Date Created: 02/26/2026
- Contributors:
    - Andy Chen (GitHub: @AndyC534, Discord: @creatine4053)
- Dependencies:
    - Pyserial 3.5


### Key Files

- modem_driver.py
    - The library for controlling the M16 modem, providing methods for configuring the modem, sending commands, reading diagnostic packets, and decoding them.

- modem_comms.py
    - This script will either run a listener sub script or a transmitter sub script


### Usage



### Notes

- Set LEVEL to 1
- Set BAUDRATE to 9600

- Protocol:
    - A message is one 5-bit code.
    - The 5-bit code is repeated three times for majority voting.
    - The final least-significant bit is set to 1 as the valid-message bit.
    - Total size: 5 + 5 + 5 + 1 = 16 bits = 2 bytes.


### Status

- Current status: Complete
- Last updated: 06/2/2026