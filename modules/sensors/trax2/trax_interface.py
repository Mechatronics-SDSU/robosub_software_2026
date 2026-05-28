import sys, os, time, math
import numpy                                as np
from multiprocessing                        import Process, Value
from trax_fxns        import TRAX


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
        self.data_components: tuple = (6, 0x15, 0x16, 0x17, 0x5, 0x18, 0x19) # 9 comp's: ax ay az yaw pitch roll gyrox gryoy gryoz 0x4A, 0x4B, 0x4C

        # positional values
        self.t_prev:    float = time.time()
        self.vel_x:     float = 0
        self.vel_y:     float = 0
        self.vel_z:     float = 0
        self.pos_x:     float = 0
        self.pos_y:     float = 0
        self.pos_z:     float = 0

        #angular values
        self.angular_accel =     np.zeros((3,1))
        self.prev_omega_s =  np.zeros((3,1))
        self.angular_vel =  np.zeros((3,1))

        
        # bias compensation
        self.accel_x_bias:  float = -0.013253514177653277 
        self.accel_y_bias:  float = -0.024590801573471467 
        self.accel_z_bias:  float = 0.004454660083781814
        self.threshold: float = 0.1
    
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

    def adjust_accel(self, accel_x: float, accel_y: float, accel_z: float, yw: float, ptch: float, rll: float) -> tuple:
        """
        TODO make this adjust acceleration based on orientation (ie gravity pulling on it at an angle) and convert to m/s^2
        """
        # ADJUST VALUES ---------------------------------------------------------------------------------------------------------------
        # convert from g to m/s^2

        ax = accel_x  * G_TO_MS2 
        ay = accel_y  * G_TO_MS2 
        az = accel_z  * G_TO_MS2 
        
        
        raw_acceleration = np.array([ax, ay, az])
        # convert from degrees to radians
        y = math.radians(yw)
        p = math.radians(ptch)
        r = math.radians(rll)
        
        
        cr = np.cos(r) #cosine of roll
        cp = np.cos(p) #cosine of pitch
        cy = np.cos(y) #cosine of yaw/heading

        sr = np.sin(r) #sine of roll
        sp = np.sin(p) #sine of pitch
        sy = np.sin(y) #sine of yaw/heading

        #rotation matrix 
        R = np.array([
            [ cy*cp,  cy*sp*sr - sy*cr,  cy*sp*cr + sy*sr ],
            [ sy*cp,  sy*sp*sr + cy*cr,  sy*sp*cr - cy*sr ],
            [   -sp,             cp*sr,              cp*cr ]
        ])

        g = np.array([0, 0, 9.80665])

        gravity_body = R @ g

        linear_acceleration = raw_acceleration - gravity_body

        ax = linear_acceleration[0]
        ay = linear_acceleration[1]
        az = linear_acceleration[2]

        
        
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
            gyro_x:     float = data[16]
            gyro_y:     float = data[18]
            gyro_z:     float = data[20]
           
            
            accel_x, accel_y, accel_z = self.adjust_accel(accel_x, accel_y, accel_z, yaw, pitch, roll)


            self.shared_memory_object.trax_yaw.value   = yaw
            self.shared_memory_object.trax_pitch.value = pitch
            self.shared_memory_object.trax_roll.value  = roll
            
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

          



            print(f"TRAX x: {self.pos_x:.2f}, y: {self.pos_y:.2f}, z: {self.pos_z:.2f}, Yaw: {yaw:.2f}, Pitch: {pitch:.2f}, Roll: {roll:.2f}, X Accel: {accel_x:.2f}, Y Accel: {accel_y:.2f}, Z Accel: {accel_z:.2f}, X gyro: {gyro_x:.2f}, Y gyro: {gyro_y:.2f}, Z gyro: {gyro_z:.2f}")

        except KeyboardInterrupt:
            self.send_packet("kStopContinuousMode")
            self.close()

        except Exception as e:
            print(f"INVALID TRAX DATA: {e}") # errors are expected

    

    def get_data(self): #for sensior fusion algorithm, just need accel because sparton will track gyro/compass
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
            gyro_x:     float = data[16]
            gyro_y:     float = data[18]
            gyro_z:     float = data[20]
            
            #accel_x, accel_y, accel_z = self.adjust_accel(accel_x, accel_y, accel_z, yaw, pitch, roll)
            accel_x = accel_x  * G_TO_MS2 
            accel_y = accel_y  * G_TO_MS2 
            accel_z = accel_z  * G_TO_MS2 - (9.80665)

            self.shared_memory_object.trax_yaw.value   = yaw
            self.shared_memory_object.trax_pitch.value = pitch
            self.shared_memory_object.trax_roll.value  = roll
            
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

            lin_accel = np.array([[accel_x], [accel_y], [accel_z]])


            return lin_accel


            
        except KeyboardInterrupt:
            self.send_packet("kStopContinuousMode")
            self.close()
        except Exception as e:
            print(f"INVALID TRAX DATA: {e}") # errors are expected

    
