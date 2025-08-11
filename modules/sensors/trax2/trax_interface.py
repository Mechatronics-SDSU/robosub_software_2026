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
        frameID = "kSetAcqParams"
        payload = (False, False, 0.0, 0.05) # T/F poll mode/cont mode, T/F compass FIR mode, PNI reserved, delay
        self.trax.send_packet(frameID, payload)

        # kSetAcqParamsDone (optional)
        #data = self.trax.recv_packet()
        #print("kSetAcqParamsDone:", data[1] == 26)

        # kSetDataComponents
        frameID = "kSetDataComponents"
        self.payload = (6, 0x15, 0x16, 0x17, 0x5, 0x18, 0x19) # 6 comp's: ax ay az yaw pitch roll
        self.trax.send_packet(frameID, self.payload)

    def run_loop(self):
        """
        Function targeted by looping multiprocessing calls
        """
        # start continuous mode if not already started
        if not self.continuous:
            self.stop_cont_mode()
            self.start_cont_mode()
            self.continuous = True
        # get data
        data = self.trax.recv_packet(self.payload)
        """
        # update values
        t = time.time()
        if t - self.t_prev == 0.05: # run only every 0.05s
            self.trax_yaw = yaw
            self.trax_pitch = pitch
            self.trax_roll = roll

            self.vel_x += ax
            self.vel_y += ay
            self.vel_z += az

            self.trax_x += self.vel_x
            self.trax_y += self.vel_y
            self.trax_z += self.vel_z

            self.t_prev = t
        
        print(f"ax={ax} ay={ay} az={az}\nvx={self.vel_x} vy={self.vy} vz={self.vel_z}\nx={self.trax_x} y={self.trax_y} z={self.trax_z}\nyaw={yaw} pitch={pitch} roll={roll}")
        """

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
    
    def get_data(self):# 6 comp's: ax ay az yaw pitch roll
        data = self.trax.recv_packet(self.payload)
        print(data)
        ax = data[4]
        ay = data[6]
        az = data[8]
        yaw = data[10]
        pitch = data[12]
        roll = data[14]
        return (ax, ay, az, yaw, pitch, roll)

if __name__ == "__main__":
    shared_memory_object = "placeholder"
    trax = Trax_Interface(shared_memory_object)
    trax.run_loop()
