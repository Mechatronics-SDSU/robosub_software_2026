import numpy as np
from USB_Transmit import USB_Transmitter
"""
usbData[0] = motor0; 
usbData[1] = motor1; 
usbData[2] = motor2; 
usbData[3] = motor3; 
usbData[4] = motor4; 
usbData[5] = motor5;
usbData[6] = motor6; 
usbData[7] = motor7; 
usbData[8] = killState; 
usbData[9] = powerOffState; 
usbData[10] = red; 
usbData[11] = green; 
usbData[12] = blue;
"""

class MotorWrapper:

    def __init__(self):    
        self.usb_transmitter = USB_Transmitter()
        #-------------------------------------------------------------------------------------------------
        self.MOTOR_MAX    = 40000
        self.MOTOR_FACTOR = 0.1 # [0.0, 1.0] -- set ~0.1 for in air, ~0.3 in water
        #-------------------------------------------------------------------------------------------------

        self.motors = np.array([
            #LjoyX   LjoyY   RjoyX   RjoyY    Rtrig   Ltrig   LPad       RDpad
            
            # x        y        z        yaw     pitch    roll
            [  0,      0,       1,       -2,       0,      1], # motor 0 FL0 (vertical)
            [ -2,      1,       0,        0,       1,      0], # motor 1 FL1
            [  0,      0,      -2,        1,       0,      1], # motor 2 BL2 (vertical)
            [  1,      1,       0,        0,      -2,      0], # motor 3 BL3
            [  0,      0,      -2,        1,       0,     -2], # motor 4 BR4 (veritcal)
            [  1,     -2,       0,        0,       1,      0], # motor 5 BR5
            [  0,      0,       1,       -2,       0,     -2], # motor 6 FR6 (vertical)
            [ -2,     -2,       0,        0,      -2,      0]  # motor 7 FR7
        ])
        self.controls   = [0, 0, 0, 255, 0] # control values (kill, power off, lights R,G,B) FIXME assign to shared mem vals
        self.motor_vals = [0, 0, 0, 0, 0, 0, 0, 0] # motor values

    # returns a validated version of the motor value
    def valid(self, motor_val):
        if type(motor_val) != int and type(motor_val) != float: return 0 # return 0 if not a number
        # multiply clamped motor value by motor factor, cast to int
        return int(self.MOTOR_FACTOR * np.clip(motor_val, -self.MOTOR_MAX, self.MOTOR_MAX))

    def move_forward(self, value):
        self.move_from_matrix(np.array([self.valid(value), 0, 0, 0, 0, 0]))

    def move_backward(self, value):
        self.move_from_matrix(np.array([self.valid(-value), 0, 0, 0, 0, 0]))

    def move_left(self, value):
        self.move_from_matrix(np.array([0, self.valid(value), 0, 0, 0, 0]))

    def move_right(self, value):
        self.move_from_matrix(np.array([0, self.valid(-value), 0, 0, 0, 0]))

    def move_up(self, value):
        self.move_from_matrix(np.array([0, 0, self.valid(value), 0, 0, 0]))

    def move_down(self, value):
        self.move_from_matrix(np.array([0, 0, self.valid(-value), 0, 0, 0]))

    def turn_up(self, value):
        self.move_from_matrix(np.array([0, 0, 0, self.valid(value), 0, 0]))

    def turn_down(self, value):
        self.move_from_matrix(np.array([0, 0, 0, self.valid(-value), 0, 0]))

    def turn_left(self, value):
        self.move_from_matrix(np.array([0, 0, 0, 0, self.valid(value), 0]))

    def turn_right(self, value):
        self.move_from_matrix(np.array([0, 0, 0, 0, self.valid(-value), 0]))

    def roll_left(self, value):
        self.move_from_matrix(np.array([0, 0, 0, 0, 0, self.valid(value)]))

    def roll_right(self, value):
        self.move_from_matrix(np.array([0, 0, 0, 0, 0, self.valid(-value)]))
    
    def stop(self): 
        self.motor_vals = [0,0,0,0,0,0,0,0]

    def kill(self):
        self.stop()


    def move_from_matrix(self, matrix):
        #translate the direction vector matrix to motor values
        # print(matrix)
        temp_list = np.round(np.dot(matrix, self.motors.transpose()))
        self.motor_vals += temp_list
        # print(temp_list)

    #sends commands to motors
    def send_command(self):
        send_data = np.concatenate((self.motor_vals, self.controls), axis=None)
        print(type(list(send_data)))
        self.usb_transmitter.send_data(list(send_data)) # concatenate motor and control values

        motor_values = self.motor_vals # save motor values
        self.stop() # reset motor values to 0s

        return motor_values # return motor values