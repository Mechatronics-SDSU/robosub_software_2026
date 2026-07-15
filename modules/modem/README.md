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
    - Ported from the Waterlinked reference M16 driver.
    - Messages are plain text, sent in 2-character chunks via transparent mode.
    - Receiving reads whatever raw bytes arrive in a given window (diagnostic
      report packets are the exception: framed with a leading '$' and
      trailing '\n', fixed 18 bytes).


### Status

- Current status: Complete
- Last updated: 07/10/2026