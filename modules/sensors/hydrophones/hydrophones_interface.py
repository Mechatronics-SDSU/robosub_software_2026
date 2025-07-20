from sensors.hydrophones.hydrophones import Hydrophone

class Hydrophone_Interface:

    def __init__(self, shared_memory_object):
        self.shared_memory_object = shared_memory_object
        self.hydrophone = Hydrophone()

    def update(self):
        return

    def run_loop(self):
        self.update()
        while self.shared_memory_object.running.value:
            self.update()
            