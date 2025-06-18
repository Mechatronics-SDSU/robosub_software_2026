import numpy as np

"""
    discord: @kialli
    github: @kchan5071

    PID six DOF methods

"""

class PID:
    def __init__(self, kp, ki, kd, dt):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.dt = dt
        self.error                  = [0, 0, 0, 0, 0, 0]
        self.prev_error             = [0, 0, 0, 0, 0, 0]
        self.prev_integral_error    = [0, 0, 0, 0, 0, 0]
        self.integral_error         = [0, 0, 0, 0, 0, 0]
        self.derivative_error       = [0, 0, 0, 0, 0, 0]
        self.output                 = [0, 0, 0, 0, 0, 0]

    def get_error(self, initial_state, desired_state):
        self.error = np.subtract(desired_state, initial_state)
        self.integral_error += self.prev_integral_error + self.error * self.dt
        self.derivative_error = np.subtract(self.error, self.prev_error) / self.dt
    

    def update(self, initial_state, desired_state):
        self.get_error(initial_state, desired_state)
        self.output = np.add(np.add(np.multiply(self.kp, self.error), 
                                    np.multiply(self.ki, self.integral_error)), 
                                    np.multiply(self.kd, self.derivative_error))
        print("Output: ", self.output)
        self.prev_error = self.error
        self.prev_integral_error = self.integral_error
        return self.output

        
        
    


