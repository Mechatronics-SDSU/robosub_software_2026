import serial
import struct

# Define the USB COM port and baud rate (adjust according to your setup)
usb_port = '/dev/ttyACM0'  # Use the correct port (e.g., COM3 for Windows)
baud_rate = 115200

# Initialize the serial connection
ser = serial.Serial(usb_port, baud_rate)

# Function to transmit 32-bit numbers over USB
def transmit_32bit_numbers(numbers):
    # Create a list to hold the packed data
    packed_data = b''
    
    for number in numbers:
        # Pack the number as a 32-bit signed integer (little-endian)
        packed_data += struct.pack('<i', number)

    # Transmit the packed data over USB
    ser.write(packed_data)
    print(f"Transmitted: {numbers}")

# Main loop to repeatedly ask for user input
try:
    while True:
        user_inputs = []
        
        # Collect the first 8 values between -8850 and +8850
        for i in range(8):
            user_input = input(f"Enter number {i+1} between -8850 and +8850 (or type 'exit' to quit): ")
            
            if user_input.lower() == 'exit':
                print("Exiting...")
                ser.close()
                print("Serial connection closed.")
                exit(0)

            try:
                number_to_send = int(user_input)
                
                # Check if the input is within the range of -8850 to +8850
                if -8850 <= number_to_send <= 8850:
                    user_inputs.append(number_to_send)
                else:
                    print("Number out of range! Please enter a number between -8850 and +8850.")
                    
            except ValueError:
                print("Invalid input! Please enter a valid integer.")

        # Collect 3 additional values (no range restriction)
        for i in range(3):
            user_input = input(f"Enter additional number {i+1} (32-bit integer, no range restriction): ")
            
            if user_input.lower() == 'exit':
                print("Exiting...")
                ser.close()
                print("Serial connection closed.")
                exit(0)

            try:
                number_to_send = int(user_input)
                # No need for range validation for these 3 additional numbers
                user_inputs.append(number_to_send)
            except ValueError:
                print("Invalid input! Please enter a valid integer.")

        # Transmit all 11 numbers over USB
        transmit_32bit_numbers(user_inputs)

finally:
    # Close the serial connection when done
    ser.close()
    print("Serial connection closed.")
