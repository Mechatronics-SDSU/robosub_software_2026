from brping import Ping360
import numpy as np
import matplotlib.pyplot as plt

BAUD_RATE = 115200 
device = '/dev/ttyUSB0'
sample_period = 80 # in microseconds, 6 cm distance per sample
num_samples = 1000

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

for angle in range(0, 400, 10):  # 10 gradians = 9 degree steps
    msg = myPing360.transmitAngle(angle)
    buffer = myPing360.get_device_data()
    if buffer:
        data = np.frombuffer(buffer['data'], dtype=np.uint8) 
        scan_data.append(data)
    else:
        print("No data received for angle:", angle)
        print(f"Message: {msg}")

img = np.array(scan_data)
print(img)

#polar_img = img.T
#print(polar_img)

"""
plt.figure(figsize=(6, 6))
plt.imshow(img, cmap='viridis')
plt.title("Ping360 Sonar Visualization")
plt.xlabel("Angle (deg)")
plt.ylabel("Sample Index (range in m)")
plt.colorbar(label="Echo Strength")
plt.show()

"""
