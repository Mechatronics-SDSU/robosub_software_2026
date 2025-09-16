import numpy as np
import time

class MotorWrapper:

    def __init__(self): #, shared_memory_object): #(REMOVED FOR INTRO PROJECT)
        """
        MotorWrapper constructor
        """
        #self.shared_memory_object = shared_memory_object #(REMOVED FOR INTRO PROJECT)
        #self.usb_transmitter = USB_Transmitter() #(REMOVED FOR INTRO PROJECT)
        #-------------------------------------------------------------------------------------------------
        self.MOTOR_MAX    = 4000
        self.MOTOR_FACTOR = 1.0 # [0.0, 1.0] -- set ~0.1 for in air, ~0.3 in water
        #-------------------------------------------------------------------------------------------------

        self.motors = np.array([
            #LjoyX   LjoyY   RjoyX   RjoyY    Rtrig   Ltrig   LPad       RDpad
            
            # x        y        z        yaw     pitch    roll
            [ 0,      0,       1,        0,       1,     -1], # motor 0 FL0 (vertical)
            [-1,     -1,       0,        1,       0,      0], # motor 1 FL1
            [ 0,      0,      -1,        0,      -1,     -1], # motor 2 BL2 (vertical)
            [ 1,     -1,       0,       -1,       0,      0], # motor 3 BL3
            [ 0,      0,      -1,        0,      -1,      1], # motor 4 BR4 (veritcal)
            [ 1,      1,       0,        1,       0,      0], # motor 5 BR5
            [ 0,      0,       1,        0,       1,      1], # motor 6 FR6 (vertical)
            [-1,      1,       0,       -1,       0,      0]  # motor 7 FR7
        ])
        self.controls   = [0, 0, 0, 255, 0] # control values (kill, power off, lights R,G,B) FIXME assign to shared mem vals
        self.motor_vals = [0, 0, 0, 0, 0, 0, 0, 0] # motor values

    def valid(self, motor_val):
        """
        Returns a validated version of the motor value
        """
        motor_val = int(motor_val)
        if type(motor_val) != int and type(motor_val) != float: return 0 # return 0 if not a number
        # multiply clamped motor value by motor factor, cast to int
        return int(self.MOTOR_FACTOR * np.clip(motor_val, -self.MOTOR_MAX, self.MOTOR_MAX))

    
    """
    Movement functions expect an single integer for speed as parameter, range [-MOTOR_MAX to MOTOR_MAX]
    """
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

    def turn_left(self, value):
        self.move_from_matrix(np.array([0, 0, 0, self.valid(value), 0, 0]))

    def turn_right(self, value):
        self.move_from_matrix(np.array([0, 0, 0, self.valid(-value), 0, 0]))

    def turn_up(self, value):
        self.move_from_matrix(np.array([0, 0, 0, 0, self.valid(value), 0]))

    def turn_down(self, value):
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
        """
        Translates the direction vector matrix to motor values
        """
        #print(matrix)
        temp_list = np.round(np.dot(matrix, self.motors.transpose()))
        self.motor_vals += temp_list
        #print(temp_list)

    def send_command(self):
        """
        Sends commands to motors
        """
        send_data = np.concatenate((self.motor_vals, self.controls), axis=None).astype(int)
        for i, data in enumerate(send_data):
            send_data[i] = self.valid(data)
        print(send_data)
        #self.usb_transmitter.send_data(list(send_data)) # concatenate motor and control values (REMOVED FOR INTRO PROJECT)

        motor_values = self.motor_vals # save motor values
        #self.shared_memory_object.motor_values.value = motor_values # save to shared memory (REMOVED FOR INTRO PROJECT)
        self.stop() # reset motor values to 0s

        return motor_values # return motor values
    
if __name__ == "__main__":
    """
    Your Code Here
    Just run the file to test
    
    """