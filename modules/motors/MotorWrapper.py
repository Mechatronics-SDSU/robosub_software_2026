import numpy                                as np
from numpy.typing                           import NDArray
from shared_memory                          import SharedMemoryWrapper
from typing                                 import Union
import os, yaml


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
        usbData[10] = servo1State;
        usbData[11] = servo2State;
        usbData[12] = dropperState;
        usbData[13] = torpedoState;
        
        user_inputs = [
            1500, # motor 0
            1500,  # motor 1
            1500,  # motor 2
            1500,  # motor 3
            1500,  # motor 4
            1500,  # motor 5
            1500,  # motor 6
            1500,  # motor 7
            0,     # motor kill state (0 = alive, 1 = kill)
            0,     # power off state  (0 = on, 1 = off)
            0,     # servo 1 - pin30
            0,     # servo 2 - pin 29
            2000,     # dropper     (0 = closed, 1 = open)
            0,     # torpedo     (1000 fires right, 2000 fires left, 1500 is armed)

    NOTE: THIS WRAPPER IS MEANT FOR CARACARA ONLY, SCION USES A DIFFERENT MOTOR WRAPPER
'''


class MotorWrapper:

    def __init__(self, shared_memory_object):    
        self.shared_memory_object = shared_memory_object
        self.usb_transmitter = USB_Transmitter()
        #-------------------------------------------------------------------------------------------------
        self.MOTOR_MAX    = 400 # NOTE: Previously 4k
        self.MOTOR_STOP   = 1500
        self.MOTOR_MIN_US = 1100
        self.MOTOR_MAX_US = 1900
        self.MOTOR_FACTOR = 0
        try: # set motor factor from yaml
            with open(os.path.expanduser("~/robosub_software_2026/objects.yaml"), 'r') as file: # read from yaml
                data = yaml.safe_load(file)
                self.MOTOR_FACTOR = float(data['motor_factor'])
        except KeyError:
            print("ERROR: Invalid data format in objects.yaml, using 0")
            
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
        self.controls   = [0, 0, 0, 0, 0, 0] # control values (kill, power off, servo1, servo2, dropper, torpedo) FIXME assign to shared mem vals
        self.motor_vals = [0, 0, 0, 0, 0, 0, 0, 0] # motor values

    # returns a validated version of the motor value
    # def valid(self, motor_val: Union[float, int]) -> int:
    #     motor_val = int(motor_val)
    #     if type(motor_val) != int and type(motor_val) != float: return 0 # return 0 if not a number
    #     # multiply clamped motor value by motor factor, cast to int
    #     val: int = int(self.MOTOR_FACTOR * np.clip(motor_val, -self.MOTOR_MAX, self.MOTOR_MAX))
    #     print(f"motor_val = {motor_val}\t val = {val}\t return = {val + 1500}")
    #     return val + 1500
    def valid(self, motor_val):
        """
        Convert centered motor command -400..400 to T200 PWM us 1100..1900.
        """
        if not isinstance(motor_val, (int, float, np.integer, np.floating)):
            return self.MOTOR_STOP

        centered = float(np.clip(motor_val, -self.MOTOR_MAX, self.MOTOR_MAX))
        offset = self.MOTOR_FACTOR * centered
        pwm = int(round(self.MOTOR_STOP + offset))
        return int(np.clip(pwm, self.MOTOR_MIN_US, self.MOTOR_MAX_US))

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

    # #sends commands to motors
    # def send_command(self) -> list:
    #     try:
    #         send_data = np.concatenate((self.motor_vals, self.controls), axis=None).astype(int)
    #         for i, data in enumerate(send_data):
    #             send_data[i] = self.valid(data)
    #         self.usb_transmitter.send_data(list(send_data)) # concatenate motor and control values
    #     except Exception as e:
    #         print(f"Error sending command: {e}")

    #     motor_values = self.motor_vals # save motor values
    #     self.stop() # reset motor values to 0s

    #     return motor_values # return motor values
    def send_command(self) -> list:
        motor_values = self.motor_vals.copy()

        try:
            motor_pwm = np.array([self.valid(v) for v in self.motor_vals], dtype=int)
            control_data = np.array(self.controls, dtype=int)

            send_data = np.concatenate((motor_pwm, control_data), axis=None).astype(int)

            self.usb_transmitter.send_data(list(send_data))

        except Exception as e:
            print(f"Error sending command: {e}")

        self.stop()
        return motor_values