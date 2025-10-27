This is the TRAX python wrapper class to interface with the PNI TRAX 2 AHRSE sensor.
Please refer to Chapter 7 'Operation with PNI Binary Protocol' of the data sheet:
https://www.pnisensor.com/wp-content/uploads/TRAX2-User-Manual.pdf

SETUP
    To use this wrapper class, start with the following:\ntrax = TRAX()\ntrax.connect()\n#your code here\ntrax.close()
SENDING DATA
    trax.send_packet(frame ID, payload)
    Usage: frame ID should be an int from the table or the string name of the command, and payload should be a tuple or array of values.
    This function returns nothing.
RECEIVING DATA
    trax.recv_packet()\nUsage: In most cases, you can leave the parameters empty. If the command says it has ID specific values, just pass the payload from whatever previous command this one is answering.
    This function returns a tuple of values according to the datagram in the data sheet.
DATAGRAM
[    byte count uint16 ] [ frame ID uint8 ] [ payload (optional) ] [ CRC uint16 ]