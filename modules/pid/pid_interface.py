import numpy as np
import time
from modules.pid.six_dof_pid import PID
from modules.motors.MotorWrapper import Can_Wrapper
from modules.motors.motor_simulation import Simulation

"""
    discord: @kialli
    github: @kchan5071

    PID methods, integration (orientation code)

"""
class PIDInterface:
    def __init__(self, shared_memory_object):
        self.shared_memory_object = shared_memory_object
        self.motor_wrapper = Can_Wrapper()

        #SIMULATION
        self.simulation = Simulation(np.array([0, 0, 0, 0, 0, 0], dtype=float))

        # array of PID k Values
        # cols = x, y, z, roll, pitch, yaw
        # rows = kp, ki, kd
        self.K_array = np.array([[10, 10, 0, 0, 0, 0], 
                                 [.5, .5, .0, .0, .0, .0],
                                 [.01 , .01 , .00 , .00 , .00 , .00 ]])

        
    
    def run_pid(self):
        desired_state = np.array([self.shared_memory_object.target_x.value, 
                                  self.shared_memory_object.target_y.value, 
                                  self.shared_memory_object.target_z.value, 
                                  self.shared_memory_object.target_roll.value, 
                                  self.shared_memory_object.target_pitch.value, 
                                  self.shared_memory_object.target_yaw.value])
        current_state = np.array([self.shared_memory_object.dvl_x.value, 
                                  self.shared_memory_object.dvl_y.value, 
                                  self.shared_memory_object.dvl_z.value, 
                                  self.shared_memory_object.dvl_roll.value, 
                                  self.shared_memory_object.dvl_pitch.value, 
                                  self.shared_memory_object.dvl_yaw.value])
        self.pid = PID(self.K_array[0], self.K_array[1], self.K_array[2], 0.5)
        return self.pid.update(current_state, desired_state)
    
    def apply_monte_carlo(self):
        self.shared_memory_object.dvl_x.value += np.random.normal(-0.2, 0.2)
        self.shared_memory_object.dvl_y.value += np.random.normal(-0.2, 0.2)
        self.shared_memory_object.dvl_z.value += np.random.normal(0-0.2, 0.2)
        self.shared_memory_object.dvl_roll.value += np.random.normal(-0.2, 0.2)
        self.shared_memory_object.dvl_pitch.value += np.random.normal(-0.2, 0.2)
        self.shared_memory_object.dvl_yaw.value += np.random.normal(-0.2, 0.2)
        
    def run_loop(self):
        np.set_printoptions(formatter={'float': lambda x: "{0:0.3f}".format(x)})
        while self.shared_memory_object.running.value:
            self.apply_monte_carlo()
            direction = self.run_pid()
            self.motor_wrapper.move_from_matrix(direction)
            motor = self.motor_wrapper.send_command()
            new_state = self.simulation.update(motor)
            self.shared_memory_object.dvl_x.value = new_state[0]
            self.shared_memory_object.dvl_y.value = new_state[1]
            self.shared_memory_object.dvl_z.value = new_state[2]
            self.shared_memory_object.dvl_roll.value = new_state[3]
            self.shared_memory_object.dvl_pitch.value = new_state[4]
            self.shared_memory_object.dvl_yaw.value = new_state[5]
            error = np.subtract(np.array([self.shared_memory_object.target_x.value, 
                                          self.shared_memory_object.target_y.value, 
                                          self.shared_memory_object.target_z.value, 
                                          self.shared_memory_object.target_roll.value, 
                                          self.shared_memory_object.target_pitch.value, 
                                          self.shared_memory_object.target_yaw.value]), 
                                np.array([self.shared_memory_object.dvl_x.value, 
                                          self.shared_memory_object.dvl_y.value, 
                                          self.shared_memory_object.dvl_z.value, 
                                          self.shared_memory_object.dvl_roll.value, 
                                          self.shared_memory_object.dvl_pitch.value, 
                                          self.shared_memory_object.dvl_yaw.value]))
            print("error: ", error)
            print("error magnitude: ", np.linalg.norm(error))
            print("state: ", new_state)
            
            time.sleep(0.2)
            

            


        
        
