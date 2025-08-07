from multiprocessing                        import Process, Value
from shared_memory                          import SharedMemoryWrapper
from modules.pid.pid_interface              import PIDInterface
from modules.vision.vision_main             import VideoRunner
from modules.sensors.a50_dvl.dvl_interface  import DVL_Interface
from socket_send                            import set_screen
import yaml
import os
"""
    discord: @.kech
    github: @rsunderr

    FSM for navigating through gate
    
"""
# FSM for gate mode
class Gate_FSM:
    def __init__(self, shared_memory_object):
        # create shared memory
        self.shared_memory_object = shared_memory_object

        # initial state (INIT, DRIVE, DONE)
        self.state = "INIT"
        self.active = False

        # create objects
        self.PID_interface = PIDInterface(self.shared_memory_object)
        self.dvl_object = DVL_Interface(self.shared_memory_object)
        #self.vis_object = VideoRunner(self.shared_memory_object)
        
        # create processes
        self.PID_process = Process(target=self.PID_interface.run_loop)
        self.dvl_process = Process(target=self.dvl_object.run_loop)
        #self.vis_process = Process(target=self.vis_object.run_loop)

        # buffers
        self.x_buffer = 0.3#m
        self.y_buffer = 10#m
        self.z_buffer = 10#m

        # target values
        self.gate_x, self.gate_y, self.gate_z = (None, None, None)
        with open(os.path.expanduser("~/robosub_software_2025/objects.yaml"), 'r') as file: # read from yaml
            data = yaml.safe_load(file)
            self.gate_x = data['objects']['gate']['x']
            self.gate_y = data['objects']['gate']['y']
            self.gate_z = data['objects']['gate']['z']

    # start FSM
    def start(self):
        self.active = True

        # start processes
        self.PID_process.start()
        self.dvl_process.start()
        #self.vis_process.start()

        #set_screen((int(self.shared_memory_object.dvl_x.value), int(self.shared_memory_object.dvl_y.value), int(self.shared_memory_object.dvl_z.value)), "GATE:DRIVE", "yippeeeee")

        # set initial state
        self.next_state("DRIVE")

    # change to next state
    def next_state(self, next):
        if not self.active or self.state == next: return # do nothing if not enabled or no state change
        match(next):
            case "INIT":
                pass
            case "DRIVE":
                self.shared_memory_object.target_x.value = self.gate_x
                self.shared_memory_object.target_y.value = self.gate_y
                self.shared_memory_object.target_z.value = self.gate_z
            case "NEXT":
                print("NEXT")
                self.active = False
                return
            case "DONE":
                print("DONE")
                self.stop()
                return
            case _: # do nothing if invalid state
                print("GATE: INVALID NEXT STATE", self.state)
                return
        self.state = next

    # loop function (mostly transitions)
    def loop(self):
        if not self.active: return # do nothing if not enabled
        # transitions
        match(self.state):
            case "INIT":
                pass
            case "DRIVE": # transition: DRIVE -> DONE
                if self.reached_xyz(self.gate_x, self.gate_y, self.gate_z):
                    self.next_state("NEXT")
            case _: # do nothing if invalid state
                print("GATE: INVALID LOOP STATE", self.state)
                return
    
    # returns true if near a location (requires x,y,z buffer and dvl to work)
    def reached_xyz(self, x, y, z):
        if abs(self.shared_memory_object.dvl_x.value - x) <= self.x_buffer and abs(self.shared_memory_object.dvl_y.value - y) <= self.y_buffer and abs(self.shared_memory_object.dvl_z.value - z) <= self.z_buffer:
            return True
        # else
        return False

    # wait until child processes terminate
    def join(self):
        if not self.active: return # do nothing if not enabled
        # join processes
        self.PID_process.join()
        self.dvl_process.join()
        #self.vis_process.join()

    # stop FSM
    def stop(self):
        self.active = False
        # terminate processes
        self.PID_process.terminate()
        self.dvl_process.terminate()
        #self.vis_process.terminate()