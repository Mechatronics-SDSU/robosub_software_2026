# Servo Wrapper Interface

Software wrapper for CaraCara's servo-based subsystem controls. Provides a high-level interface for updating PWM values for servo-controlled mechanisms during a run, including the dropper, grabber, and torpedoes.

### Outline

- Date Created: 05/25/2026
- Contributors:
    - Alice Vo (GitHub: @alicvo, Discord: @alicvo)
- Dependencies:
    - Python 3.11+
    - Pyserial 3.5

### Key Files

- `servoWrapper.py`
    - Main wrapper interface for updating shared memory PWM values for servo-controlled subsystems
- `test_servo.py`
    - Test script for validating servo subsystem PWM updates

### Usage

- Run `python test_servo.py` to validate functionality

The servo wrapper updates PWM values in shared memory. These values are sent to the STM32 when the main USB command packet is sent.

Each subsystem command can be called without an argument to use its default PWM constant, or with a custom PWM value to override the default.

Example:

    servo_wrapper.dropper_drop()
    servo_wrapper.dropper_drop(1500)

**Dropper commands:**
- `dropper_drop()`
- `dropper_reset()`

**Grabber commands:**
- `grabber1_open()`
- `grabber1_close()`
- `grabber2_open()`
- `grabber2_close()`

**Torpedo commands:**
- `torpedo_fire()`
- `torpedo_reset()`

**Generic PWM command:**
- `set_pwm(subsystem, pwm_value)`
    - Sets a PWM value for a given servo subsystem name
    - Example: `set_pwm("dropper", 1500)`
    - Example: `set_pwm("grabber1", 300)`

Edit the PWM constants in `servoWrapper.py` as needed.

### Notes

- Intended specifically for CaraCara's servo-controlled mechanisms
- This wrapper only updates shared memory values
- PWM values are sent to hardware when the main USB command packet is sent
- `set_pwm()` logs an error if an invalid subsystem name is passed

### Status

- Current status: In testing
