from modules.motors.kill_motors             import kill_motors
from start                                  import shared_memory
import time

#soft kills sub

shared_memory_object = shared_memory
shared_memory_object.running.value = 0
time.sleep(0.5)
kill_motors()