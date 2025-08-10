from brping import Ping360
import numpy as np
import matplotlib.pyplot as plt

BAUD_RATE = 115200 
device = "/dev/ttyUSB0"
sample_period = 80 # in microseconds, 6 cm distance per sample
num_samples = 1000
speed_of_sound = 1500000 # speed of sound in cm/s

def get_angle(row):
    angle = row * 0.9
    return angle

def get_distance(col):
    distance_per_sample = (speed_of_sound * sample_period) / 2000
    distance = distance_per_sample * col / 10000
    return distance # in cm

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

print(myPing360.set_sample_period(sample_period))
print(myPing360.set_number_of_samples(num_samples))

scan_data = []

for angle in range(0, 400):  # 0.9 degree steps
    msg = myPing360.transmitAngle(angle)
    buffer = myPing360.get_device_data()
    if buffer:
        data = np.frombuffer(buffer['data'], dtype=np.uint8) 
        scan_data.append(data)
    else:
        print("No data received for angle:", angle)
        print(f"Message: {msg}")

img = np.array(scan_data)

num_angles = 400
num_samples = 500

# Example: simulate the dimensions
num_angles, num_ranges = img.shape

# Create theta (angle) and r (range) arrays
theta = np.linspace(0, 2 * np.pi, num_angles)  # full circle (360°)
r = np.arange(num_ranges)

# Create meshgrid for polar coordinates
theta_grid, r_grid = np.meshgrid(theta, r, indexing='ij')

# Plot in polar coordinates
fig = plt.figure(figsize=(8, 6))
ax = fig.add_subplot(111, polar=True)

# Normalize for better contrast
normalized_image = img / np.max(img)

# Plot using colormap
c = ax.pcolormesh(theta_grid, r_grid, normalized_image, cmap='hot')

# Add colorbar and title
plt.colorbar(c, label='Normalized Intensity')
ax.set_title('Ping 360 Visualization')
plt.show()
