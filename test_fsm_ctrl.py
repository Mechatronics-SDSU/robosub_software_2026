import argparse, logging, subprocess, time

# the shared Logger class defaults to DEBUG, which floods modem testing with
# a "Returning None"/"Buffer length" line on every idle poll
logging.getLogger("default").setLevel(logging.INFO)

# import FSMs to test
from shared_memory                          import SharedMemoryWrapper
from fsm.gate_fsm                           import Gate_FSM
from fsm.octagon_fsm                        import Octagon_FSM
from fsm.slalom_fsm                         import Slalom_FSM
from fsm.return_fsm                         import Return_FSM
from fsm.prequal_fsm                        import Prequal_FSM
from fsm.coinflip_fsm                       import CoinFlip_FSM
from fsm.modem_fsm                          import Modem_FSM, FRAME_TYPE_DATA
from fsm.torpedo_fsm                        import Torpedo_FSM
from fsm.dropper_fsm                        import Dropper_FSM
from fsm.grabber_fsm                        import Grabber_FSM

from fsm_test_helpers                       import (
    FakeModem, FakeSignalWrapper, drift_toward_targets, FAKE_TORPEDO_CIRCLE_DATA,
    FAKE_DROPPER_DETECTIONS, FAKE_GRABBER_DETECTIONS
)

"""
    discord: @.kech
    github: @rsunderr

    General FSM test controller.

    Based on test_msn_ctrl.py, but runs ONE fsm at a time so it can be
    tested/debugged on its own instead of running the whole mission chain.

    HOW TO RUN:
        1. set FSM_TO_TEST below to the fsm you want to test
        2. python test_fsm_ctrl.py

    HOW TO ADD A NEW FSM:
        1. import the FSM class at the top of this file
        2. add a matching case for it inside build_fsm()

    MODEM ON ONE COMPUTER, TWO TERMINALS:
        Set FSM_TO_TEST = "modem" and FAKE_INPUT = False below (this part
        is the same for both terminals), then pass --role/--port/--task-code/
        --color-flag on the command line so each terminal can use different
        settings without editing the file in between:

            python test_fsm_ctrl.py --role listener --port COM7
            python test_fsm_ctrl.py --role sender --port COM8 --task-code 2 --color-flag

        Start the listener terminal first. CLI flags override
        MODEM_ROLE/MODEM_PORT/MODEM_TASK_CODE below; omit them to fall
        back to those constants.
"""

# create shared memory object
shared_memory_object = SharedMemoryWrapper()
DELAY = 0.2 # loop delay, raise this to slow down/step through states

FAKE_INPUT = False # fake dvl movement + fake modem messages, turn off once testing on real hardware
FAKE_MODEM_DATA_FRAME = { # data frame the fake modem "receives" when testing the modem listener, set to None for no message
    "frame_number": 0, "frame_type": FRAME_TYPE_DATA, "color_flag": 0, "task_code": 2,
}

# -----------------------------------------------------------------------------------
# CHOOSE WHICH FSM TO TEST HERE
# -----------------------------------------------------------------------------------
FSM_TO_TEST = "modem" # gate, octagon, slalom, return, prequal, coinflip, modem, torpedo, dropper, grabber
TEST_ROLE = "survey_and_repair" # survey_and_repair or search_and_rescue, used by dropper and grabber

# modem hardware settings, used when FSM_TO_TEST == "modem" and FAKE_INPUT = False.
# Run this file once per sub with the opposite MODEM_ROLE and each sub's real COM port.
MODEM_ROLE       = "listener" # "sender" or "listener" -- give each of the two subs the opposite role
MODEM_PORT       = "COM_TEST" # e.g. "COM7" on Windows or "/dev/ttyUSB0" on Linux
MODEM_TASK_CODE  = 2          # 0-3, the task code to send (sender role) or expect (listener role, informational only)
MODEM_COLOR_FLAG = False

def build_fsm(name: str):
    """
    Build and return the FSM instance to test, chosen by name
    """
    match(name):
        case "gate":
            return Gate_FSM(shared_memory_object, [])
        case "octagon":
            return Octagon_FSM(shared_memory_object, [])
        case "slalom":
            return Slalom_FSM(shared_memory_object, [])
        case "return":
            return Return_FSM(shared_memory_object, [])
        case "prequal":
            return Prequal_FSM(shared_memory_object, [])
        case "coinflip":
            return CoinFlip_FSM(shared_memory_object, [])
        case "modem":
            return Modem_FSM(shared_memory_object, [], role=MODEM_ROLE, port=MODEM_PORT,
                              task_code=MODEM_TASK_CODE, color_flag=MODEM_COLOR_FLAG)
        case "torpedo":
            # FakeSignalWrapper prints instead of firing real hardware, safe by default for testing.
            # For a real run, build a real modules.signals.SignalWrapper from the shared
            # USB_Transmitter and pass it in as signal_wrapper instead (see launch.py).
            return Torpedo_FSM(shared_memory_object, [], signal_wrapper=FakeSignalWrapper())
        case "dropper":
            # FakeSignalWrapper prints instead of actuating real hardware, safe by default for testing.
            return Dropper_FSM(shared_memory_object, [], role=TEST_ROLE, signal_wrapper=FakeSignalWrapper())
        case "grabber":
            return Grabber_FSM(shared_memory_object, [], role=TEST_ROLE, signal_wrapper=FakeSignalWrapper())
        case _:
            print(f"Unknown FSM '{name}', check FSM_TO_TEST / build_fsm()")
            return None

def main():
    """
    Main function
    """
    mode = build_fsm(FSM_TO_TEST)
    if mode is None:
        return

    print(f"TESTING: {mode.name}")

    if FAKE_INPUT and FSM_TO_TEST == "modem":
        # no modem hardware attached, fake it so start()/loop() never touch a real serial port
        mode.comms.open_modem = lambda *a, **kw: FakeModem(mode.comms, fake_data_frame=FAKE_MODEM_DATA_FRAME)

    if FAKE_INPUT and FSM_TO_TEST == "torpedo":
        # no camera/vision pipeline attached, fake the circle data so a hole can be found
        mode.lineup.get_torpedo_circle_data = lambda: FAKE_TORPEDO_CIRCLE_DATA

    if FAKE_INPUT and FSM_TO_TEST == "dropper":
        # no camera/vision pipeline attached, fake the detections so a bin can be found
        mode.helper.get_target_detections = lambda: FAKE_DROPPER_DETECTIONS[TEST_ROLE]

    if FAKE_INPUT and FSM_TO_TEST == "grabber":
        # no camera/vision pipeline attached, fake the detections so items/basket can be found
        mode.helper.get_target_detections = lambda: FAKE_GRABBER_DETECTIONS[TEST_ROLE]

    mode.start()
    main_loop(mode)

def main_loop(mode):
    """
    Looping function, runs the selected fsm until it completes
    """
    # modem state changes happen faster than a human can read at the normal
    # per-tick display cadence, and the per-tick DVL/TGT numbers are
    # meaningless for it anyway -- only print when the state actually changes.
    last_displayed_state = None

    while shared_memory_object.running.value:
        time.sleep(DELAY) # loop delay

        # fake input code, mimics sensors moving toward the FSM's targets ------------
        if FAKE_INPUT:
            drift_toward_targets(shared_memory_object)
        # ------------------------------------------------------------------------------

        mode.loop() # run fsm loop

        if FSM_TO_TEST == "modem":
            if mode.state != last_displayed_state:
                display(mode)
                last_displayed_state = mode.state
        else:
            display(mode)

        if mode.complete: # exit condition: fsm finished on its own
            print(f"{mode.name} finished (complete=True) in state {mode.state}, stopping test")
            mode.stop()
            stop()
            break

def display(mode):
    """
    Display function for testing
    """
    print(f"MODE: {mode.name}:{mode.state}")
    if hasattr(mode, "role"): # selected role, for dropper/grabber/modem
        print(f"ROLE: {mode.role}")
    if hasattr(mode, "received_frame"): # modem data/ack exchange result
        print(f"MODEM SUCCESS: {mode.success}  RECEIVED FRAME: {mode.received_frame}")
    if getattr(mode, "current_target", None) is not None: # last target detection/hole tracked
        target = mode.current_target
        if isinstance(target, dict): # torpedo's circle_data hole format
            print(f"TARGET: x_norm={target['x_norm']:.2f}  y_norm={target['y_norm']:.2f}")
        else: # dropper/grabber's vision target box format
            print(f"TARGET: label={target[0]}  x_norm={target[3]:.2f}  y_norm={target[4]:.2f}")

    helper = getattr(mode, "helper", None) # dropper/grabber downward-camera alignment debug info
    if helper is not None and hasattr(helper, "last_motion_cmd"):
        print("IMAGE ERROR: x=%.2f y=%.2f depth=%.2f" % (helper.last_x_error, helper.last_y_error, helper.last_depth_error))
        print("MOVE CMD: strafe=%.2f forward=%.2f vertical=%.2f" % helper.last_motion_cmd)
        print(f"STABLE: {helper.last_stable}  CENTERED: {helper.last_centered}  DWELL_OK: {helper.last_dwell_ok}  LOST: {helper.last_lost}")

    # %.3f instead of %.1f: torpedo/dropper/grabber alignment offsets are often
    # small (a few cm) and would otherwise round away to look unchanged
    print("x: %.3f -> %.3f" % (shared_memory_object.dvl_x.value, shared_memory_object.target_x.value))
    print("y: %.3f -> %.3f" % (shared_memory_object.dvl_y.value, shared_memory_object.target_y.value))
    print("z: %.3f -> %.3f" % (shared_memory_object.dvl_z.value, shared_memory_object.target_z.value))
    print("\n")

def stop():
    """
    Soft kill the robot
    """
    shared_memory_object.running.value = 0 # kill gracefully

def parse_args():
    """
    Optional CLI overrides for the modem settings, so the same file can be
    launched from two terminals (e.g. one per role) without editing it in
    between. Anything not passed falls back to the constants above.
    """
    parser = argparse.ArgumentParser(description="Single-FSM test controller")
    parser.add_argument("--role", choices=["sender", "listener"], default=None, help="override MODEM_ROLE")
    parser.add_argument("--port", default=None, help="override MODEM_PORT")
    parser.add_argument("--task-code", type=int, default=None, help="override MODEM_TASK_CODE")
    parser.add_argument("--color-flag", action="store_true", default=None, help="override MODEM_COLOR_FLAG to True")
    return parser.parse_args()

if __name__ == '__main__':
    args = parse_args()
    if args.role is not None:
        MODEM_ROLE = args.role
    if args.port is not None:
        MODEM_PORT = args.port
    if args.task_code is not None:
        MODEM_TASK_CODE = args.task_code
    if args.color_flag is not None:
        MODEM_COLOR_FLAG = args.color_flag

    print(f"RUNNING SINGLE FSM TEST: {FSM_TO_TEST}")
    try:
        main()
    except KeyboardInterrupt:
        print("keyboard interrupt detected, stopping program")
        shared_memory_object.running.value = 0
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
