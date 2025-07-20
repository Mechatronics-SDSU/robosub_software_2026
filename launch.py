from multiprocessing                        import Process, Value
from shared_memory                          import SharedMemoryWrapper
from modules.motors.MotorInterface          import MotorInterface
from modules.pid.pid_interface              import PIDInterface
from modules.sensors.a50_dvl.dvl_interface  import DVL_Interface
from modules.sensors.trax2.trax_fxns        import TRAX
from modules.vision.vision_main             import VideoRunner
from modules.sensors.depth_sensor.depth_sensor_interface import DepthSensorInterface
from utils.kill_button_interface            import Kill_Button_Interface
import subprocess

device_path = '/dev/ttyACM0'

"""
    discord: @kialli
    github: @kchan5071
    
    This is the main file that will be run to start the program.
    Combined the old launch.py with the launch.py.DVL_Test
    
"""
def main():
    # try:
        # create shared memory
        shared_memory_object = SharedMemoryWrapper()
        # set deadzone
        temp_x_hard_deadzone = 400 #FIXME
        # set mode
        mode = "pid"

        if (mode == "normal"): 
            # create objects
            vis_object = VideoRunner(shared_memory_object, temp_x_hard_deadzone) #, shared_memory_object.x_hard_deadzone)
            interface = MotorInterface(shared_memory_object)
            kill_btn = Kill_Button_Interface(shared_memory_object)

            # trax_obj = TRAX(shared_memory_object)
            
            
            #create processes
            vis_process = Process(target=vis_object.run_loop)
            interface_process = Process(target=interface.run_loop)
            kill_btn_process = Process(target=kill_btn.run_loop)
            # trax_process = Process(target=trax_obj.run_loop)


            # start processes
            vis_process.start()
            interface_process.start()
            kill_btn_process.start()
            # trax_process.start()

            # wait for processes to finish
            vis_process.join()
            interface_process.join()
            kill_btn_process.join()
            # trax_process.join()

        elif(mode == "pid"):
            # create objects
            PID_interface = PIDInterface(shared_memory_object)
            dvl_object = DVL_Interface(shared_memory_object)  
            # depth_sensor = DepthSensorInterface(shared_memory_object)      
            
            #create processes
            PID_process = Process(target=PID_interface.run_loop)
            dvl_process = Process(target=dvl_object.run_loop)
            # depth_sensor_process = Process(target=depth_sensor.run_loop)

            # start processes
            PID_process.start()
            dvl_process.start()
            # depth_sensor_process.start()

            # wait for processes to finish
            PID_process.join()
            dvl_process.join()
            # depth_sensor_process.join()

    # except:
    #     #END
    #     print("Program has finished")


if __name__ == '__main__':
    print("RUN FROM LAUNCH")
    try:
        subprocess.run(["sudo", "chmod", "777", device_path], check=True)
        print(f"Permissions changed for {device_path}")
        main()
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        
