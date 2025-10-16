import numpy                                as np
from numpy.typing                           import NDArray
from shared_memory                          import SharedMemoryWrapper
from typing                                 import Union


#this is to handle errors in using the CLI for testing motors
try:
    from modules.motors.USB_Transmit        import USB_Transmitter
except:
    from USB_Transmit                       import USB_Transmitter

'''
    discord: @kialli, @.kech
    github: @kchan5071, @rsunderr
    
    This class is a wrapper for the USB interface. It is used to send commands to the motors.
    contains:
        move methods for motors with the following protocol:
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

    NOTE: THIS WRAPPER IS MEANT FOR CARACARA ONLY, SCION USES A DIFFERENT MOTOR WRAPPER
'''


class MotorWrapper:

    def __init__(self, shared_memory_object):    
        self.shared_memory_object = shared_memory_object
        self.usb_transmitter = USB_Transmitter()
        #-------------------------------------------------------------------------------------------------
        self.MOTOR_MAX    = 4000
        self.MOTOR_FACTOR = 0.7 # [0.0, 1.0] -- set ~0.1 for in air, ~0.7 in water
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

    # returns a validated version of the motor value
    def valid(self, motor_val: Union[float, int]) -> int:
        motor_val = int(motor_val)
        if type(motor_val) != int and type(motor_val) != float: return 0 # return 0 if not a number
        # multiply clamped motor value by motor factor, cast to int
        return int(self.MOTOR_FACTOR * np.clip(motor_val, -self.MOTOR_MAX, self.MOTOR_MAX))

    def move_forward(self, value: Union[float, int]) -> None:
        self.move_from_matrix(np.array([self.valid(value), 0, 0, 0, 0, 0]))

    def move_backward(self, value: Union[float, int]) -> None:
        self.move_from_matrix(np.array([self.valid(-value), 0, 0, 0, 0, 0]))

    def move_left(self, value: Union[float, int]) -> None:
        self.move_from_matrix(np.array([0, self.valid(value), 0, 0, 0, 0]))

    def move_right(self, value: Union[float, int]) -> None:
        self.move_from_matrix(np.array([0, self.valid(-value), 0, 0, 0, 0]))

    def move_up(self, value: Union[float, int]) -> None:
        self.move_from_matrix(np.array([0, 0, self.valid(value), 0, 0, 0]))

    def move_down(self, value: Union[float, int]) -> None:
        self.move_from_matrix(np.array([0, 0, self.valid(-value), 0, 0, 0]))

    def turn_left(self, value: Union[float, int]) -> None:
        self.move_from_matrix(np.array([0, 0, 0, self.valid(value), 0, 0]))

    def turn_right(self, value: Union[float, int]) -> None:
        self.move_from_matrix(np.array([0, 0, 0, self.valid(-value), 0, 0]))

    def turn_up(self, value: Union[float, int]) -> None:
        self.move_from_matrix(np.array([0, 0, 0, 0, self.valid(value), 0]))

    def turn_down(self, value: Union[float, int]) -> None:
        self.move_from_matrix(np.array([0, 0, 0, 0, self.valid(-value), 0]))

    def roll_left(self, value: Union[float, int]) -> None:
        self.move_from_matrix(np.array([0, 0, 0, 0, 0, self.valid(value)]))

    def roll_right(self, value: Union[float, int]) -> None:
        self.move_from_matrix(np.array([0, 0, 0, 0, 0, self.valid(-value)]))
    
    def stop(self) -> None: 
        self.motor_vals = [0,0,0,0,0,0,0,0]

    def kill(self) -> None:
        self.stop()


    def move_from_matrix(self, matrix: NDArray) -> None:
        #translate the direction vector matrix to motor values
        temp_list = np.round(np.dot(matrix, self.motors.transpose()))
        self.motor_vals += temp_list

    #sends commands to motors
    def send_command(self) -> list:
        send_data = np.concatenate((self.motor_vals, self.controls), axis=None).astype(int)
        for i, data in enumerate(send_data):
            send_data[i] = self.valid(data)
        self.usb_transmitter.send_data(list(send_data)) # concatenate motor and control values

        motor_values = self.motor_vals # save motor values
        self.stop() # reset motor values to 0s

        return motor_values # return motor values