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

    def __init__(self, shared_memory_object, include_gyro=False, preferred_trax = 1 ) -> None:
        """
        Trax interface constructor
        """
        super().__init__(preferred_trax)
        self.shared_memory_object = shared_memory_object
        self.interval: float = 0
        self.acq_params: tuple = (False, False, 0, self.interval) # poll mode false, flush filter false, PNI reserved, interval
        # only trax2 can handle gyro data
        self.include_gyro = include_gyro
        if include_gyro:
            self.data_components: tuple = (9, 0x15, 0x16, 0x17, 0x5, 0x18, 0x19, 0x4A, 0x4B, 0x4C) # 9 comp's: ax ay az yaw pitch roll and gyro x y z
        else:
            self.data_components: tuple = (6, 0x15, 0x16, 0x17, 0x5, 0x18, 0x19) # 6 comp's: ax ay az yaw pitch roll
        # positional values
        self.t_prev:    float = time.time()
        self.vel_x:     float = 0
        self.vel_y:     float = 0
        self.vel_z:     float = 0
        self.pos_x:     float = 0
        self.pos_y:     float = 0
        self.pos_z:     float = 0
        # Don't be confused these relate to angular velocity, not linear position
        self.prev_x:    float = 0
        self.prev_y:    float = 0
        self.prev_z:    float = 0

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
            
    @staticmethod        
    def to_360(angle):
        if angle < 0:
            return angle + 360
        return angle


    def adjust_accel(self, accel_x: float, accel_y: float, acel_z: float, yw: float, ptch: float, rll: float) -> tuple:
        """
        TODO make this adjust acceleration based on orientation (ie gravity pulling on it at an angle) and convert to m/s^2
        """
        # ADJUST VALUES ---------------------------------------------------------------------------------------------------------------
        # convert from g to m/s^2
        ay = accel_y * G_TO_MS2
        ax = accel_x * G_TO_MS2
        az = acel_z * G_TO_MS2
        # convert from degrees to radians and convert to 0-360 range
        yaw = math.radians(yw)
        pitch = math.radians(Trax_Interface.to_360(ptch))
        roll = math.radians(Trax_Interface.to_360(rll))
        cy=math.cos(roll)
        sy=math.sin(roll)
        sB=math.sin(pitch)
        cB=math.cos(pitch)
        sa=math.sin(yaw)
        ca=math.cos(yaw)
        # Rotate the body acceleration to world then subtract world gravity
        rollRot=np.array([[1,0,0],[0,cy,-sy],[0,sy,cy]])
        pitchRot=np.array([[cB, 0, sB],[0, 1, 0],[-sB, 0, cB]])
        yawRot=np.array([[ca, -sa, 0],[sa, ca, 0],[0, 0, 1]])
        self.R=np.matmul(yawRot,np.matmul(pitchRot,rollRot))
        # R=np.array([[ca*cB, ca*sB*sy-sa*cy, ca*sB*cy+sa*sy], [sa*cB, sa*sB*sy+ca*cy, sa*sB*cy-ca*sy], [-sB, cB*sy, cB*cy]])
        Rinv=np.linalg.inv(self.R)
        localAccel=np.array([ax, ay, az]).T
        globalAccel=np.matmul(self.R,localAccel)
        globalAccel=globalAccel-np.array([0,0,G_TO_MS2]).T #force of gravity is felt by accelerometer in opposite direction
        ax=globalAccel[0]
        ay=globalAccel[1]
        az=globalAccel[2]
        self.shared_memory_object.trax_R[:] = np.reshape(self.R, -1)# store rotation matrix in shared memory
        
        
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
            pitch:      float = data[12] if self.current_trax == 1 else -1*data[12] # trax 2 is mounted flipped, invert pitch to compensate
            roll:       float = data[14] if self.current_trax == 1 else -1*data[14] # trax 2 is mounted flipped, invert roll to compensate
            accel_x, accel_y, accel_z = self.adjust_accel(accel_x, accel_y, accel_z, yaw, pitch, roll)
            
            self.shared_memory_object.trax_yaw.value   = yaw
            self.shared_memory_object.trax_pitch.value = pitch
            self.shared_memory_object.trax_roll.value  = roll
            
            # integrate velocity and position
            dx: float = accel_x 
            dy: float = accel_y 
            dz: float = accel_z 
            
            # accumulate velocity
            self.vel_x += dx * dt
            self.vel_y += dy * dt
            self.vel_z += dz * dt
            
            # update position
            self.pos_x += self.vel_x * dt
            self.pos_y += self.vel_y * dt
            self.pos_z += self.vel_z * dt
            
            self.print_data("Trax"+ str(self.current_trax)+str(f"x: {self.pos_x:.2f}, y: {self.pos_y:.2f}, z: {self.pos_z:.2f}, Yaw: {yaw:.2f}, Pitch: {pitch:.2f}, Roll: {roll:.2f}, X Accel: {accel_x:.2f}, Y Accel: {accel_y:.2f}, Z Accel: {accel_z:.2f}"))
        except KeyboardInterrupt:
            self.send_packet("kStopContinuousMode")
            self.close()
        except Exception as e:
            print(f"INVALID TRAX DATA: {e}") # errors are expected

    def first_update(self)->None:
        #self.setup() # only run once ever
        self.connect()
        self.send_packet("kStartContinuousMode") # kStartContinuousMode - start continuous mode
        
    # single data call so function can be looped outside of Trax_Interface (meant for multi IMU sensor fusion algorithm)
    def get_data(self):
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
            

            accel_x, accel_y, accel_z = self.adjust_accel(accel_x, accel_y, accel_z, yaw, pitch, roll)

            # integrate velocity and position
            dx: float = accel_x 
            dy: float = accel_y 
            dz: float = accel_z 

            # accumulate velocity
            self.vel_x += dx * dt
            self.vel_y += dy * dt
            self.vel_z += dz * dt

            # update position
            self.pos_x += self.vel_x * dt
            self.pos_y += self.vel_y * dt
            self.pos_z += self.vel_z * dt
            lin_accel = np.array([[accel_x], [accel_y], [accel_z]])

            if self.include_gyro:
                
                gyro_x:     float = data[16]
                gyro_y:     float = data[18]
                gyro_z:     float = data[20]
                ang_rate = np.array([[gyro_x], [gyro_y], [gyro_z]])

                # needed to calculate T matrix for converting angular rate to angular velocity
                yaw = math.radians(yaw)
                pitch = math.radians(Trax_Interface.to_360(pitch))
                roll = math.radians(Trax_Interface.to_360(roll))
                cy=math.cos(roll)
                sy=math.sin(roll)
                sB=math.sin(pitch)
                cB=math.cos(pitch)
                sa=math.sin(yaw)
                ca=math.cos(yaw)
                T=np.array([[-sa, 0 , 1], [ca*sy, cy, 0], [cy*ca, -sy, 0]])
                ang_vel = T @ ang_rate
                global_ang_vel = self.R @ ang_vel
                # angular acceleration
                self.global_angular_acc_x = (global_ang_vel[0] - self.prev_x) / dt
                self.global_angular_acc_y = (global_ang_vel[1] - self.prev_y) / dt
                self.global_angular_acc_z = (global_ang_vel[2] - self.prev_z) / dt
                self.prev_x,self.prev_y,self.prev_z = global_ang_vel[0], global_ang_vel[1], global_ang_vel[2]

                global_ang_acc = np.array([[self.global_angular_acc_x], [self.global_angular_acc_y], [self.global_angular_acc_z]])
                return lin_accel, global_ang_vel, global_ang_acc
            return lin_accel
        except KeyboardInterrupt:
            self.send_packet("kStopContinuousMode")
            self.close()
        except Exception as e:
            print(f"INVALID TRAX DATA: {e}") # errors are expected