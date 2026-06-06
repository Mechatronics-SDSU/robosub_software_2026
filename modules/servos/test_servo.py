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
    print("Servo tester commands:")
    print("  dd  = dropper drop")
    print("  dr  = dropper reset")
    print("  g1o = grabber 1 open")
    print("  g1c = grabber 1 close")
    print("  g2o = grabber 2 open")
    print("  g2c = grabber 2 close")
    print("  tf  = torpedo fire")
    print("  tr  = torpedo reset")
    print("  set = manually set PWM by subsystem name")
    print("  q   = quit")

    while True:
        command = input("\nEnter servo command: ").lower()

        if command == "q":
            break

        elif command == "dd":
            S.dropper_drop()

        elif command == "dr":
            S.dropper_reset()

        elif command == "g1o":
            S.grabber1_open()

        elif command == "g1c":
            S.grabber1_close()

        elif command == "g2o":
            S.grabber2_open()

        elif command == "g2c":
            S.grabber2_close()

        elif command == "tf":
            S.torpedo_fire()

        elif command == "tr":
            S.torpedo_reset()

        elif command == "set":
            subsystem = input("Enter subsystem (dropper, grabber1, grabber2, torpedo): ").lower()
            pwm = int(input("Enter PWM value: "))
            S.set_pwm(subsystem, pwm)

        else:
            print("Invalid command")
            continue

        M.send_command()