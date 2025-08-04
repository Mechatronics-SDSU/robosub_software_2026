from multiprocessing                        import Process, Value
from shared_memory                          import SharedMemoryWrapper
"""
    discord: @.kech
    github: @rsunderr

    FSM
    
"""
class FSM:
    def __init__(self):
        self.active = False
        # create shared memory
        self.shared_memory_object = SharedMemoryWrapper()
        # initial state
        self.state = "S0"
        
    
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
            case _: # do nothing if invalid state
                print("INVALID STATE")
                return
        self.state = next

    # looping function
    def loop(self):
        if not self.active: return # do nothing if not enabled
        # transitions
        match(next):
            case "S1":
                pass
            case _:
                print("INVALID STATE")
                return
    
    # wait until child processes terminate
    def join(self):
        # join processes
        pass

    # stop FSM
    def stop(self):
        self.active = False
        # terminate processes