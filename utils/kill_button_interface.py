import can
from multiprocessing import Process, Value

"""
    discord: @kialli
    github: @kchan5071

    Makes kill button end processes gracefully

"""

class Kill_Button_Interface:
    def __init__(self, shared_memory_object):
            self.shared_memory_object = shared_memory_object
            self.filters = [{"can_id": 0x007, "can_mask": 0x7FF}]
            self.bus = can.Bus(interface='socketcan',channel = 'can0', receive_own_messages=True, can_filters = self.filters)


    def run_loop(self):
        while self.shared_memory_object.running.value:
            message = self.bus.recv()
            if message == None:
                continue
            data = message.data
            if data[0] == None:
                continue
            if message.arbitration_id == 0x007:
                if data[0] == 0:
                    self.shared_memory_object.running.value = False
                    print("DEAD")