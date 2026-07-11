import subprocess, time

from shared_memory                          import SharedMemoryWrapper
from fsm.modem_fsm                          import Modem_FSM
from modules.motors.MotorWrapper            import MotorWrapper
from modules.motors.USB_Transmit            import USB_Transmitter
from modules.logger.logger                  import Logger

"""
    Standalone background modem listener for Caracara.

    Loops forever: waits for a DATA frame over the M16 modem, and on a
    successful receive, turns the sub in place at reduced power for
    MOTOR_CONFIRM_DURATION seconds as a visible "message received"
    confirmation, then goes back to listening for the next one.

    This bypasses Modem_FSM's built-in PID-tracked wiggle (the
    WIGGLE_LEFT/CENTER/RIGHT states) entirely -- those need a real PID +
    DVL process to do anything (see fsm/modem_fsm.py's docstring) and are
    left wired as-is for later. Here the motors are driven directly
    instead, so the confirmation works today without PID/DVL set up.

    The sender side is the existing test_fsm_ctrl.py, run from a dev
    machine with its own modem:
        python test_fsm_ctrl.py --role sender --port COM7 --task-code 2

    FILL IN BEFORE RUNNING ON THE SUB:
        MODEM_PORT -- the modem's serial device path (e.g. "/dev/ttyUSB0").
        Find it with `ls /dev/serial/by-id/` or `dmesg | grep tty` after
        plugging the modem in. Linux enumerates USB serial ports by
        arrival order, so this can shift between reboots/USB hubs --
        don't assume it stays whatever it was last time, unlike the motor
        controller's fixed /dev/ttyACM0.
"""

MODEM_PORT        = None  # TODO: fill in, e.g. "/dev/ttyUSB0"
MODEM_CHANNEL     = 1
MODEM_POWER_LEVEL = 4

LOOP_DELAY = 0.2  # seconds between Modem_FSM.loop() ticks

MOTOR_CONFIRM_DURATION = 10.0  # seconds to turn for, confirming a message was received
MOTOR_CONFIRM_SPEED    = 75    # low value out of MotorWrapper's +-400 range -- slow/gentle turn
MOTOR_COMMAND_INTERVAL = 0.2   # seconds between repeated motor commands (matches pid_interface.py's cadence)

logger = Logger()


def fix_modem_permissions() -> None:
    """
    Best-effort permission fix for the modem's serial device, same pattern
    launch.py uses for the motor controller's /dev/ttyACM0. Non-fatal if it
    fails -- the modem might already be accessible, or this might be run
    before the device is plugged in / MODEM_PORT is filled in.
    """
    try:
        subprocess.run(["sudo", "chmod", "777", MODEM_PORT], check=True)
        logger.info(f"Permissions changed for {MODEM_PORT}")
    except Exception as e:
        logger.warning(f"Could not chmod {MODEM_PORT}: {e}")


def confirm_receipt_with_motors(shared_memory_object) -> None:
    """
    Turn in place at reduced power for MOTOR_CONFIRM_DURATION seconds, then
    stop. Drives the motors directly (bypassing PID/target_yaw) since no
    PID process is running in this script.
    """
    motor_wrapper = MotorWrapper(shared_memory_object)
    logger.info(f"Confirming receipt: turning for {MOTOR_CONFIRM_DURATION}s")

    start = time.monotonic()
    while time.monotonic() - start < MOTOR_CONFIRM_DURATION:
        motor_wrapper.turn_left(MOTOR_CONFIRM_SPEED)
        motor_wrapper.send_command()
        time.sleep(MOTOR_COMMAND_INTERVAL)

    motor_wrapper.stop()
    motor_wrapper.send_command()  # send the zeroed command so the motors actually stop
    logger.info("Confirmation turn complete")


def run_one_handshake(shared_memory_object) -> bool:
    """
    Run one Modem_FSM listen -> receive -> (no-op wiggle) -> ack -> done
    cycle. Returns whether it completed successfully.
    """
    mode = Modem_FSM(
        shared_memory_object, [], role="listener", port=MODEM_PORT,
        channel=MODEM_CHANNEL, power_level=MODEM_POWER_LEVEL,
    )
    mode.start()

    while shared_memory_object.running.value and not mode.complete:
        mode.loop()
        time.sleep(LOOP_DELAY)

    return mode.success


def main() -> None:
    if MODEM_PORT is None:
        raise ValueError("Set MODEM_PORT at the top of this script before running on the sub")

    fix_modem_permissions()
    shared_memory_object = SharedMemoryWrapper()

    logger.info("Caracara modem listener starting, waiting for messages")
    while shared_memory_object.running.value:
        try:
            success = run_one_handshake(shared_memory_object)
        except Exception as e:
            logger.error(f"Handshake attempt failed: {e}")
            time.sleep(2.0)  # brief pause before retrying, avoids a tight crash loop
            continue

        if success:
            confirm_receipt_with_motors(shared_memory_object)
        else:
            logger.warning("Handshake did not complete successfully, listening again")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("keyboard interrupt detected, stopping program")
    finally:
        transmitter = USB_Transmitter()
        transmitter.kill_motors()
