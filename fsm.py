from multiprocessing                        import Process, Value
from shared_memory                          import SharedMemoryWrapper
"""
    discord: @.kech
    github: @rsunderr

    FSM
    
"""
class FSM:
    def __init__(self, shared_memory_object):
        self.active = False
        # create shared memory
        self.shared_memory_object = shared_memory_object
        # initial state
        self.state = "S0"

        # buffers
        self.x_buffer = 0.5
        self.y_buffer = 0.5
        self.z_buffer = 0.5
        
    
    # start FSM
    def start(self):
        self.active = True
        # start processes

        # set initial state
        self.next_state("S1")
       

    # change to next state
    def next_state(self, next):
        if self.state == next: return # do nothing if no state change
        match(next):
            case "S1":
                pass
            case "DONE":
                print("DONE")
                self.stop()
                return
            case _: # do nothing if invalid state
                print("INVALID STATE")
                return
        self.state = next

    # looping function (mostly transitions)
    def loop(self):
        if not self.active: return # do nothing if not enabled
        # transitions
        match(next):
            case "S1":
                pass
            case _:
                print("INVALID STATE")
                return
    
    # returns true if near a location (requires x,y,z buffer and dvl to work)
    def reached_xyz(self, x, y, z):
        if abs(self.shared_memory_object.dvl_x.value - x) <= self.x_buffer and abs(self.shared_memory_object.dvl_y.value - y) <= self.y_buffer and abs(self.shared_memory_object.dvl_z.value - z) <= self.z_buffer:
            return True
        # else
        return False
    
    # wait until child processes terminate
    def join(self):
        # join processes
        pass

    # stop FSM
    def stop(self):
        self.active = False
        # terminate processes

"""
Functionalities I want to add:
- make the processes into an array so that it just iterates through the array to start, join etc.
- read from a file for shared memory target values to prevent issues for plans with multiple modes
- turn this file (fsm.py) into a parent class inherited by child fsm classes?
- add more comments to explain stuff
- add a function for getting if you are at a location
"""