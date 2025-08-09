import time

class Test_Process:
    def __init__(self, shared_memory_object):
        self.shared_memory_object = shared_memory_object


    def run_loop(self):
        while self.shared_memory_object.running.value:
            #write code here

            print("Test Process Running")
            time.sleep(1)

            #end
            pass