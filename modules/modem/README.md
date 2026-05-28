# Modem
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

- modem_receive.py
    - This script continuously listens for packets from the modem.

- modem_send.py
    - This script sends a predefined binary pattern through the modem.

### Usage

- Create a modem object "M16(PORT, BAUDRATE, CHANNEL, LEVEL, DIAGNOSTIC)"
- Run "read_packet()" to listens from packets from other modems
- Run "send_two_bytes()" to send from 2 bytes of information to other modems

### Notes

- Set LEVEL to 1
- Set BAUDRATE to 9600


### Status

- Current status: In Progress