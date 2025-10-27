from multiprocessing                        import Process, Value
from shared_memory                          import SharedMemoryWrapper
from trax_fxns import *
import time

class Compass:

    """
    discord: @.kech
    github: @rsunderr
    """

    def __init__(self, shared_memory_object: SharedMemoryWrapper):
        """
        Trax interface constructor
        """
        self.shared_memory_object = shared_memory_object
        # setup trax
        self.trax = TRAX()
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
    
    def connect(self) -> None:
        """
        Connect to trax
        """
        self.trax.connect()
    
    def close(self) -> None:
        """
        Close trax connection
        """
        self.trax.close()

    def run_loop(self) -> None:
        """
        Function targeted by looping multiprocessing calls, called only once
        """
        self.trax.connect()

        # kSetAcqParams
        frameID = "kSetAcqParams"
        payload = (False, False, 0.0, 0.05) # T/F poll mode/cont mode, T/F compass FIR mode, PNI reserved, delay
        self.trax.send_packet(frameID, payload)

        # kSetAcqParamsDone (optional)
        #data = self.trax.recv_packet()
        #print("kSetAcqParamsDone:", data[1] == 26)

        # kSetDataComponents
        frameID = "kSetDataComponents"
        payload = (6, 0x15, 0x16, 0x17, 0x5, 0x18, 0x19) # 6 comp's: ax ay az yaw pitch roll
        self.trax.send_packet(frameID, payload)

        # kStopContinuousMode
        frameID = "kStopContinuousMode"
        self.trax.send_packet(frameID)

        # kStartContinuousMode
        frameID = "kStartContinuousMode"
        self.trax.send_packet(frameID)

        while self.shared_memory_object.running.value:
            try:
                # get data
                data = self.trax.recv_packet(self.payload)
            except KeyboardInterrupt:
                # kStopContinuousMode
                frameID = "kStopContinuousMode"
                self.trax.send_packet(frameID)
                self.trax.close()
    
    def get_data(self) -> tuple:# 6 comp's: ax ay az yaw pitch roll
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
    shared_memory_object = SharedMemoryWrapper()
    trax = Trax_Interface(shared_memory_object)
    trax.run_loop()