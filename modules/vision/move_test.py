"""
Quick movement test — forward, right, down in small increments.
Run directly: python move_test.py

Requires the USB motor controller to be connected.
Set MOTOR_FACTOR in MotorWrapper.py before running:
  ~0.1 for in-air testing
  ~0.3 for in-water testing
"""

import sys
import os
import time

# Resolve paths to repo root and motors module
_root   = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
_motors = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'motors'))
sys.path.insert(0, _root)
sys.path.insert(0, _motors)

from shared_memory import SharedMemoryWrapper
from MotorWrapper import MotorWrapper

# ── CONTROL PANEL ────────────────────────────────────────────
THRUST    = 300   # raw motor value (max 4000; scaled by MOTOR_FACTOR in MotorWrapper)
DURATION  = 1.0   # seconds per move
SEQUENCE  = [
    ("forward", THRUST),
    ("forward", THRUST),
    ("right",   THRUST),
    ("right",   THRUST),
    ("down",    THRUST),
    ("down",    THRUST),
]
# ─────────────────────────────────────────────────────────────

sm     = SharedMemoryWrapper()
motors = MotorWrapper(sm)

DISPATCH = {
    "forward":  motors.move_forward,
    "backward": motors.move_backward,
    "left":     motors.move_left,
    "right":    motors.move_right,
    "up":       motors.move_up,
    "down":     motors.move_down,
    "yaw_left": motors.turn_left,
    "yaw_right":motors.turn_right,
}

print("Starting movement sequence. Ctrl+C to abort.")

try:
    for direction, value in SEQUENCE:
        print(f"  {direction} @ {value}")
        deadline = time.time() + DURATION
        while time.time() < deadline:
            DISPATCH[direction](value)
            motors.send_command()
            time.sleep(0.05)  # 20 Hz command rate
        motors.stop()
        motors.send_command()
        time.sleep(0.2)       # brief pause between moves

except KeyboardInterrupt:
    print("Aborted.")

finally:
    motors.stop()
    motors.send_command()
    print("Motors zeroed.")
