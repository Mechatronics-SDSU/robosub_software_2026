from multiprocessing                        import Process, Value
from shared_memory                          import SharedMemoryWrapper
from imu_fsm                                import IMU_FSM
from forward_spin_fsm                       import ForwardSpinFSM
import subprocess
import time
import os

#import modules
from modules.pid.pid_interface                                      import PIDInterface
from modules.sensors.depth_sensor.depth_sensor_interface            import DepthSensorInterface
from modules.vision.vision_main                                     import VisionDetection
# from modules.position_estimator.estimator_interface                 import PositionEstimatorInterface
from utils.kill_button_interface                                    import Kill_Button_Interface
from socket_send                                                    import set_screen

"""
    discord: @kialli, @.kech
    github: @kchan5071, @rsunderr
    
    Runs mission control code and starts the sub
    
"""
device_path = '/dev/ttyACM0'
# create shared memory object
shared_memory_object = SharedMemoryWrapper()
mode = "IMU"
delay = 0.001

# initialize objects
pid_object = PIDInterface(shared_memory_object)
vis_object = VisionDetection(shared_memory_object)
depth_object = DepthSensorInterface(shared_memory_object)
kill_button_object = Kill_Button_Interface(shared_memory_object)
# imu_estimator_object = PositionEstimatorInterface(shared_memory_object)


# initialize modes

imu_modules = [pid_object, vis_object, depth_object, kill_button_object]
forward_spin_modules = [pid_object, vis_object, depth_object, kill_button_object]
test_modules = [depth_object]

imu_mode    = IMU_FSM(shared_memory_object, imu_modules, True)
forward_spin_mode = ForwardSpinFSM(shared_memory_object, forward_spin_modules, False)

def main():
    """
    Main function
    """
    imu_mode.start()

    loop() # loop

    # join processes
    imu_mode.join()
    forward_spin_mode.join()
    time.sleep(5)

def loop():
    """
    Looping function, mostly mode transitions within conditionals
    """
    mode = "IMU"
    while shared_memory_object.running.value:
        #time.sleep(delay)

        imu_mode.loop()
        forward_spin_mode.loop()


        # TRANSITIONS-----------------------------------------------------------------------------------------------------------------------
        match(mode):
            case "IMU":
                if imu_mode.complete:
                    print("IMU IS DONE")
                    mode = "FDSP"
                    forward_spin_mode.start()
            case "FDSP":
                if forward_spin_mode.complete:
                    stop() # turn off robot


def stop():
    """
    Soft kill the robot
    """
    shared_memory_object.running.value = 0 # kill gracefully
    os.system("cansend can0 000#")

if __name__ == '__main__':
    print("RUN FROM LAUNCH")
    try:
        subprocess.run(["sudo", "chmod", "777", device_path], check=True)
        print(f"Permissions changed for {device_path}")
        main()
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        
