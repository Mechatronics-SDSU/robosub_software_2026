# Servo Wrapper Interface

Software wrapper for CaraCara's servo-based subsystem controls. This interface provides a high-level way to update PWM values for servo-controlled mechanisms during a run, including the dropper, grabbers, and torpedoes.

The wrapper only updates PWM values in shared memory. These values are sent to the STM32 when the main USB command packet is sent.

## Outline

* Date Created: 05/25/2026
* Contributors:

  * Alice Vo

    * GitHub: @alicvo
    * Discord: @alicvo
* Dependencies:

  * Python 3.11+
  * Pyserial 3.5

## Key Files

* `ServoWrapper.py`

  * Main wrapper interface for updating shared memory PWM values for servo-controlled subsystems
* `test_servo.py`

  * Test script for validating servo subsystem PWM updates

## Usage

Run the servo test script:

```bash
python test_servo.py
```

Create a `ServoWrapper` object using the shared memory object:

```python
servo_wrapper = ServoWrapper(shared_memory_object)
```

Then call each servo subsystem with a command.

```python
servo_wrapper.dropper("drop")
servo_wrapper.dropper("reset")

servo_wrapper.grabber1("open")
servo_wrapper.grabber1("close")

servo_wrapper.grabber2("open")
servo_wrapper.grabber2("close")

servo_wrapper.torpedo("fire")
servo_wrapper.torpedo("reset")
```

Each command uses its default PWM value from `ServoWrapper.py`.

## Custom PWM Override

A custom PWM value can be passed with `pwm_value` to override the default value for a command.

```python
servo_wrapper.dropper("drop", pwm_value=1500)
servo_wrapper.grabber1("open", pwm_value=1500)
servo_wrapper.torpedo("fire", pwm_value=1500)
```

This is mainly useful for testing, tuning, or calibrating servo positions.

## Available Commands

### Dropper

```python
servo_wrapper.dropper("drop")
servo_wrapper.dropper("reset")
```

### Grabber 1

```python
servo_wrapper.grabber1("open")
servo_wrapper.grabber1("close")
```

### Grabber 2

```python
servo_wrapper.grabber2("open")
servo_wrapper.grabber2("close")
```

### Torpedo

```python
servo_wrapper.torpedo("fire")
servo_wrapper.torpedo("reset")
```

## Generic PWM Command

The `set_pwm()` method can be used to directly set a PWM value for a subsystem.

```python
servo_wrapper.set_pwm("dropper", 1500)
servo_wrapper.set_pwm("grabber1", 300)
servo_wrapper.set_pwm("grabber2", 300)
servo_wrapper.set_pwm("torpedo", 1500)
```

Valid subsystem names are:

```python
"dropper"
"grabber1"
"grabber2"
"torpedo"
```

## PWM Constants

Default PWM values are stored in the `SERVO_COMMANDS` dictionary in `ServoWrapper.py`.

Example:

```python
SERVO_COMMANDS = {
    "dropper": {
        "drop": 1500,
        "reset": 300,
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
```

Edit these values as needed for servo calibration.

## Status

Current status: In testing
