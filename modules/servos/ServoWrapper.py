import modules.logger.better_logger as better_logger
from modules.motors.USB_Transmit    import USB_Transmitter

"""
github: @alicvo

This class is a wrapper for servo-based subsystem PWM control on CaraCara.
It updates shared memory PWM values for servo-controlled mechanisms,
including the dropper, grabbers, and torpedoes.

Default PWM values are stored in SERVO_COMMANDS. A custom pwm_value can be
passed to override the default value for testing or calibration.

Read the README for more information on how to use this class.

NOTE:
    This wrapper only updates shared memory values. The PWM values are sent
    to hardware when the main USB command packet is sent.
"""

class ServoWrapper:

    # Change these values as needed
    SERVO_COMMANDS = {
        "dropper": {
            "drop": 1500,
            "reset": 300,
            "close": 300,
            "open": 1500,
        },
        "grabber1": {
            "open": 1500,
            "close": 300,
        },
        "grabber2": {
            "open": 1500,
            "close": 300,
        },
        "torpedo": {
            "fire": 1500,
            "reset": 300,
        },
    }

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

    def dropper(self, command="drop", pwm_value=None):
        self.run_servo_command("dropper", command, pwm_value)

    def grabber1(self, command="close", pwm_value=None):
        self.run_servo_command("grabber1", command, pwm_value)

    def grabber2(self, command="close", pwm_value=None):
        self.run_servo_command("grabber2", command, pwm_value)

    def torpedo(self, command="fire", pwm_value=None):
        self.run_servo_command("torpedo", command, pwm_value)

    def run_servo_command(self, subsystem, command, pwm_value=None):
        if subsystem not in self.SERVO_COMMANDS:
            self.logger.log_error(f"ServoWrapper: invalid subsystem '{subsystem}'")
            return

        if command not in self.SERVO_COMMANDS[subsystem]:
            valid_commands = ", ".join(self.SERVO_COMMANDS[subsystem].keys())
            self.logger.log_error(
                f"ServoWrapper: invalid command '{command}' for '{subsystem}'. "
                f"Valid commands: {valid_commands}"
            )
            return

        pwm = pwm_value if pwm_value is not None else self.SERVO_COMMANDS[subsystem][command]
        self.set_pwm(subsystem, pwm)

    def set_pwm(self, subsystem, pwm_value):
        if subsystem not in self.servo_pwm:
            self.logger.log_error(f"ServoWrapper: invalid subsystem '{subsystem}'")
            return

        self.servo_pwm[subsystem].value = pwm_value
        self.logger.log_info(f"ServoWrapper: {subsystem} set to PWM {pwm_value}")
