from multiprocessing                        import Process, Value
#from shared_memory                          import SharedMemoryWrapper
from trax_fxns import *
import time

class Trax_Interface:

    """
    discord: @.kech
    github: @rsunderr
    """

    def __init__(self, shared_memory_object):
        """
        Trax interface constructor
        """
        self.shared_memory_object = shared_memory_object
        # setup trax
        self.trax = TRAX()
        self.trax.connect()
        self.t_prev = time.time()
        self.continuous = False
        self.payload = None
        self.data = []

        # positional data
        self.trax_x = 0 # eventually put these in shared memory
        self.trax_y = 0
        self.trax_z = 0

        self.vel_x = 0
        self.vel_y = 0
        self.vel_z = 0

        self.trax_yaw   = 0
        self.trax_pitch = 0
        self.trax_roll  = 0

        # kSetAcqParams
        frameID = "kSetAcqParams" # OR =24
        self.payload = (False, False, 0.0, 0.001)
        self.trax.send_packet(frameID, self.payload)

        # kSetAcqParamsDone
        #self.data = self.trax.recv_packet()
        #print("kSetAcqParamsDone:", self.data[1] == 26)

        # kSetDataComponents
        frameID = "kSetDataComponents"
        self.payload = (6, 0x15, 0x16, 0x17, 0x5, 0x18, 0x19) # 6 comp's: ax ay az yaw pitch roll
        self.trax.send_packet(frameID, self.payload)

    def update(self):
        """
        message_type, dvl_data = self.dvl.recieveData()
        if dvl_data != None and message_type == "dead_reckoning":
            self.shared_memory_object.dvl_yaw.value = dvl_data[0]
            self.shared_memory_object.dvl_pitch.value = dvl_data[1]
            self.shared_memory_object.dvl_roll.value = dvl_data[2]
            self.shared_memory_object.dvl_x.value = -dvl_data[3]
            self.shared_memory_object.dvl_y.value = dvl_data[4]
            self.shared_memory_object.dvl_z.value = dvl_data[5]
            print("dvl_yaw:", self.shared_memory_object.dvl_yaw.value)
            print("dvl_pitch:", self.shared_memory_object.dvl_pitch.value)
            print("dvl_roll:", self.shared_memory_object.dvl_roll.value)
            print("dvl_x:", self.shared_memory_object.dvl_x.value)
            print("dvl_y:", self.shared_memory_object.dvl_y.value)
            print("dvl_z:", self.shared_memory_object.dvl_z.value)
        """

    def run_loop(self):
        """
        Function targeted by looping multiprocessing calls
        """
        # start continuous mode if not already started
        if not self.continuous:
            #self.start_cont_mode()
            self.continuous = True
        # get data
        self.data = self.trax.recv_packet(self.payload)
        print(self.data)
        # update values
        self.trax_yaw = self.data[3]
        self.trax_pitch = self.data[4]
        self.trax_roll = self.data[5]
        t = time.time()
        if t - self.t_prev == 0.05: # run only every 0.05s
            self.vel_x += self.data[0]
            self.vel_y += self.data[1]
            self.vel_z += self.data[2]

            self.trax_x += self.vel_x
            self.trax_y += self.vel_y
            self.trax_z += self.vel_z

            self.t_prev = t

    def start_cont_mode(self):
        """
        Start continuous data mode
        """
        self.stop_cont_mode() # stop first to prevent issues
        # kStartContinuousMode
        frameID = "kStartContinuousMode"
        self.trax.send_packet(frameID)
        self.continuous = True
    
    def stop_cont_mode(self):
        """
        Stop continuous data mode
        """
        # kStopContinuousMode
        frameID = "kStopContinuousMode"
        self.trax.send_packet(frameID)

if __name__ == "__main__":
    shared_memory_object = "placeholder"
    trax = Trax_Interface(shared_memory_object)
    trax.run_loop()
