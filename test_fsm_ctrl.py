import subprocess, time

# import FSMs to test
from shared_memory                          import SharedMemoryWrapper
from fsm.gate_fsm                           import Gate_FSM
from fsm.octagon_fsm                        import Octagon_FSM
from fsm.slalom_fsm                         import Slalom_FSM
from fsm.return_fsm                         import Return_FSM
from fsm.prequal_fsm                        import Prequal_FSM
from fsm.coinflip_fsm                       import CoinFlip_FSM
from fsm.modem_fsm                          import Modem_FSM

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
"""

# create shared memory object
shared_memory_object = SharedMemoryWrapper()
DELAY = 0.2 # loop delay, raise this to slow down/step through states

FAKE_INPUT = True # fake dvl movement + fake modem messages, turn off once testing on real hardware
FAKE_MODEM_CODE = 7 # code the fake modem "receives" when testing the modem listener, set to None for no message

# -----------------------------------------------------------------------------------
# CHOOSE WHICH FSM TO TEST HERE
# -----------------------------------------------------------------------------------
FSM_TO_TEST = "modem" # gate, octagon, slalom, return, prequal, coinflip, modem

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
            # role/port/message are hardware settings, edit as needed for a real run
            return Modem_FSM(shared_memory_object, [], role="listener", port="COM_TEST", message=5)
        # PLACEHOLDER: no fsm/torpedo_fsm.py exists yet.
        # once a Torpedo_FSM(FSM_Template) class exists (same shape as Gate_FSM),
        # import it above and uncomment the case below
        # case "torpedo":
        #     return Torpedo_FSM(shared_memory_object, [])
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
        mode.comms.open_modem = lambda *a, **kw: FakeModem(mode.comms, fake_code=FAKE_MODEM_CODE)

    mode.start()
    main_loop(mode)

def main_loop(mode):
    """
    Looping function, runs the selected fsm until it completes
    """
    while shared_memory_object.running.value:
        time.sleep(DELAY) # loop delay

        # fake input code, mimics sensors moving toward the FSM's targets ------------
        if FAKE_INPUT:
            drift_toward_targets(shared_memory_object)
        # ------------------------------------------------------------------------------

        mode.loop() # run fsm loop
        display(mode)

        if mode.complete: # exit condition: fsm finished on its own
            print(f"{mode.name} finished (complete=True), stopping test")
            mode.stop()
            stop()
            break

def display(mode):
    """
    Display function for testing
    """
    print(f"MODE: {mode.name}:{mode.state}")
    print("x: %.1f -> %.1f" % (shared_memory_object.dvl_x.value, shared_memory_object.target_x.value))
    print("y: %.1f -> %.1f" % (shared_memory_object.dvl_y.value, shared_memory_object.target_y.value))
    print("z: %.1f -> %.1f" % (shared_memory_object.dvl_z.value, shared_memory_object.target_z.value))
    print("\n")

def stop():
    """
    Soft kill the robot
    """
    shared_memory_object.running.value = 0 # kill gracefully

if __name__ == '__main__':
    print(f"RUNNING SINGLE FSM TEST: {FSM_TO_TEST}")
    try:
        main()
    except KeyboardInterrupt:
        print("keyboard interrupt detected, stopping program")
        shared_memory_object.running.value = 0
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
