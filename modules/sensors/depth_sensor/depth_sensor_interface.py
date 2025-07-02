from modules.sensors.depth_sensor import DepthSensor
from multiprocessing import Value

class DepthSensorInterface:
    def __init__(self, shared_memory_object):
        self.depth_sensor = DepthSensor()
        self.shared_memory_object = shared_memory_object

    def update(self):
        depth = self.depth_sensor.recieve_data()
        if depth != None and len(depth) > 3:
            if"Depth" in depth:
                print(float(depth[depth.find(" ") + 1:]))
                self.shared_memory_object.depth.value = float(depth[depth.find(" ") + 1:])

    def print_data(self):
        print(self.shared_memory_object.depth.value)

    def run_loop(self):
        while self.shared_memory_object.running.value:
            self.update()
