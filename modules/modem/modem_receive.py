"""
This script continuously listens for packets from the modem. It converts the received packet into a binary string, checks the last bit to determine if the packet should be processed, and then splits the binary string into 5-bit chunks. The script uses a majority voting mechanism on the first three 5-bit chunks to determine a trusted chunk, which is then printed to the console. If there is no majority match among the three chunks, it indicates that all chunks differ.
"""

from modem_driver import M16

# Configuration parameters for the modem
PORT = "COM7"
CHANNEL = 1
POWER_LEVEL = 1
DIAGNOSTIC_MODE = False

modem = M16(PORT, baudrate=9600, channel=CHANNEL, level=POWER_LEVEL, diagnostic=DIAGNOSTIC_MODE)

print("Starting loop, exit with ctrl + c")

last_chunk = None
repeat_count = 0
listening = True

#Need to update once we figure out how we want to write the task codes

while listening and modem.is_connected():
    packet = modem.read_packet()

    if packet is None:
        continue

    # Convert packet bytes to one long binary string
    binary_string = ''.join(f'{byte:08b}' for byte in packet)

    last_bit = binary_string[-1]

    if(last_bit == '0'):
        print("Received a packet with last bit 0, ignoring")
        continue
    else:
        binary_string = binary_string[:-1]

        print(f"Trimmed binary: {binary_string}")

        # Split into 5-bit chunks
        chunks = [binary_string[i:i+5] for i in range(0, len(binary_string), 5)]

        # Keep only full 5-bit chunks
        chunks = [chunk for chunk in chunks if len(chunk) == 5]

        # We only care about the first 3 chunks for majority voting
        if len(chunks) < 3:
            print("Not enough 5-bit chunks received")
            continue

        chunk1, chunk2, chunk3 = chunks[:3]


        # Majority vote logic
        if chunk1 == chunk2 or chunk1 == chunk3:
            trusted_chunk = chunk1
        elif chunk2 == chunk3:
            trusted_chunk = chunk2
        else:
            trusted_chunk = None

        if trusted_chunk is not None:
            print(f"Trusted chunk: {trusted_chunk}")
            listening = False
            modem.close()
        else:
            print("No majority match found, all 3 chunks differ")
            listening = False
            modem.close()