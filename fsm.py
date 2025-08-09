from multiprocessing                        import Process, Value
from shared_memory                          import SharedMemoryWrapper
from socket_send import set_screen
import os
import yaml
import time
import socket_send


"""
    discord: @.kech
    github: @rsunderr

    FSM parent class
    
"""
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
        self.complete = False   # mode complete boolean
        self.name = "PARENT"    # mode name string

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
        # start processes

        for process in self.process_objects:
            process.start()

        # set initial state
        self.next_state("S1")
       
    def next_state(self, next):
        """
        Change to next state
        """
        if self.state == next: return # do nothing if no state change
        match(next):
            case "INIT": pass
            case _: # do nothing if invalid state
                print("INVALID STATE")
                return
        self.state = next

    def loop(self):
        """
        Loop function, mostly state transitions within conditionals
        """
        if not self.active: return # do nothing if not enabled
        # transitions
        match(next):
            case "INIT": pass
            case _:
                print("INVALID STATE")
                return
    
    def reached_xyz(self, x, y, z):
        """
        Returns true if near a location (requires x,y,z buffer and dvl to work)
        """
        if abs(self.shared_memory_object.dvl_x.value - x) <= self.x_buffer and abs(self.shared_memory_object.dvl_y.value - y) <= self.y_buffer and abs(self.shared_memory_object.dvl_z.value - z) <= self.z_buffer:
            return True
        # else
        return False
    
    def display(self, r, g, b):
        """
        Sends color and text to display
        """
        tgt_txt = f"TGT:\t\tx = {self.shared_memory_object.dvl_x.value}\ty = {self.shared_memory_object.dvl_y.value}\tz = {self.shared_memory_object.dvl_z.value}"
        dvl_txt = f"DVL:\t\tx = {self.shared_memory_object.target_x.value}\ty = {self.shared_memory_object.target_y.value}\tz = {self.shared_memory_object.target_z.value}"
        set_screen(
            (r, g, b),
            f"{self.name}:{self.state}",
            tgt_txt + "\n\n" + dvl_txt
        )
    
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