import numpy as np
import time
from modules.pid.six_dof_pid import PID
from scipy.spatial.transform import Rotation as R

try: 
    from modules.motors.ScionMotorWrapper       import MotorWrapper
    print("SCION")
except ImportError:
    from modules.motors.MotorWrapper            import MotorWrapper
    print("CARACARA")

"""
    discord: @kialli
    github: @kchan5071

    PID methods, integration (orientation code)

"""
P_DEBUG = False
IN_WATER = True
TRANSLATION_MODE_IMU = True

class PIDInterface:
    def __init__(self, shared_memory_object):
        self.shared_memory_object = shared_memory_object
        # if IN_WATER:
        print("WATER")
        self.motor_wrapper = MotorWrapper(shared_memory_object)
        self.source = "IMU"

        #SIMULATION
        # self.simulation = Simulation(np.array([0, 0, 0, 0, 0, 0], dtype=float))

        # array of PID k Values
        # cols = x, y, z, yaw, pitch, roll
        # rows = kp, ki, kd
        self.K_array = np.array([[2000,  2000,  50,    5,     2,    2], 
                                 [.5,   .5,     1,     .5,    0,   0],
                                 [.1,   .1 ,    2,     .1,    0,   0]])
        self.imu_active = False
        
    def get_target_state(self, arg):
        if self.shared_memory_object.depth.value == 0.0:
            return  np.array([0, 0, 0, 0, 0, 0])
        if arg == "ERROR" or arg == "ZERO":
            return  np.array([0, 0, 0, 0, 0, 0])
        if self.source == "DVL":
            return np.array([
                self.shared_memory_object.target_x.value, 
                self.shared_memory_object.target_y.value, 
                self.shared_memory_object.target_z.value, 
                self.shared_memory_object.target_yaw.value, 
                self.shared_memory_object.target_pitch.value, 
                self.shared_memory_object.target_roll.value
            ])

    def get_imu_rotation(self):
            try:
                rotation = R.from_quat([
                    self.shared_memory_object.imu_orientation[0], 
                    self.shared_memory_object.imu_orientation[1], 
                    self.shared_memory_object.imu_orientation[2], 
                    self.shared_memory_object.imu_orientation[3]
                ])
                euler_angles = rotation.as_euler('xzy', degrees=False)
                print(euler_angles)
                return rotation.as_euler('xzy', degrees=False)
            except:
                return False
            
    def run_pid(self):
        if self.source == "DVL":
            desired_state = np.array([
                self.shared_memory_object.target_x.value, 
                self.shared_memory_object.target_y.value, 
                self.shared_memory_object.target_z.value, 
                self.shared_memory_object.target_yaw.value, 
                self.shared_memory_object.target_pitch.value, 
                self.shared_memory_object.target_roll.value
            ])
            current_state = np.array([
                self.shared_memory_object.dvl_x.value, 
                self.shared_memory_object.dvl_y.value, 
                self.shared_memory_object.dvl_z.value, 
                self.shared_memory_object.dvl_yaw.value, 
                self.shared_memory_object.dvl_pitch.value, 
                self.shared_memory_object.dvl_roll.value
            ])
        elif self.source == "IMU":
            while not self.imu_active:
                if self.shared_memory_object.imu_orientation[0] != 0.0:
                    self.imu_active = True
            euler_angles = self.get_imu_rotation()
            if euler_angles is not False:
                self.shared_memory_object.imu_yaw.value = euler_angles[1]
                if P_DEBUG:
                    print("EULER ANGLES:\t", euler_angles)
                if self.shared_memory_object.depth.value == 0.0:
                    desired_state = np.array([0, 0, 0, 0, 0, 0])
                    current_state = np.array([0, 0, 0, 0,  0, 0])
                # print("EULER ANGLES:\t", euler_angles)
                desired_state = np.array([
                    self.shared_memory_object.target_x.value,
                    0, 
                    self.shared_memory_object.target_z.value, 
                    self.shared_memory_object.target_yaw.value, 
                    self.shared_memory_object.target_pitch.value, 
                    self.shared_memory_object.target_roll.value
                ])
                current_state = np.array([
                    0, 
                    0, 
                    self.shared_memory_object.depth.value, 
                    self.shared_memory_object.imu_yaw.value, 
                    0, 
                    0
                ])
                if P_DEBUG:
                    print("EULER ANGLES:\t", euler_angles)
                    print("CURRENT STATE:\t", current_state)
            # except Exception as e:
            #     desired_state = np.array([0, 0, 0, 0, 0, 0])
            #     current_state = np.array([0, 0, 0, 0,  0, 0])
        self.pid = PID(self.K_array[0], self.K_array[1], self.K_array[2], 0.5)
        # Get the PID output: movement in robot's local frame
        untransformed = self.pid.update(current_state, desired_state)  # [x, y, z, yaw, pitch, roll]

        # Split into linear and angular components
        movement_local = np.array(untransformed[:3])  # Linear: x, y, z (local frame)
        angular = np.array(untransformed[3:])         # Angular: yaw, pitch, roll

        # Get current orientation of the robot (in degrees)
        yaw, pitch, roll = current_state[3], current_state[4], current_state[5]

        # Build rotation matrix from current orientation (order: yaw -> pitch -> roll)
        rotation = R.from_euler('zyx', [yaw, pitch, roll], degrees=True)

        # Rotate movement vector from local to global frame
        movement_global_linear = rotation.apply(movement_local)

        # Combine with angular commands (still in local frame)
        movement_global = np.concatenate([movement_global_linear, angular])
        if P_DEBUG:
            print("Untransformed: ", untransformed)
            print("Yaw, Pitch, Roll: ", (yaw, pitch, roll))
            print("Transformed: ",movement_global)
        movement_global = (np.multiply(movement_global, [1,-1,-1, 1,1,1]))
        return movement_global, untransformed
    
    def run_loop(self):
        np.set_printoptions(formatter={'float': lambda x: "{0:0.3f}".format(x)})
        while self.shared_memory_object.running.value:
            direction, untransformed_direction = self.run_pid()
            # if IN_WATER:
            self.motor_wrapper.move_from_matrix(direction)
            self.motor_wrapper.send_command()


            if P_DEBUG:
                print("Direction: ", direction)
                print("Untransformed Direction: ", untransformed_direction)

            
            time.sleep(0.2)
            

            


        
        
