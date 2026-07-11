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


#original version - manually submit values everyrun

# try:
#     while True:
#         user_inputs = []
#
#         # Collect 8 motor values
#         for i in range(8):
#             while True:
#                 user_input = input(f"Enter motor value {i} between -8500 and +8500 (or 'exit' to quit): ")
#                 if user_input.lower() == 'exit':
#                     print("Exiting...")
#                     raise SystemExit
#                 try:
#                     number_to_send = int(user_input)
#                     if -8500 <= number_to_send <= 8500:
#                         user_inputs.append(number_to_send)
#                         break
#                     else:
#                         print("Number out of range! Please enter between -8500 and +8500.")
#                 except ValueError:
#                     print("Invalid input! Please enter an integer.")
#
#         # Kill state
#         while True:
#             user_input = input("Enter kill state (1 = kill, 0 = run): ")
#             if user_input.lower() == 'exit':
#                 print("Exiting...")
#                 raise SystemExit
#             if user_input in ('0', '1'):
#                 user_inputs.append(int(user_input))
#                 break
#             else:
#                 print("Invalid input! Please enter 0 or 1.")
#
#         # Power off state
#         while True:
#             user_input = input("Enter power off state (1 = off, 0 = on): ")
#             if user_input.lower() == 'exit':
#                 print("Exiting...")
#                 raise SystemExit
#             if user_input in ('0', '1'):
#                 user_inputs.append(int(user_input))
#                 break
#             else:
#                 print("Invalid input! Please enter 0 or 1.")
#
#         # Servo 1
#         while True:
#             user_input = input("Enter servo 1 value (or 'exit' to quit): ")
#             if user_input.lower() == 'exit':
#                 print("Exiting...")
#                 raise SystemExit
#             try:
#                 user_inputs.append(int(u,ser_input))
#                 break
#             except ValueError:
#                 print("Invalid input! Please enter an integer.")
#
#         # Servo 2
#         while True:
#             user_input = input("Enter servo 2 value (or 'exit' to quit): ")
#             if user_input.lower() == 'exit':
#                 print("Exiting...")
#                 raise SystemExit
#             try:
#                 user_inputs.append(int(user_input))
#                 break
#             except ValueError:
#                 print("Invalid input! Please enter an integer.")
#
#         # Dropper
#         while True:
#             user_input = input("Enter dropper state (1 = closed, 0 = open): ")
#             if user_input.lower() == 'exit':
#                 print("Exiting...")
#                 raise SystemExit
#             if user_input in ('0', '1'):
#                 user_inputs.append(int(user_input))
#                 break
#             else:
#                 print("Invalid input! Please enter 0 or 1.")
#
#         # Torpedo
#         while True:
#             user_input = input("Enter torpedo state (1 = fire, 0 = armed): ")
#             if user_input.lower() == 'exit':
#                 print("Exiting...")
#                 raise SystemExit
#             if user_input in ('0', '1'):
#                 user_inputs.append(int(user_input))
#                 break
#             else:
#                 print("Invalid input! Please enter 0 or 1.")
#
#         # Transmit all 14 values
#         transmit_32bit_numbers(user_inputs)
#
# finally:
#     ser.close()
#     print("Serial connection closed.")
 



#automatic version - im tired of putting values in every damn time 

try:
    while True:

        user_inputs = [
            1600, # motor 0
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
            1000,     # dropper     (1000 = closed/est, 1400 = open)
            1500,     # torpedo     (1000 fires right, 1900 fires left, ~1500 is armed/flat)
        ]

        transmit_32bit_numbers(user_inputs)

        time.sleep(5)

finally:
    ser.close()
    print("Serial connection closed.")