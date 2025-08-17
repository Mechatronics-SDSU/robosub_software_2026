from multiprocessing                        import Process, Value
from shared_memory                          import SharedMemoryWrapper
from tricks_fsm                             import Tricks_FSM
import subprocess, os

#import modules
from modules.pid.pid_interface                                      import PIDInterface
from modules.sensors.depth_sensor.depth_sensor_interface            import DepthSensorInterface
from modules.vision.vision_main                                     import VisionDetection
from modules.motors.MotorWrapper                                    import MotorWrapper
# from modules.position_estimator.estimator_interface                 import PositionEstimatorInterface
from utils.kill_button_interface                                    import Kill_Button_Interface
from socket_send                                                    import set_screen

"""
    discord: @.kech
    github: @rsunderr
    
    Runs mission control code and starts the sub
    
"""
# permissions fix
try:
    # device_path = '/dev/ttyACM0'
    subprocess.run(["sudo", "chmod", "777", device_path], check=True)
    print(f"Permissions changed for {device_path}")
except: pass
# create shared memory object
shared_memory_object = SharedMemoryWrapper()

# initialize objects
pid_object = PIDInterface(shared_memory_object)
vis_object = VisionDetection(shared_memory_object)
depth_object = DepthSensorInterface(shared_mesmory_object)
kill_button_object = Kill_Button_Interface(shared_memory_object)
#motor_object = MotorWrapper(shared_memory_object)
#imu_estimator_object = PositionEstimatorInterface(shared_memory_object)

# initialize modes
tricks_modules = [pid_object, vis_object, depth_object, kill_button_object]
tricks_mode = Tricks_FSM(shared_memory_object, tricks_modules, True)


def main():
    """
    Main function
    """
    os.system("cansend can0 00A#") # all clear
    tricks_mode.start()

    while shared_memory_object.running.value:
        tricks_mode.loop()
        if tricks_mode.complete: stop()

def stop():
    """
    Soft kill the robot
    """
    shared_memory_object.running.value = 0 # kill gracefully
    os.system("cansend can0 000#") # motor kill

if __name__ == '__main__':
    print("RUN FROM LAUNCH")
    try:
        main()
    except KeyboardInterrupt:
        print("Keyboard interrupt detected")
        stop()
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        
