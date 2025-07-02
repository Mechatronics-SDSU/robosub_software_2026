from sensors.depth_sensor import DepthSensor
from multiprocessing import Value

class DepthSensorInterface:
    def __init__(self, z):
        self.z = z
        self.depth_sensor = DepthSensor()

    def update(self):
        depth = self.depth_sensor.recieve_data()
        if depth != None and len(depth) > 3:
            if"Depth" in depth:
                print(float(depth[depth.find(" ") + 1:]))
                self.z.value = float(depth[depth.find(" ") + 1:])

    def print_data(self):
        print(self.z.value)

    def run_loop(self):
        while True:
            self.update()

if __name__ == "__main__":
    depth_z = Value('d', 0.0)
    depth_sensor_interface = DepthSensorInterface(z=depth_z)
    depth_sensor_interface.run_loop()
