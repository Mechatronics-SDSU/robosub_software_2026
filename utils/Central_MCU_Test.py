import serial
import struct
from modules.logger.logger import Logger

# Define the USB COM port and baud rate
usb_port = 'COM4'  # Change as needed
baud_rate = 115200

# Initialize the serial connection
ser = serial.Serial(usb_port, baud_rate)
logger = Logger()

# Function to transmit 32-bit numbers over USB
def transmit_32bit_numbers(numbers):
    packed_data = b''
    for number in numbers:
        packed_data += struct.pack('<i', number)  # Little-endian signed 32-bit
    ser.write(packed_data)
    logger.info(f"Transmitted: {numbers}")

try:
    while True:
        user_inputs = []
        
        # Collect 8 motor values
        for i in range(8):
            while True:
                user_input = input(f"Enter motor value {i+1} between -8850 and +8850 (or type 'exit' to quit): ")
                if user_input.lower() == 'exit':
                    logger.info("Exiting...")
                    ser.close()
                    exit(0)
                try:
                    number_to_send = int(user_input)
                    if -8850 <= number_to_send <= 8850:
                        user_inputs.append(number_to_send)
                        break
                    else:
                        logger.warning("Number out of range! Please enter between -8850 and +8850.")
                except ValueError:
                    logger.warning("Invalid input! Please enter an integer.")

        # Motor kill state
        while True:
            user_input = input("Enter motor kill state (1 for kill, 0 for run): ")
            if user_input.lower() == 'exit':
                logger.info("Exiting...")
                ser.close()
                exit(0)
            if user_input in ('0', '1'):
                user_inputs.append(int(user_input))
                break
            else:
                logger.warning("Invalid input! Please enter 0 or 1.")

        # Power off state
        while True:
            user_input = input("Enter power off state (1 to turn off the sub, 0 to keep it on): ")
            if user_input.lower() == 'exit':
                logger.info("Exiting...")
                ser.close()
                exit(0)
            if user_input in ('0', '1'):
                user_inputs.append(int(user_input))
                break
            else:
                logger.warning("Invalid input! Please enter 0 or 1.")

        # RGB values
        for color in ["red", "green", "blue"]:
            while True:
                user_input = input(f"Enter {color} value: ")
                if user_input.lower() == 'exit':
                    logger.info("Exiting...")
                    ser.close()
                    exit(0)
                try:
                    number_to_send = int(user_input)
                    user_inputs.append(number_to_send)
                    break
                except ValueError:
                    logger.warning("Invalid input! Please enter an integer.")

        # Transmit all 13 values (8 motors + 2 flags + 3 RGB)
        transmit_32bit_numbers(user_inputs)

finally:
    ser.close()
    logger.info("Serial connection closed.")
