from MotorWrapper import *

SharedMemoryWrapper = SharedMemoryWrapper()
M = MotorWrapper(SharedMemoryWrapper)

for i in range(8):
    d = input("Enter direction (e.g. f, b, tl, rr): ").lower()

    if d == "f":
        v = int(input("Give a speed [-4200, 4200]: "))
        M.move_from_matrix(np.array([M.valid(v), 0, 0, 0, 0, 0]))
    elif d == "b":
        v = int(input("Give a speev [-4200, 4200]: "))
        M.move_from_matrix(np.array([M.valid(-v), 0, 0, 0, 0, 0]))
    elif d == "l":
        v = int(input("Give a speed [-4200, 4200]: "))
        M.move_from_matrix(np.array([0, M.valid(v), 0, 0, 0, 0]))
    elif d == "r":
        v = int(input("Give a speed [-4200, 4200]: "))
        M.move_from_matrix(np.array([0, M.valid(v), 0, 0, 0, 0]))
    elif d == "u":
        v = int(input("Give a speed [-4200, 4200]: "))
        M.move_from_matrix(np.array([0, 0, M.valid(v), 0, 0, 0]))
    elif d == "d":
        v = int(input("Give a speed [-4200, 4200]: "))
        M.move_from_matrix(np.array([0, 0, M.valid(-v), 0, 0, 0]))
    elif d == "tu":
        v = int(input("Give a speed [-4200, 4200]: "))
        M.turn_up(v)
    elif d == "td":
        v = int(input("Give a speed [-4200, 4200]: "))
        M.turn_down(v)
    elif d == "tl":
        v = int(input("Give a speed [-4200, 4200]: "))
        M.turn_left(v)
    elif d == "tr":
        v = int(input("Give a speed [-4200, 4200]: "))
        M.turn_right(v)
    elif d == "rl":
        v = int(input("Give a speed [-4200, 4200]: "))
        M.roll_left(v)
    elif d == "rr":
        v = int(input("Give a speed [-4200, 4200]: "))
        M.roll_right(v)
    elif d == "s":
        M.stop()
    else:
        print("Invalid direction! Please enter a valid command.")

    M.send_command()
