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
        self.complete = False   # boolean for when the mode has completed its tasks
        self.name = "PARENT"    # mode name string
        self.testing = False    # testing mode

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
       
    def next_state(self, next):
        """
        Change to next state
        """
        if self.state == next: return # do nothing if no state change
        match(next):
            case "INIT": return # initial state
            case "S1": pass
            case _: # do nothing if invalid state
                print(f"{self.name} INVALID NEXT STATE {next}")
                return
        self.state = next
        print(f"{self.name}:{self.state}")

    def loop(self):
        """
        Loop function, mostly state transitions within conditionals
        """
        if not self.active: return # do nothing if not enabled
        # transitions
        match(self.state):
            case "INIT": pass
            case _:
                print(f"{self.name} INVALID STATE {self.state}")
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
        tgt_txt = f"DVL: \t\t x = {round(self.shared_memory_object.dvl_x.value,2)}\t y = {round(self.shared_memory_object.dvl_y.value,2)}\t z = {round(self.shared_memory_object.dvl_z.value,2)}"
        dvl_txt = f"TGT: \t\t x = {round(self.shared_memory_object.target_x.value,2)}\t y = {round(self.shared_memory_object.target_y.value,2)}\t z = {round(self.shared_memory_object.target_z.value,2)}"
        # don't run display if in testing mode
        if self.testing:
            print(f"{tgt_txt}\n{dvl_txt}")
            return
        try:
            # log output
            os.system(f"echo {tgt_txt} >> /tmp/croppie.txt")
            os.system(f"echo {dvl_txt} >> /tmp/croppie.txt")
            os.system(f"echo {round(self.shared_memory_object.target_yaw.value,2)} >> /tmp/croppie.txt")
            # show on display
            set_screen(
                (r, g, b),
                f"{self.name}:{self.state}",
                tgt_txt + "\n\n" + dvl_txt
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