from multiprocessing                        import Process, Value
#from modules.sensors.trax2.trax_fxns        import Trax
from trax_fxns import Trax
import time
try:
    from shared_memory                      import SharedMemoryWrapper
except:
    pass


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
        self.t_prev = time.time()

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

    def run_loop(self):
        """
        Function targeted by looping multiprocessing calls
        """
        trax = Trax()
        trax.connect()

        # kStopContinuousMode
        frameID = "kStopContinuousMode"
        trax.send_packet(frameID)

        # kSetAcqParams
        frameID = "kSetAcqParams"
        payload = (False, False, 0.0, 0.2)
        trax.send_packet(frameID, payload)

        # kSetAcqParamsDone
        #data = trax.recv_packet()
        #print(data)
        #print(data[1] == 26)

        # kSetDataComponents
        frameID = "kSetDataComponents"
        payload = (6, 0x15, 0x16, 0x17, 0x5, 0x18, 0x19) # 6 comp's: ax ay az yaw pitch roll
        trax.send_packet(frameID, payload)

        # kStartContinuousMode
        frameID = "kStartContinuousMode"
        trax.send_packet(frameID)
        
        # GET CONTINUOUS DATA ------------------------------------------------------------------------------------------
        try:
            while True:#self.shared_memory_object.running.value:
                data = trax.recv_packet(payload)
                print(data)

                if len(data) == 16: # if receiving kGetDataResp for 6 components
                    # parse data
                    ax = data[4] #+ 0.053
                    ay = data[6] #+ 0.057
                    az = data[8] #- 0.997
                    yaw = data[10]
                    pitch = data[12]
                    roll = data[14]
                    print(f"ax={ax} ay={ay} az={az}\nvx={self.vel_x} vy={self.vel_y} vz={self.vel_z}\nx={self.trax_x} y={self.trax_y} z={self.trax_z}\nyaw={yaw} pitch={pitch} roll={roll}")

                    # UPDATE VALUES ------------------------------------------------------------------------------------------
                    t = time.time()
                    dt = t - self.t_prev
                    self.t_prev = t

                    self.trax_yaw = yaw
                    self.trax_pitch = pitch
                    self.trax_roll = roll

                    self.vel_x += ax * dt
                    self.vel_y += ay * dt
                    self.vel_z += az * dt

                    self.trax_x += self.vel_x * dt
                    self.trax_y += self.vel_y * dt
                    self.trax_z += self.vel_z * dt

        except KeyboardInterrupt:
            # kStopContinuousMode
            frameID = "kStopContinuousMode"
            trax.send_packet(frameID)
            trax.close()
        finally:
            # kStopContinuousMode (PLEASE REMEMBER TO STOP - CONTINUOUS RUNS ON STARTUP)
            frameID = "kStopContinuousMode"
            trax.send_packet(frameID)
            trax.close()

if __name__ == "__main__":
    print("RUNNING FROM MAIN")
    shared_memory_object = "placeholder"
    trax = Trax_Interface(shared_memory_object)
    trax.run_loop()