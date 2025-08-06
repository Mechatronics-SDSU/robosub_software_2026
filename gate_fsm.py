from multiprocessing                        import Process, Value
from shared_memory                          import SharedMemoryWrapper
from modules.pid.pid_interface              import PIDInterface
from modules.vision.vision_main             import VideoRunner
from modules.sensors.a50_dvl.dvl_interface  import DVL_Interface
"""
    discord: @.kech
    github: @rsunderr

    Test FSM
    
"""
class Gate_FSM:
    def __init__(self, shared_memory_object):
        self.active = False
        # create shared memory
        self.shared_memory_object = shared_memory_object
        # buffers
        self.x_buffer = 0.3#m
        self.y_buffer = 0.3#m
        self.z_buffer = 0.5#m
        # initial state (INIT, DRIVE, DONE)
        self.state = "INIT"

        # create objects
        self.PID_interface = PIDInterface(self.shared_memory_object)
        self.dvl_object = DVL_Interface(self.shared_memory_object)
        self.vis_object = VideoRunner(self.shared_memory_object)
                
        # create processes
        self.PID_process = Process(target=self.PID_interface.run_loop)
        self.dvl_process = Process(target=self.dvl_object.run_loop)
        self.vis_process = Process(target=self.vis_object.run_loop)

    # start FSM
    def start(self):
        self.active = True

        # start processes
        self.PID_process.start()
        self.dvl_process.start()
        self.vis_process.start()

        # set initial state
        self.next_state("DRIVE")

    # change to next state
    def next_state(self, next):
        if self.state == next: return # do nothing if no state change
        match(next):
            case "DRIVE":
                self.shared_memory_object.target_x.value = 3#m TODO make us read from a file
                self.shared_memory_object.target_y.value = 0#m
                self.shared_memory_object.target_z.value = 1#m
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
                if abs(self.shared_memory_object.dvl_x.value - self.shared_memory_object.target_x.vlaue) <= self.x_buffer and abs(self.shared_memory_object.dvl_y.value - self.shared_memory_object.target_y.value) <= self.y_buffer and abs(self.shared_memory_object.dvl_z.value - self.shared_memory_object.target_z.value) <= self.z_buffer:
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
        self.vis_process.join()

    # stop FSM
    def stop(self):
        self.active = False
        # terminate processes
        self.PID_process.terminate()
        self.dvl_process.terminate()
        self.vis_process.terminate()