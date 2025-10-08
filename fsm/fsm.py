from multiprocessing                        import Process, Value
from shared_memory                          import SharedMemoryWrapper
from utils.socket_send                      import set_screen
import os
import yaml
import time
import utils.socket_send as socket_send


"""
    discord: @.kech
    github: @rsunderr

    FSM parent class
    
"""
DISPLAY_TIMER = 2

class FSM_Template:
    def __init__(self, shared_memory_object, run_list):
        """
        FSM parent class constructor to setup inherited attributes for modes
        """

        # create shared memory
        self.shared_memory_object = shared_memory_object
        # initial state
        self.state = "INIT"     # state tracking variable
        self.active = False     # enable/disable boolean
        self.complete = False   # boolean for when the mode has completed its tasks
        self.complete = False   # boolean for when the mode has completed its tasks
        self.name = "PARENT"    # mode name string
        self.display_on = False # enable/disable display output
        self.last_display_command = time.time()
        self.next_mode = None  # next mode pointer

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

    def start(self):
        """
        Start FSM by enabling and starting processes
        """
        self.active = True
        print(f"STARTING {self.name} MODE")
        # start processes
        for process in self.process_objects:
            process.start()
    
    def reached_xy(self, x, y):
        """
        Returns true if near a location in terms of x and y (requires x,y, buffer and dvl to work), use ignore to ignore a value
        """
        if abs(self.shared_memory_object.dvl_x.value - x) <= self.x_buffer and abs(self.shared_memory_object.dvl_y.value - y) <= self.y_buffer:
            return True
        # else
        return False
    
    def reached_xyz(self, x, y, z):
        """
        Returns true if near a location (requires x,y,z buffer and dvl to work), use ignore to ignore a value
        """
        if abs(self.shared_memory_object.dvl_x.value - x) <= self.x_buffer and abs(self.shared_memory_object.dvl_y.value - y) <= self.y_buffer and abs(self.shared_memory_object.dvl_z.value - z) <= self.z_buffer:
            return True
        # else
        return False
    
    def display(self, r, g, b):
        """
        Sends color and text to display
        """

        if time.time() - self.last_display_command <= DISPLAY_TIMER:
            return
        tgt_txt = f"DVL: \t x = {round(self.shared_memory_object.dvl_x.value,2)}\t y = {round(self.shared_memory_object.dvl_y.value,2)}\t z = {round(self.shared_memory_object.dvl_z.value,2)}"
        dvl_txt = f"TGT: \t x = {round(self.shared_memory_object.target_x.value,2)}\t y = {round(self.shared_memory_object.target_y.value,2)}\t z = {round(self.shared_memory_object.target_z.value,2)}"
        if not self.display_on: # don't run display if in testing mode
            print(f"{tgt_txt}\n{dvl_txt}")
            return
        try:
            # show on display
            set_screen(
                (r, g, b),
                f"{self.name}:{self.state}",
                f"{tgt_txt}\n{dvl_txt}"
            )
        except:
            return
    
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
        Stop FSM by disabling and killing processes, mark as complete
        """
        self.active = False
        self.complete = True
        # terminate processes
        for process in self.process_objects:
            if process.is_alive():
                process.terminate()
    
    def suspend(self):
        """
        Soft kill FSM, use when a mode is done to be ready for the next mode to start
        """
        self.active = False
        self.complete = True
    
    def next(self, mode=None):
        """
        Transition to the next mode, stops if no next mode
        """
        self.suspend() # soft kill current mode

        # if parameter passed, start parameter mode
        if mode is not None:
            self.next_mode = mode
            self.next_mode.start()
        # if no parameter passed, start next_mode if it exists
        elif self.next_mode is not None:
            self.next_mode.start()
        # if no parameter or next_mode, stop
        else:
            self.stop()
        
        return self.next_mode