from multiprocessing                        import Process, Value
from shared_memory                          import SharedMemoryWrapper
from modules.pid.pid_interface              import PIDInterface
from modules.sensors.a50_dvl.dvl_interface  import DVL_Interface
"""
    discord: @.kech
    github: @rsunderr

    Test FSM
    
"""
class Spin_FSM:
    def __init__(self, shared_memory_object):
        self.active = False
        # create shared memory
        self.shared_memory_object = shared_memory_object
        # buffers
        self.buffer = 15#deg
        # initial state (S1, S2)
        self.state = "S0"

        # create objects
        self.PID_interface = PIDInterface(self.shared_memory_object)
        self.dvl_object = DVL_Interface(self.shared_memory_object)
                
        # create processes
        self.PID_process = Process(target=self.PID_interface.run_loop)
        self.dvl_process = Process(target=self.dvl_object.run_loop)

    # start FSM
    def start(self):
        self.active = True

        # start processes
        self.PID_process.start()
        self.dvl_process.start()

        # set initial state
        self.next_state("S1")

    # change to next state
    def next_state(self, next):
        if self.state == next: return # do nothing if no state change
        match(next):
            case "S1":
                self.shared_memory_object.target_yaw.value = 90#m
            case "S2":
                self.shared_memory_object.target_yaw.value = -90#m
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
        next = None # next state local
        # transitions
        match(self.state):
            case "S1":
                if abs(self.shared_memory_object.dvl_yaw.value - 90) <= self.buffer:    next = "S2"
            case "S2":
                if abs(self.shared_memory_object.dvl_yaw.value - -90) <= self.buffer:   next = "DONE"
            case _:
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
