"""
    discord: @kialli
    github: @kchan5071

    PID six DOF methods
    this is a pretty standard implementation of a PID controller

"""

import numpy as np
from numpy.typing import NDArray

P_DEBUG = True

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

    def _get_error(self, initial_state: NDArray, desired_state: NDArray) -> None:
        # error is the difference between target and current state
        self.error = np.subtract(desired_state, initial_state)

        # integral errors build up over time, so:
        # prev error + ( current error * time)
        self.integral_error = self.prev_integral_error + self.error * self.dt

        # derivative errors is basically slope, so:
        # (current error - prev error) / time
        self.derivative_error = np.subtract(self.error, self.prev_error) / self.dt


    def update(self, initial_state: NDArray, desired_state: NDArray) -> NDArray:

        """
        updates errors, then returns pid values
        """

        # update error values
        self._get_error(initial_state, desired_state)

        # calculate output based on errors and k values
        # this is multidimensional so it needs to be done with arrays
        # output += (error * kp) + (integral_error * ki) + (derivative_error * kd)
        self.output = np.add(
            np.add(
                np.multiply(self.kp, self.error),
                np.multiply(self.ki, self.integral_error)),
                np.multiply(self.kd, self.derivative_error
            )
        )

        #update errors for next cycle
        self.prev_error = self.error
        self.prev_integral_error = self.integral_error

        # print debug
        if P_DEBUG:
            print("initial stae: ", initial_state)
            print("desired stae: ", desired_state)
            print("Output: ", self.output)
        return self.output
