import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from modules.servos.ServoWrapper import ServoWrapper
from modules.motors.MotorWrapper import MotorWrapper
from shared_memory import SharedMemoryWrapper

"""
    discord: @alicvo
    github: @alicvo

    Simple CLI for testing servo-based subsystem PWM commands.
    Updates shared memory through ServoWrapper, then sends the full USB packet
    through MotorWrapper.send_command().
"""

shared_memory_object = SharedMemoryWrapper()
M = MotorWrapper(shared_memory_object)
S = ServoWrapper(shared_memory_object)

if __name__ == "__main__":

    while True:
        command = input("\nEnter servo command: ").lower()

        if command == "q":
            break

        elif command == "dd":
            S.dropper("drop")

        elif command == "dr":
            S.dropper("reset")

        elif command == "g1o":
            S.grabber1("open")

        elif command == "g1c":
            S.grabber1("close")

        elif command == "g2o":
            S.grabber2("open")

        elif command == "g2c":
            S.grabber2("close")

        elif command == "tf":
            S.torpedo("fire")

        elif command == "tr":
            S.torpedo("reset")

        elif command == "set":
            subsystem = input("Enter subsystem (dropper, grabber1, grabber2, torpedo): ").lower()
            pwm = int(input("Enter PWM value: "))
            S.set_pwm(subsystem, pwm)

        elif command == "help":
            print("Available commands:")
            print("  dd  - Dropper Drop")
            print("  dr  - Dropper Reset")
            print("  g1o - Grabber 1 Open")
            print("  g1c - Grabber 1 Close")
            print("  g2o - Grabber 2 Open")
            print("  g2c - Grabber 2 Close")
            print("  tf  - Torpedo Fire")
            print("  tr  - Torpedo Reset")
            print("  set - Set custom PWM value for a subsystem")
            print(" help - Show this help message")
            print("  q   - Quit the program")
        else:
            print("Invalid command")
            continue

        M.send_command()
