import sys, os, time, math
import numpy                                as np
from multiprocessing                        import Process, Value
from modules.sensors.trax2.trax_fxns        import TRAX

G_TO_MS2 = 9.80665 # gravity conversion

class Trax_Interface(TRAX):

    """
    discord: @.kech
    github: @rsunderr
    """

    def __init__(self, shared_memory_object) -> None:
        """
        Trax interface constructor
        """
        super().__init__()
        self.shared_memory_object = shared_memory_object
        self.interval: float = 0
        self.acq_params: tuple = (False, False, 0, self.interval) # poll mode false, flush filter false, PNI reserved, interval
        self.data_components: tuple = (6, 0x15, 0x16, 0x17, 0x5, 0x18, 0x19) # 6 comp's: ax ay az yaw pitch roll

        # positional values
        self.t_prev:    float = time.time()
        self.vel_x:     float = 0
        self.vel_y:     float = 0
        self.vel_z:     float = 0
        self.pos_x:     float = 0
        self.pos_y:     float = 0
        self.pos_z:     float = 0
        
        # bias compensation
        self.accel_x_bias:  float = 0
        self.accel_y_bias:  float = 0
        self.accel_z_bias:  float = 0
        self.threshold:     float = 0.1
    
    def setup(self) -> None:
        """
        Setup function to initialize Trax interface
        Call this function once ever after continuous mode is stopped, it is remembered by non-volatile memory (no need to run every time)
        """
        self.connect() # connect to trax
        self.send_packet("kStopContinuousMode") # kStopContinuousMode (ensure not running)
        self.send_packet("kSetAcqParams", self.acq_params) # kSetAcqParams - set acquisition parameters
        self.send_packet("kSetDataComponents", self.data_components) # kSetDataComponents - set data components
        self.send_packet("kSave") # kSave - save settings
        resp = self.recv_packet() # save response
        print(resp)
        
    def run_loop(self) -> None:
        """
        Start the Trax interface process
        """
        #self.setup() # only run once ever
        self.connect()
        self.send_packet("kStartContinuousMode") # kStartContinuousMode - start continuous mode
        while self.shared_memory_object.running.value:
            self.update()

    def adjust_accel(self, accel_x: float, accel_y: float, acel_z: float, yw: float, ptch: float, rll: float) -> tuple:
        """
        TODO make this adjust acceleration based on orientation (ie gravity pulling on it at an angle) and convert to m/s^2
        """
        # ADJUST VALUES ---------------------------------------------------------------------------------------------------------------
        # convert from g to m/s^2
        ay = accel_y * G_TO_MS2
        ax = accel_x * G_TO_MS2
        az = acel_z * G_TO_MS2
        # convert from degrees to radians
        yaw = math.radians(yw)
        pitch = math.radians(ptch)
        roll = math.radians(rll)
        
        
        
        
        return (ax, ay, az)

    def update(self) -> None:
        """
        Function targeted by looping multiprocessing calls, called only once
        """
        t:  float = time.time()
        dt: float = t - self.t_prev
        self.t_prev = t
        try:
            # READ DATA
            data:       tuple = self.recv_packet(self.data_components)
            accel_x:    float = data[4]
            accel_y:    float = data[6]
            accel_z:    float = data[8]
            yaw:        float = data[10]
            pitch:      float = data[12]
            roll:       float = data[14]
            
            #accel_x, accel_y, accel_z = self.adjust_accel(accel_x, accel_y, accel_z, yaw, pitch, roll)
            
            self.shared_memory_object.trax_yaw.value   = yaw
            self.shared_memory_object.trax_pitch.value = pitch
            self.shared_memory_object.trax_roll.value  = roll
            
            # integrate velocity and position
            dx: float = accel_x if abs(accel_x) > self.threshold else 0
            dy: float = accel_y if abs(accel_y) > self.threshold else 0
            dz: float = accel_z if abs(accel_z) > self.threshold else 0
            
            # accumulate velocity
            self.vel_x += dx * dt
            self.vel_y += dy * dt
            self.vel_z += dz * dt
            
            # update position
            self.pos_x += self.vel_x * dt
            self.pos_y += self.vel_y * dt
            self.pos_z += self.vel_z * dt

            print(f"TRAX x: {self.pos_x:.2f}, y: {self.pos_y:.2f}, z: {self.pos_z:.2f}, Yaw: {yaw:.2f}, Pitch: {pitch:.2f}, Roll: {roll:.2f}, X Accel: {accel_x:.2f}, Y Accel: {accel_y:.2f}, Z Accel: {accel_z:.2f}")
        except KeyboardInterrupt:
            self.send_packet("kStopContinuousMode")
            self.close()
        except Exception as e:
            print(f"INVALID TRAX DATA: {e}") # errors are expected