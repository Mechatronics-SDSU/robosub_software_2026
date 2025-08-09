from multiprocessing                        import Process, Value
from shared_memory                          import SharedMemoryWrapper


"""
    discord: @.kech
    github: @rsunderr

    FSM
    
"""
class FSM_Template:
    def __init__(self, shared_memory_object, run_list):

        # create shared memory
        self.shared_memory_object = shared_memory_object
        # initial state
        self.state = "INIT"
        self.active = False

        # buffers
        self.x_buffer = 0.5
        self.y_buffer = 0.5
        self.z_buffer = 0.5

        # process saving
        self.process_objects = []     

        # create processes
        for run_object in run_list:
            temp_process = Process(target=run_object.run_loop)
            self.process_objects.append(temp_process)

        
    # start FSM
    def start(self):
        self.active = True
        # start processes

        for process in self.process_objects:
            process.start()

        # set initial state
        self.next_state("S1")
       

    # change to next state
    def next_state(self, next):
        if self.state == next: return # do nothing if no state change
        match(next):
            case _: # do nothing if invalid state
                print("INVALID STATE")
                return
        self.state = next

    # looping function (mostly transitions)
    def loop(self):
        if not self.active: return # do nothing if not enabled
        # transitions
        match(next):
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
        """
        Wait until child processes terminate
        """
        if not self.active: return # do nothing if not enabled
        # join processes
        for process in self.process_objects:
            if process.is_alive():
                process.join()

    def stop(self):
        """
        Stop FSM
        """
        self.active = False
        # terminate processes
        for process in self.process_objects:
            if process.is_alive():
                process.terminate()

"""
Functionalities I want to add:
-(Done) make the processes into an array so that it just iterates through the array to start, join etc.
- read from a file for shared memory target values to prevent issues for plans with multiple modes
-(Done) turn this file (fsm.py) into a parent class inherited by child fsm classes?
- add more comments to explain stuff
-(Done) add a function for getting if you are at a location
- make a README
-(Done) maybe rewrite FSMs to make modes that share processes
"""