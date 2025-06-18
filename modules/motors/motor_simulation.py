import numpy as np

class Simulation:
    def __init__(self, initial_state):
        self.state = initial_state
        self.motor_strength = .03
        self.motors_forces = np.array([
           # x        y        z        yaw     pitch    roll
            [ 0,      0,       -1,        0,      -1,     -1], # motor 0 (top front left)
            [ 1,      1,        0,       -1,       0,      0], # motor 1 (bottom front left)
            [ 0,      0,       -1,        0,       1,     -1], # motor 2 (top back left)
            [ 1,     -1,        0,       -1,       0,      0], # motor 3 (bottom back left)
            [ 0,      0,       -1,        0,       1,      1], # motor 4 (top back right)
            [ 1,     -1,        0,        1,       0,      0], # motor 5 (bottom back right)
            [ 0,      0,       -1,        0,      -1,      1], # motor 6 (top front right)
            [ 1,      1,        0,        1,       0,      0]  # motor 7 (bottom front right)
        ])

    def update(self, motor_string):
        force_vector = np.array([0, 0, 0, 0, 0, 0], dtype=float)
        for i in range(6):
            for j in range(8):
                force_vector[i] += self.motor_strength * self.motors_forces[j][i] * motor_string[j]
        self.state += force_vector
        return self.state
    
    def apply_monte_carlo(self, state):
        for i in range(6):
            state[i] += np.random.normal(0, 0.1)
        return state