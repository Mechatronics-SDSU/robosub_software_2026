from modules.sensors.depth_sensor.depth_sensor import DepthSensor
from multiprocessing import Value

class DepthSensorInterface:
    def __init__(self, shared_memory_object):
        self.depth_sensor = DepthSensor()
        self.shared_memory_object = shared_memory_object
        self.last_shared = 0

    def update(self):
        depth = self.depth_sensor.receive_data()
        try:
            len(depth)
        except:
            return

        if depth != None and len(depth) > 3:
            # print(depth)
            try:
                self.shared_memory_object.depth.value = float(depth)
                self.last_shared = float(depth)
            except:
                self.shared_memory_object.depth.value = self.last_shared

    def print_data(self):
        print(self.shared_memory_object.depth.value)

    def run_loop(self):
        while self.shared_memory_object.running.value:
            self.update()
