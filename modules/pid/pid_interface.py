import numpy as np
import time
from modules.pid.six_dof_pid import PID
from scipy.spatial.transform import Rotation as R

try: 
    from modules.motors.ScionMotorWrapper       import MotorWrapper
except ImportError:
    from modules.motors.MotorWrapper            import MotorWrapper

"""
    discord: @kialli
    github: @kchan5071

    PID methods, integration (orientation code)

"""
P_DEBUG = False

class PIDInterface:
    def __init__(self, shared_memory_object):
        self.shared_memory_object = shared_memory_object
        self.motor_wrapper = MotorWrapper(self.shared_memory_object)

        #SIMULATION
        # self.simulation = Simulation(np.array([0, 0, 0, 0, 0, 0], dtype=float))

        # array of PID k Values
        # cols = x, y, z, yaw, pitch, roll
        # rows = kp, ki, kd
        self.K_array = np.array([[3000,  3000,  2500,    30,     2,    2], 
                                 [.5,   .5,      2,      2,    .5,   .5],
                                 [.1,   .1 ,    .1,     .2,    .5,   .5]])
        
    
    def run_pid(self):
        desired_state = np.array([self.shared_memory_object.target_x.value, 
                                  self.shared_memory_object.target_y.value, 
                                  self.shared_memory_object.target_z.value, 
                                  self.shared_memory_object.target_yaw.value, 
                                  self.shared_memory_object.target_pitch.value, 
                                  self.shared_memory_object.target_roll.value])
        current_state = np.array([self.shared_memory_object.dvl_x.value, 
                                  self.shared_memory_object.dvl_y.value, 
                                  self.shared_memory_object.dvl_z.value, 
                                  self.shared_memory_object.dvl_yaw.value, 
                                  self.shared_memory_object.dvl_pitch.value, 
                                  self.shared_memory_object.dvl_roll.value])
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
        movement_global = (np.multiply(movement_global, [1,-1,-1,-1,1,1]))
        return movement_global, untransformed
    
    def run_loop(self):
        np.set_printoptions(formatter={'float': lambda x: "{0:0.3f}".format(x)})
        while self.shared_memory_object.running.value:
            direction, untransformed_direction = self.run_pid()
            self.motor_wrapper.move_from_matrix(direction)
            self.motor_wrapper.send_command()
            error = np.subtract(np.array([self.shared_memory_object.target_x.value, 
                                          self.shared_memory_object.target_y.value, 
                                          self.shared_memory_object.target_z.value, 
                                          self.shared_memory_object.target_yaw.value, 
                                          self.shared_memory_object.target_pitch.value, 
                                          self.shared_memory_object.target_roll.value]), 
                                np.array([self.shared_memory_object.dvl_x.value, 
                                          self.shared_memory_object.dvl_y.value, 
                                          self.shared_memory_object.dvl_z.value, 
                                          self.shared_memory_object.dvl_yaw.value, 
                                          self.shared_memory_object.dvl_pitch.value, 
                                          self.shared_memory_object.dvl_roll.value]))
            if P_DEBUG:
                print("Direction: ", direction)
                print("Untransformed Direction: ", untransformed_direction)
                print("Linear Error: ", np.sum(error[:3]))
                print("Angular Error: ", np.sum(error[3:]))

            
            time.sleep(0.2)
            

            


        
        
