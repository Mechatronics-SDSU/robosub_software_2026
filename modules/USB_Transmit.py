import serial
import struct

from modules.logger.logger import Logger

BAUD_RATE = 115200

'''
    discord: @kialli
    github: @kchan5071

    Handles USB transmission from the motor/dropper/grabber/torpedo wrappers
    to the central STM32 microcontroller. Owns the one shared serial
    connection and the full firmware packet state. Subsystem wrappers call
    into this instead of opening their own serial connections.

    Packet layout (all fields 4 bytes, little-endian, offsets 0-52):
        0  motorValues[0]        32 killState
        4  motorValues[1]        36 powerOff
        8  motorValues[2]        40 servo1
        12 motorValues[3]        44 servo2
        16 motorValues[4]        48 dropper
        20 motorValues[5]        52 torpedo
        24 motorValues[6]
        28 motorValues[7]

    Acceptable values:
        motors:     1100-1900, 1500 neutral
        servos:     900-1900, 1500 neutral
        killState:  0 alive, 1 kill
        powerOff:   0 on, 1 off
        dropper:    0 open, 1 closed
        torpedo:    0 armed, 1 fire
'''

MOTOR_MIN, MOTOR_MAX, MOTOR_NEUTRAL = 1100, 1900, 1500
SERVO_MIN, SERVO_MAX, SERVO_NEUTRAL = 900, 1900, 1500


class USB_Transmitter:
    def __init__(self):
        self.logger = Logger()
        self.srl = None
        for port in ["/dev/ttyACM0"]:
            try:
                self.srl = serial.Serial(port, BAUD_RATE)
                self.logger.info(f"Connected on {port}")
                break
            except serial.SerialException as e:
                self.logger.error(f"Failed to connect on {port}: {e}")

        # full firmware packet state, safe startup defaults------------------------------------------------------------------
        self.motor_vals = [MOTOR_NEUTRAL] * 8
        self.kill_state = 1     # 1 = kill, safe default until explicitly un-killed
        self.power_off  = 0
        self.servo1     = SERVO_NEUTRAL
        self.servo2     = SERVO_NEUTRAL
        self.dropper    = 1     # 1 = closed
        self.torpedo    = 0     # 0 = armed (not firing)

    # VALIDATION----------------------------------------------------------------------------------------------------------------
    def _clamp_motor(self, value: int) -> int:
        value = int(value)
        if value < MOTOR_MIN or value > MOTOR_MAX:
            self.logger.error(f"Motor value {value} out of range [{MOTOR_MIN},{MOTOR_MAX}], clamping")
        return max(MOTOR_MIN, min(MOTOR_MAX, value))

    def _clamp_servo(self, value: int) -> int:
        value = int(value)
        if value < SERVO_MIN or value > SERVO_MAX:
            self.logger.error(f"Servo value {value} out of range [{SERVO_MIN},{SERVO_MAX}], clamping")
        return max(SERVO_MIN, min(SERVO_MAX, value))

    def _validate_binary(self, value: int, field_name: str, current: int) -> int:
        if value not in (0, 1):
            self.logger.error(f"{field_name} must be 0 or 1, got {value}, keeping current value {current}")
            return current
        return value

    # PACKET----------------------------------------------------------------------------------------------------------------------
    def build_packet(self) -> bytes:
        """
        Builds the full 14-field firmware packet in the required order.
        """
        packet_values = self.motor_vals + [
            self.kill_state,
            self.power_off,
            self.servo1,
            self.servo2,
            self.dropper,
            self.torpedo,
        ]
        packed_data = b''
        for value in packet_values:
            packed_data += struct.pack('<i', value)
        return packed_data

    def send_packet(self) -> None:
        """
        Sends the full firmware packet over the serial connection.
        """
        if self.srl is None:
            self.logger.error("Unable to send, no serial connection.")
            return
        self.srl.write(self.build_packet())

    def send_data(self, motor_vals: list) -> None:
        """
        Backward-compatible entry point for old motor-only code. Takes only
        the first 8 values as motor values (works with both a plain 8-value
        list and the old 13-value motor+controls list), updates stored motor
        state, then sends the full firmware packet.
        """
        self.set_motors(motor_vals[:8])

    # MOTORS------------------------------------------------------------------------------------------------------------------------
    def set_motor(self, index: int, value: int) -> None:
        if index < 0 or index >= 8:
            self.logger.error(f"Invalid motor index {index}")
            return
        self.motor_vals[index] = self._clamp_motor(value)
        self.send_packet()

    def set_motors(self, motor_vals: list) -> None:
        if len(motor_vals) != 8:
            self.logger.error(f"Expected 8 motor values, got {len(motor_vals)}")
            return
        self.motor_vals = [self._clamp_motor(value) for value in motor_vals]
        self.send_packet()

    def stop_motors(self) -> None:
        self.motor_vals = [MOTOR_NEUTRAL] * 8
        self.send_packet()

    # KILL / POWER--------------------------------------------------------------------------------------------------------------
    def kill(self) -> None:
        self.set_kill_state(1)

    def unkill(self) -> None:
        self.set_kill_state(0)

    def set_kill_state(self, value: int) -> None:
        self.kill_state = self._validate_binary(value, "killState", self.kill_state)
        self.send_packet()

    def request_power_off(self) -> None:
        self.set_power_off(1)

    def set_power_off(self, value: int) -> None:
        self.power_off = self._validate_binary(value, "powerOff", self.power_off)
        self.send_packet()

    # GRABBER SERVOS------------------------------------------------------------------------------------------------------------
    def set_servo1(self, value: int) -> None:
        self.servo1 = self._clamp_servo(value)
        self.send_packet()

    def set_servo2(self, value: int) -> None:
        self.servo2 = self._clamp_servo(value)
        self.send_packet()

    def set_grabber_servos(self, servo1: int, servo2: int) -> None:
        self.servo1 = self._clamp_servo(servo1)
        self.servo2 = self._clamp_servo(servo2)
        self.send_packet()

    # DROPPER-------------------------------------------------------------------------------------------------------------------
    def open_dropper(self) -> None:
        self.set_dropper(0)

    def close_dropper(self) -> None:
        self.set_dropper(1)

    def set_dropper(self, value: int) -> None:
        self.dropper = self._validate_binary(value, "dropper", self.dropper)
        self.send_packet()

    # TORPEDO-------------------------------------------------------------------------------------------------------------------
    def arm_torpedo(self) -> None:
        self.set_torpedo(0)

    def fire_torpedo(self) -> None:
        self.set_torpedo(1)

    def set_torpedo(self, value: int) -> None:
        self.torpedo = self._validate_binary(value, "torpedo", self.torpedo)
        self.send_packet()
