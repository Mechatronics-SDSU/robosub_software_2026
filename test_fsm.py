from multiprocessing                        import Process, Value
from shared_memory                          import SharedMemoryWrapper
from modules.pid.pid_interface              import PIDInterface
from modules.sensors.a50_dvl.dvl_interface  import DVL_Interface
"""
    discord: @.kech
    github: @rsunderr

    Test FSM
    
"""
class Test_FSM:
    def __init__(self):
        self.active = False
        # create shared memory
        self.shared_memory_object = SharedMemoryWrapper()
        self.x_buffer = 0.2#m
        self.y_buffer = 0.2#m
        self.z_buffer = 0.6#m
        # initial state (S1, S2)
        self.state = "S1"

        # create objects
        self.PID_interface = PIDInterface(self.shared_memory_object)
        self.dvl_object = DVL_Interface(self.shared_memory_object)        
                
        # create processes
        self.PID_process = Process(target=self.PID_interface.run_loop)
        self.dvl_process = Process(target=self.dvl_object.run_loop)

    def start(self):
        self.active = True
        # set initial target coords
        self.shared_memory_object.target_x.value = 2#m
        self.shared_memory_object.target_y.value = 0#m
        self.shared_memory_object.target_z.value = 1#m

        # start processes
        self.PID_process.start()
        self.dvl_process.start()

    def next_state(self, next):
        if self.state == next: return
        self.state = next
        match(self.state):
            case "S1":
                self.shared_memory_object.target_x.value = 2#m
                self.shared_memory_object.target_y.value = 0#m
                self.shared_memory_object.target_z.value = 1#m
            case "S2":
                self.shared_memory_object.target_x.value = 0#m
                self.shared_memory_object.target_y.value = 0#m
                self.shared_memory_object.target_z.value = 1#m
            case _:
                print("invalid state")

    def loop(self):
        if not self.active: return
        if abs(self.shared_memory_object.dvl_x.value - self.shared_memory_object.target_x.value) <= self.x_buffer and abs(self.shared_memory_object.dvl_y.value - self.shared_memory_object.target_y.value) <= self.y_buffer and abs(self.shared_memory_object.dvl_z.value - self.shared_memory_object.target_z.value) <= self.z_buffer:
            next = "S1" if self.state == "S2" else "S2"
            self.next_state(next)

    def join(self):
        if not self.active: return
        # join processes
        self.PID_process.join()
        self.dvl_process.join()

    def stop(self):
        self.active = False
        # terminate processes
        self.PID_process.terminate()
        self.dvl_process.terminate()
