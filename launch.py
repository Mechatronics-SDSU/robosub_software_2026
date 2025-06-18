from multiprocessing                        import Process, Value
from shared_memory                          import SharedMemoryWrapper
from modules.motors.MotorInterface          import MotorInterface
from modules.pid.pid_interface              import PIDInterface
from modules.sensors.a50_dvl.dvl_interface  import DVL_Interface
from modules.vision.vision_main             import VideoRunner
from utils.kill_button_interface            import Kill_Button_Interface

"""
    discord: @kialli
    github: @kchan5071
    
    This is the main file that will be run to start the program.
    Combined the old launch.py with the launch.py.DVL_Test
    
"""
def main():
    # create shared memory
    shared_memory_object = SharedMemoryWrapper()
    # set deadzone
    temp_x_hard_deadzone = 400 #FIXME
    # set mode
    mode = "normal"

    if (mode == "normal"): 
        # create objects
        vis_object = VideoRunner(shared_memory_object, temp_x_hard_deadzone) #, shared_memory_object.x_hard_deadzone)
        interface = MotorInterface(shared_memory_object)
        kill_btn = Kill_Button_Interface(shared_memory_object)
        
        
        #create processes
        vis_process = Process(target=vis_object.run_loop)
        interface_process = Process(target=interface.run_loop)
        kill_btn_process = Process(target=kill_btn.run_loop)

        # start processes
        vis_process.start()
        interface_process.start()
        kill_btn_process.start()

        # wait for processes to finish
        vis_process.join()
        interface_process.join()
        kill_btn_process.join()

    elif(mode == "pid"):
        # create objects
        PID_interface = PIDInterface(shared_memory_object)
        dvl_object = DVL_Interface(shared_memory_object)        
        
        #create processes
        PID_process = Process(target=PID_interface.run_loop)
        dvl_process = Process(target=dvl_object.run_loop)

        # start processes
        PID_process.start()
        dvl_process.start()

        # wait for processes to finish
        PID_process.join()
        dvl_process.join()

    #END
    print("Program has finished")

if __name__ == '__main__':
    print("RUN FROM LAUNCH")
    main()