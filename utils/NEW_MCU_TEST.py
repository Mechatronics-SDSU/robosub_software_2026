import serial
import struct
import threading
import time

# Define the USB COM port and baud rate
# Change as needed

#windows - 'COM*'
#debian - '/dev/ttyACM*' 

usb_port = '/dev/ttyACM0'
baud_rate = 115200

# Initialize the serial connection
ser = serial.Serial(usb_port, baud_rate, timeout=6)

# RX Thread for debugging - lets make sure that my usbBuffer is being completely filled the first time
def read_from_stm32():
    last = None

    while True:
        try:
            data = ser.readline()

            if data and data != last:
                print(f"\n[STM32 RAW] {repr(data)}")
                last = data

        except Exception as e:
            print(f"[RX ERROR] {e}")
            break

# Start background reader
rx_thread = threading.Thread(target=read_from_stm32, daemon=True)
rx_thread.start()

# Function to transmit 32-bit numbers over USB
def transmit_32bit_numbers(numbers):
    packed_data = b''
    for number in numbers:
        packed_data += struct.pack('<i', number)  # Little-endian signed 32-bit
    ser.write(packed_data)
    ser.flush()
    print(f"Transmitted: {numbers}")

try:
    while True:

        user_inputs = [
            1500, # motor 0
            1500,  # motor 1
            1500,  # motor 2
            1500,  # motor 3
            1500,  # motor 4
            1500,  # motor 5
            1500,  # motor 6
            1500,  # motor 7
            0,     # motor kill state (0 = alive, 1 = kill)
            0,     # power off state  (0 = on, 1 = off)
            0,     # servo 1 - pin30
            0,     # servo 2 - pin 29
            1400,     # dropper     (1000 = closed/est, 1400 = open)
            1500,     # torpedo     (1000 fires right, 1900 fires left, ~1500 is armed/flat)
            int(b'01000000000000', 2) #int(b'00000011111111', 2) # bitmask (8 bits for motors, 6 bits for other controls)
        ]

        transmit_32bit_numbers(user_inputs)

        time.sleep(5)

finally:
    ser.close()
    print("Serial connection closed.")