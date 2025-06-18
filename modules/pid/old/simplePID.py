import numpy as np

class PID:
    def __init__(self, Kp, Ki, Kd, target):
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd
        self.target = target
        self.error = 0
        self.prev_error = 0
        self.integral_error = 0
        self.derivative_error = 0
        self.output = 0

    def update(self, measurement, dt):
        self.error = self.target - measurement
        self.integral_error += self.error * dt
        self.derivative_error = (self.error - self.prev_error) / dt
        self.output = self.Kp * self.error + self.Ki * self.integral_error + self.Kd * self.derivative_error
        self.prev_error = self.error
        return self.output
    
    def set_target(self, target):
        self.target = target

