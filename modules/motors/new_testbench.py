from MotorWrapper import *

M = MotorWrapper()

for i in range(8):
    d = input("Enter direction (e.g. f, b, tl, rr): ").lower()

    if d == "f":
        v = int(input("Give a speed [-4200, 4200]: "))
        M.move_forward(v)
    elif d == "b":
        v = int(input("Give a speed [-4200, 4200]: "))
        M.move_backward(v)
    elif d == "l":
        v = int(input("Give a speed [-4200, 4200]: "))
        M.move_left(v)
    elif d == "r":
        v = int(input("Give a speed [-4200, 4200]: "))
        M.move_right(v)
    elif d == "u":
        v = int(input("Give a speed [-4200, 4200]: "))
        M.move_up(v)
    elif d == "d":
        v = int(input("Give a speed [-4200, 4200]: "))
        M.move_down(v)
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
