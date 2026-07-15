import os
import argparse, logging, subprocess, time

# suppress Qt platform plugin crash on headless Linux (no X display)
if not os.environ.get('DISPLAY'):
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

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
from fsm.dropper_fsm                        import Dropper_FSM
from fsm.dropper_test_fsm                   import DropperTest_FSM
from fsm.grabber_fsm                        import Grabber_FSM
from fsm.grabber_test_fsm                   import GrabberTest_FSM
from fsm.torpedo_fsm                        import Torpedo_FSM
from fsm.lineup_test_fsm                    import Lineup_Test_FSM
from fsm.vision_test_fsm                    import Vision_Test_FSM

from fsm_test_helpers                       import FakeModem, drift_toward_targets

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

    LINEUP TARGET LABEL / CONFIDENCE WITHOUT EDITING THE FILE:
        Set FSM_TO_TEST = "lineup" below, then override which class to look
        for and/or the confidence floor from the command line:

            python test_fsm_ctrl.py --target-label blood --conf-min 0.9

        Omit either flag to fall back to LINEUP_TARGET_LABEL/LINEUP_CONF_MIN below.
"""

# create shared memory object
shared_memory_object = SharedMemoryWrapper()
DELAY = 0.2 # loop delay, raise this to slow down/step through states

FAKE_INPUT = False # fake dvl movement + fake modem messages, turn off once testing on real hardware

# dropper test settings, used when FSM_TO_TEST == "dropper_test". Camera-only bench test:
# points the chosen camera at a bin, fires the dropper when a stable detection is seen.
# No motors are commanded. Ctrl+C to stop (it loops forever on no-detect).
DROPPER_TEST_CAMERA_SOURCE = "downfacing" # "downfacing" (sub cam), "webcam" (laptop/dev), or "zed"
DROPPER_TEST_TARGET_LABEL  = None         # None = use role from objects.yaml; or e.g. "fire" / "blood"
DROPPER_TEST_SHOW_VIDEO    = False        # True = live preview window (requires X display / monitor)
DROPPER_TEST_RECORD_VIDEO  = True         # True = save annotated MP4 to dropper_test_recordings/
DROPPER_TEST_CONF_MIN      = 0.50         # minimum detection confidence (0.0–1.0)
DROPPER_TEST_IMGSZ         = 640          # YOLO inference resolution — lower (e.g. 320) on weak compute
# NOTE: FAKE_INPUT only fakes DVL drift (drift_toward_targets), not vision. Testing
# "dropper" past SEARCH_FOR_BIN needs either the real downward camera + a bin image,
# or a manual monkeypatch of DropperHelpers.get_target_detections() at the call site.

FAKE_MODEM_DATA_FRAME = { # data frame the fake modem "receives" when testing the modem listener, set to None for no message
    "frame_number": 0, "frame_type": FRAME_TYPE_DATA, "color_flag": 0, "task_code": 2,
}

# -----------------------------------------------------------------------------------
# CHOOSE WHICH FSM TO TEST HERE
# -----------------------------------------------------------------------------------
FSM_TO_TEST = "vision_test" # gate, octagon, slalom, return, prequal, coinflip, modem, dropper, dropper_test, grabber, grabber_test, torpedo, lineup, vision_test

# modem hardware settings, used when FSM_TO_TEST == "modem" and FAKE_INPUT = False.
# Run this file once per sub with the opposite MODEM_ROLE and each sub's real COM port.
MODEM_ROLE       = "listener" # "sender" or "listener" -- give each of the two subs the opposite role
MODEM_PORT       = "COM_TEST" # e.g. "COM7" on Windows or "/dev/ttyUSB0" on Linux
MODEM_TASK_CODE  = 2          # 0-3, the task code to send (sender role) or expect (listener role, informational only)
MODEM_COLOR_FLAG = False

# lineup test settings, used when FSM_TO_TEST == "lineup". Bench-diagnostic: reads
# and prints the vision/alignment math for the chosen system, never drives the sub.
LINEUP_SYSTEM        = "dropper"  # "dropper" or "grabber" -- which tool offset to test with
LINEUP_TARGET_LABEL  = "fire"     # vision class label to search for, must match a trained class
LINEUP_CAMERA_SOURCE = "webcam"   # "downfacing" (sub's cam), "webcam" (laptop/dev), or "zed" (ZED/ZED X-series)
LINEUP_CONF_MIN      = 0.70       # minimum detection confidence to produce any output at all
LINEUP_SHOW_VIDEO    = True       # live preview window with YOLO boxes + fps (press q to close, doesn't stop the FSM)
LINEUP_IMGSZ         = 640        # YOLO inference resolution -- lower (e.g. 320) on weak/RAM-limited compute
LINEUP_CAMERA_ID     = None       # only used when LINEUP_CAMERA_SOURCE == "zed" -- selects among multiple/GMSL cameras

# vision test settings, used when FSM_TO_TEST == "vision_test". Feature-test/showcase:
# logs every qualifying detection's coords/box to vision.log, no alignment math, never drives the sub.
# Runs unattended (no live window) - records MP4 (+ SVO for zed) instead, review afterward.
VISION_TEST_CAMERA_SOURCE = "downfacing"     # "downfacing" (sub's cam), "webcam" (laptop/dev), or "zed" (e.g. ZED 2i)
VISION_TEST_TARGET_LABEL  = None         # None = log every detected class; or a specific label to filter to
VISION_TEST_CONF_MIN      = 0.70         # minimum detection confidence to log/display
VISION_TEST_IMGSZ         = 640          # YOLO inference resolution -- lower (e.g. 320) on weak/RAM-limited compute
VISION_TEST_CAMERA_ID     = None         # only used when VISION_TEST_CAMERA_SOURCE == "zed"
VISION_TEST_CAMERA_INDEX  = 2            # only used when VISION_TEST_CAMERA_SOURCE == "downfacing"/"webcam" -- V4L2
                                          # device index (e.g. /dev/videoN). Default 0 collides with the ZED (which
                                          # claims /dev/video0+/dev/video1) on boxes where it enumerates first --
                                          # run `v4l2-ctl --list-devices` to confirm which index is the real down cam
VISION_TEST_LOG_PERIOD    = 10.0         # seconds between running-summary log lines
VISION_TEST_TARGET_DEPTH  = 1.0          # meters, assumed target plane depth for the metric back-projection log line
VISION_TEST_RECORD_MP4    = True         # record annotated video.mp4 (no live window - review afterward)
VISION_TEST_RECORD_SVO    = False        # also record native ZED recording.svo -- only used when camera_source="zed"
VISION_TEST_OUTPUT_DIR    = "vision_recordings" # base dir, one timestamped subfolder per run
VISION_TEST_HEADLESS      = False         # True = no live window (unattended); False = also show a live preview
VISION_TEST_ZED_FALLBACK  = None         # only used when VISION_TEST_CAMERA_SOURCE == "zed" -- set to
                                          # "downfacing" or "webcam" to auto-fall-back if the ZED fails to open

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
        case "dropper":
            return Dropper_FSM(shared_memory_object, [])
        case "dropper_test":
            return DropperTest_FSM(shared_memory_object, [],
                                    camera_source=DROPPER_TEST_CAMERA_SOURCE,
                                    target_label=DROPPER_TEST_TARGET_LABEL,
                                    show_video=DROPPER_TEST_SHOW_VIDEO,
                                    record_video=DROPPER_TEST_RECORD_VIDEO,
                                    conf_min=DROPPER_TEST_CONF_MIN,
                                    imgsz=DROPPER_TEST_IMGSZ)
        case "grabber":
            return Grabber_FSM(shared_memory_object, [])
        case "grabber_test":
            return GrabberTest_FSM(shared_memory_object, [])
        case "torpedo":
            return Torpedo_FSM(shared_memory_object, [])
        case "lineup":
            return Lineup_Test_FSM(shared_memory_object, [], system=LINEUP_SYSTEM, target_label=LINEUP_TARGET_LABEL,
                                    camera_source=LINEUP_CAMERA_SOURCE, conf_min=LINEUP_CONF_MIN, show_video=LINEUP_SHOW_VIDEO,
                                    imgsz=LINEUP_IMGSZ, camera_id=LINEUP_CAMERA_ID)
        case "vision_test":
            return Vision_Test_FSM(shared_memory_object, [], camera_source=VISION_TEST_CAMERA_SOURCE,
                                    target_label=VISION_TEST_TARGET_LABEL, conf_min=VISION_TEST_CONF_MIN,
                                    imgsz=VISION_TEST_IMGSZ, camera_id=VISION_TEST_CAMERA_ID,
                                    camera_index=VISION_TEST_CAMERA_INDEX,
                                    log_period_s=VISION_TEST_LOG_PERIOD, target_depth=VISION_TEST_TARGET_DEPTH,
                                    record_mp4=VISION_TEST_RECORD_MP4, record_svo=VISION_TEST_RECORD_SVO,
                                    output_dir=VISION_TEST_OUTPUT_DIR, headless=VISION_TEST_HEADLESS,
                                    zed_fallback=VISION_TEST_ZED_FALLBACK)
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
    if hasattr(mode, "role"): # selected role, for modem
        print(f"ROLE: {mode.role}")
    if hasattr(mode, "received_frame"): # modem data/ack exchange result
        print(f"MODEM SUCCESS: {mode.success}  RECEIVED FRAME: {mode.received_frame}")
    if hasattr(mode, "helper") and hasattr(mode.helper, "debug"): # dropper/grabber/lineup alignment debug info
        print(f"{mode.name} DEBUG: {mode.helper.debug}")
    elif hasattr(mode, "debug"): # vision_test - no helper, debug lives directly on the FSM
        print(f"{mode.name} DEBUG: {mode.debug}")

    # %.3f instead of %.1f: small position offsets would otherwise round away to look unchanged
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
    parser.add_argument("--target-label", default=None, help="override LINEUP_TARGET_LABEL")
    parser.add_argument("--conf-min", type=float, default=None, help="override LINEUP_CONF_MIN")
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
    if args.target_label is not None:
        LINEUP_TARGET_LABEL = args.target_label
    if args.conf_min is not None:
        LINEUP_CONF_MIN = args.conf_min

    print(f"RUNNING SINGLE FSM TEST: {FSM_TO_TEST}")
    try:
        main()
    except KeyboardInterrupt:
        print("keyboard interrupt detected, stopping program")
        shared_memory_object.running.value = 0
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")