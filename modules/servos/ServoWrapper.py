import modules.logger.better_logger as better_logger
from modules.motors.USB_Transmit    import USB_Transmitter

'''
    github: @alicvo
    
    This class is a wrapper for servo-based subsystem PWM control on CaraCara.
    It updates shared memory PWM values for servo-controlled subsystems,
    including the dropper, grabber, and torpedoes.

    contains:
        dropper_drop method: sets dropper PWM in shared memory to drop value
        dropper_reset method: sets dropper PWM in shared memory to reset value

        grabber1_open method: sets grabber servo 1 PWM in shared memory to open value
        grabber1_close method: sets grabber servo 1 PWM in shared memory to close value
        grabber2_open method: sets grabber servo 2 PWM in shared memory to open value
        grabber2_close method: sets grabber servo 2 PWM in shared memory to close value

        torpedo_fire method: sets torpedo PWM in shared memory to fire value
        torpedo_reset method: sets torpedo PWM in shared memory to reset value
        
        set_pwm method: sets PWM in shared memory for a given servo subsystem name

    NOTE: this wrapper only updates shared memory values. The PWM values are sent
            to hardware when the main USB command packet is sent.
'''

class ServoWrapper:
    # change these values as needed
    DROPPER_DROP_PWM = 1500
    DROPPER_RESET_PWM = 300

    GRABBER1_OPEN_PWM = 1500
    GRABBER1_CLOSE_PWM = 300
    GRABBER2_OPEN_PWM = 1500
    GRABBER2_CLOSE_PWM = 300

    TORPEDO_FIRE_PWM = 1500
    TORPEDO_RESET_PWM = 300
    
    def __init__(self, shared_memory_object):
        self.usb_transmitter = USB_Transmitter()
        self.logger = better_logger.Better_Logger()
        self.shared_memory_object = shared_memory_object

        self.servo_pwm = {
            "dropper": self.shared_memory_object.dropper_pwm,
            "grabber1": self.shared_memory_object.grabber1_pwm,
            "grabber2": self.shared_memory_object.grabber2_pwm,
            "torpedo": self.shared_memory_object.torpedo_pwm,
        }

    def dropper_drop(self, pwm_value=None):
        pwm = pwm_value if pwm_value is not None else self.DROPPER_DROP_PWM
        self.send_pwm("dropper", pwm)

    def dropper_reset(self, pwm_value=None):
        pwm = pwm_value if pwm_value is not None else self.DROPPER_RESET_PWM
        self.send_pwm("dropper", pwm)

    def grabber1_open(self, pwm_value=None):
        pwm = pwm_value if pwm_value is not None else self.GRABBER1_OPEN_PWM
        self.send_pwm("grabber1", pwm)

    def grabber1_close(self, pwm_value=None):
        pwm = pwm_value if pwm_value is not None else self.GRABBER1_CLOSE_PWM
        self.send_pwm("grabber1", pwm)

    def grabber2_open(self, pwm_value=None):
        pwm = pwm_value if pwm_value is not None else self.GRABBER2_OPEN_PWM
        self.send_pwm("grabber2", pwm)

    def grabber2_close(self, pwm_value=None):
        pwm = pwm_value if pwm_value is not None else self.GRABBER2_CLOSE_PWM
        self.send_pwm("grabber2", pwm)

    def torpedo_fire(self, pwm_value=None):
        pwm = pwm_value if pwm_value is not None else self.TORPEDO_FIRE_PWM
        self.send_pwm("torpedo", pwm)

    def torpedo_reset(self, pwm_value=None):
        pwm = pwm_value if pwm_value is not None else self.TORPEDO_RESET_PWM
        self.send_pwm("torpedo", pwm)

    def set_pwm(self, subsystem, pwm_value):
        if subsystem not in self.servo_pwm:
            self.logger.log_error(f"ServoWrapper: invalid subsystem '{subsystem}'")
            return

        self.servo_pwm[subsystem].value = pwm_value
        self.logger.log_info(f"ServoWrapper: {subsystem} set (PWM: {pwm_value})")