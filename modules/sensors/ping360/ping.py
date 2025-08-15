from brping import Ping360
import numpy as np
import matplotlib.pyplot as plt
import struct
from brping import definitions
import sys

"""

If the coin lands on HEADS, the AUV is positioned approximately parallel to the gate.  

If the coin lands on TAILS, the AUV is positioned with its tail approximately facing the gate (the AUV is backward).

"""

def get_angle(row):
    angle = row * 0.9   # 1 radian = 0.9 degrees
    return angle

def get_distance(col):
    distance_per_sample = (speed_of_sound * sample_period) / 2
    distance = distance_per_sample * col
    return distance # in meters

BAUD_RATE = 115200 
device = "/dev/ttyUSB0"
sample_period = 225 # 1 tick = 2 us, so 225 ticks = 450 us
num_samples = 1200
speed_of_sound = 1500 # speed of sound in m/s
transmit_frequency = 800 # in kHz

myPing360 = Ping360()

try:
    myPing360.connect_serial(device, BAUD_RATE) 
except:
    print("Failed to connect to Ping360 device")
    exit(1)

try:
    myPing360.initialize()
    print("Ping360 initialized successfully")
except:
    print("Failed to initialize Ping360")
    exit(1)

myPing360.set_sample_period(sample_period)
myPing360.set_number_of_samples(num_samples)
myPing360.set_transmit_frequency(transmit_frequency)

scan_data = []

for angle in range(0, 400, 10):  
    myPing360.transmitAngle(angle)
    data = myPing360._data
    if data:
        scan_data.append(list(data))
    else:
        print("No data received for angle:", angle)

scan = np.array(scan_data)
np.set_printoptions(threshold=sys.maxsize)
print(scan_data)

N = 110
scan[:, :N] = 0 # filter out noise from the pinger itself

row_sums = []

for row in range(len(scan)): 
    sum = np.sum(scan[row])   # sum the values at each angle row
    row_sums.append(sum)

quarter_sum  = 0
angle_index = 0

for angle in range(0, 40): 
    if np.sum(row_sums[angle:angle+10]) > quarter_sum:
        quarter_sum = np.sum(row_sums[angle:angle+10])
        angle_index = angle*10 + 50 # midpoint of the quarter
print("angle index: ", angle_index)

wall_forward = False
wall_left = False
wall_right = False
wall_back = False

if angle_index <= 50 or angle_index >= 350:
    wall_forward = True
elif angle_index > 50 and angle_index < 150:
    wall_right = True
elif angle_index >= 150 and angle_index < 250:
    wall_back = True
elif angle_index >= 250 and angle_index < 350:
    wall_left = True

print("Wall forward:", wall_forward)
print("Wall right:", wall_right)
print("Wall backward:", wall_back)
print("Wall left:", wall_left)

