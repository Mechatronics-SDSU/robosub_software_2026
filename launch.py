import subprocess, time
from multiprocessing                        import Process, Value

# import FSMs
from shared_memory                          import SharedMemoryWrapper
from fsm.gate_fsm                           import Gate_FSM
from fsm.octagon_fsm                        import Octagon_FSM
from fsm.slalom_fsm                         import Slalom_FSM
from fsm.return_fsm                         import Return_FSM
from fsm.fsm                                import FSM_Template
from fsm.test_signals_fsm                   import TestSignals_FSM
from fsm.torpedo_fsm                        import Torpedo_FSM
from fsm.dropper_fsm                        import Dropper_FSM
from fsm.grabber_fsm                        import Grabber_FSM

#import modules
from modules.pid.pid_interface              import PIDInterface
from modules.sensors.a50_dvl.dvl_interface  import DVL_Interface
from modules.signals.SignalWrapper          import SignalWrapper
from modules.torpedo.torpedo_helpers         import TorpedoHelper
# NOTE: DropperHelpers/GrabberHelpers are constructed internally by
# Dropper_FSM/Grabber_FSM (they take shared_memory_object + signal_wrapper,
# not usb_object, and aren't run_list process objects), so they aren't
# imported/instantiated here.

#kill module
from modules.motors.USB_Transmit            import USB_Transmitter


"""
    discord: @.kech, @kialli∏
    github: @rsunderr, @kchan5071
    
    Runs mission control code and starts the sub
    
"""
# permissions fix
try:
    device_path = '/dev/ttyACM0'
    subprocess.run(["sudo", "chmod", "777", device_path], check=True)
    print(f"Permissions changed for {device_path}")
except subprocess.CalledProcessError as e:
    print(f"ERROR: Permissions fix failed (subprocess error): {e}")
except FileNotFoundError as e:
    print(f"ERROR: Permissions fix failed (command or device not found): {e}")
except PermissionError as e:
    print(f"ERROR: Permissions fix failed (permission denied): {e}")
except OSError as e:
    print(f"ERROR: Permissions fix failed (OS error): {e}")


# create shared memory object
shared_memory_object = SharedMemoryWrapper()
DELAY = 0 #s

# initialize objects
usb_object = USB_Transmitter()  # Create a single USB_Transmitter instance to be shared
pid_object = PIDInterface(shared_memory_object, usb_object)  # Pass the USB_Transmitter instance to PIDInterface
dvl_object = DVL_Interface(shared_memory_object)
sig_object = SignalWrapper(usb_object)
tor_object = TorpedoHelper(usb_object)

# initialize modes
gate_modules = [pid_object, dvl_object]
gate_mode   = Gate_FSM(shared_memory_object, gate_modules)

test_signals_modules = [sig_object, pid_object, dvl_object]
test_signals_mode = TestSignals_FSM(shared_memory_object, test_signals_modules)

slalom_mode = Slalom_FSM(shared_memory_object, [])
oct_mode    = Octagon_FSM(shared_memory_object, [])
return_mode = Return_FSM(shared_memory_object, [])

torpedo_mode = Torpedo_FSM(shared_memory_object, [tor_object, pid_object, dvl_object])
dropper_mode = Dropper_FSM(shared_memory_object, [pid_object, dvl_object], signal_wrapper=sig_object)
grabber_mode = Grabber_FSM(shared_memory_object, [pid_object, dvl_object], signal_wrapper=sig_object)

#mode_list = [gate_mode, slalom_mode, oct_mode, return_mode] # order of modes
mode_list = [test_signals_mode]

def main():
    """
    Main function - intializes mode and starts loop
    """    
    # make linked list of modes
    make_list(mode_list) #type: ignore
    
    # start initial mode
    mode = mode_list[0] # mode pointer
    mode.start()
    # loop
    main_loop(mode)

def main_loop(mode: FSM_Template | None) -> None:
    """
    Looping function, handles mode transitions
    """
    while shared_memory_object.running.value:
        time.sleep(DELAY) # loop delay
        
        if mode is not None:
            mode.loop() # run current mode loop
            if mode.complete:
                mode = mode.next()   # transition to next mode
        else: # exit loop if no mode
            stop()
            break

def stop():
    """
    Soft kill the robot
    """
    shared_memory_object.running.value = 0 # kill gracefully
    time.sleep(0.25)
    usb_object.soft_kill()

def make_list(modes: list[FSM_Template]) -> None:
    """
    Make a linked list of modes from a list of modes
    """
    for i in range(len(modes)-1):
        modes[i].next_mode = modes[i+1]
        
    modes[len(modes)-1].next_mode = None # end chain


if __name__ == '__main__':
    print("RUN FROM LAUNCH")
    try:
        main()
    except KeyboardInterrupt:
        print("keyboard interrupt detected, stopping program")
        shared_memory_object.running.value = 0 # kill gracefully
        time.sleep(0.25)
        usb_object.kill_motors()
        
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        
        