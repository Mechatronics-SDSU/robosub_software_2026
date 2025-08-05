from multiprocessing                        import Process, Value
from shared_memory                          import SharedMemoryWrapper
from modules.motors.MotorInterface          import MotorInterface
# from modules.pid.pid_interface              import PIDInterface
from modules.sensors.a50_dvl.dvl_interface  import DVL_Interface
from modules.sensors.trax2.trax_fxns        import TRAX
from modules.vision.vision_main             import VideoRunner
from modules.sensors.depth_sensor.depth_sensor_interface import DepthSensorInterface
from utils.kill_button_interface            import Kill_Button_Interface
import subprocess
from missionctrl                            import MissionControl

device_path = '/dev/ttyACM0'

"""
    discord: @kialli
    github: @kchan5071
    
    This is the main file that will be run to start the program.
    Combined the old launch.py with the launch.py.DVL_Test
    
"""
def main():
    msn_ctrl = MissionControl()
    msn_ctrl.loop()

if __name__ == '__main__':
    print("RUN FROM LAUNCH")
    try:
        subprocess.run(["sudo", "chmod", "777", device_path], check=True)
        print(f"Permissions changed for {device_path}")
        main()
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        
