from multiprocessing                        import Process, Value
from shared_memory                          import SharedMemoryWrapper
from modules.pid.pid_interface              import PIDInterface
from modules.sensors.a50_dvl.dvl_interface  import DVL_Interface
import yaml
"""
    discord: @.kech
    github: @rsunderr

    Gate FSM
    
"""
class Octagon_FSM:
    def __init__(self, shared_memory_object):
        self.active = False
        # create shared memory
        self.shared_memory_object = shared_memory_object

        # initial state (INIT, DRIVE, RISE, DONE)
        self.state = "INIT"

        # create objects
        self.PID_interface = PIDInterface(self.shared_memory_object)
        self.dvl_object = DVL_Interface(self.shared_memory_object)
                
        # create processes
        self.PID_process = Process(target=self.PID_interface.run_loop)
        self.dvl_process = Process(target=self.dvl_object.run_loop)

        # buffers
        self.x_buffer = 0.3#m
        self.y_buffer = 0.3#m
        self.z_buffer = 0.5#m

        # target values
        self.x1, self.y1, self.z1, self.z2 = (None, None, None, None)
        with open("~/robosub_software_2025/objects.yaml", 'r') as file:
            data = yaml.safe_load(file)
            self.x1 = data['objects']['gate']['x']
            self.y1 = data['objects']['gate']['y']
            self.z1 = 1
            self.z2 = data['objects']['gate']['z']

    # start FSM
    def start(self):
        self.active = True

        # start processes
        self.PID_process.start()
        self.dvl_process.start()

        # set initial state
        self.next_state("DRIVE")

    # change to next state
    def next_state(self, next):
        if self.state == next: return # do nothing if no state change
        match(next):
            case "DRIVE":
                self.shared_memory_object.target_x.value = self.x1
                self.shared_memory_object.target_y.value = self.y1
                self.shared_memory_object.target_z.value = self.z1
            case "RISE":
                self.shared_memory_object.target_z.value = self.z2
            case "DONE":
                print("DONE")
                self.stop()
                return
            case _: # do nothing if invalid state
                print("invalid state")
                return
        self.state = next
    
    # loop function
    def loop(self):
        if not self.active: return # do nothing if not enabled
        next = None
        # transitions
        match(self.state):
            case "DRIVE":
                if abs(self.shared_memory_object.dvl_x.value - self.x1) <= self.x_buffer and abs(self.shared_memory_object.dvl_y.value - self.y1) <= self.y_buffer and abs(self.shared_memory_object.dvl_z.value - self.shared_memory_object.z1) <= self.z_buffer:
                    next = "RISE"
            case "RISE":
                if abs(abs(self.shared_memory_object.dvl_z.value - self.z2) <= self.z_buffer):
                    next = "DONE"
            case _: # do nothing if invalid state
                print("invalid state")
                return
        self.next_state(next)

    # wait until child processes terminate
    def join(self):
        if not self.active: return
        # join processes
        self.PID_process.join()
        self.dvl_process.join()

    # stop FSM
    def stop(self):
        self.active = False
        # terminate processes
        self.PID_process.terminate()
        self.dvl_process.terminate()
