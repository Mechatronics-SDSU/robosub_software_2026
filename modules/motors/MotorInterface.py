from modules.motors.MotorWrapper            import MotorWrapper
from modules.motors.ObjectTracking          import Object_Tracking
import time

#from MotorWrapper import Can_Wrapper
"""
    discord: @kialli
    github: @kchan5071

    This module is responsible for interfacing the shared memory object with the hierarchical state machine.
    
"""

class MotorInterface:

    def __init__(self, shared_memory_object):
        self.shared_memory_object = shared_memory_object
        self.Object_Tracking = Object_Tracking()
        self.motor_wrapper = MotorWrapper()


        #----------------------Tune-----------------------------------
        self.y_turn_speed = 5

        # The maximum distance from gate after shooting to it to change from the gate task to the buoy task. 
        self.distance_stop_value = 1000

        #---------------------------timeout / detection parameters------------------------------
        # The number of iterations of the initial sitting at depth.
        self.intitial_iterations = 0
        # The number of iterations of following the gate.
        self.iterations_shooting_for_gate = 0
        # Max iterations of following the gate until switching to buoy
        self.max_iterations_shooting_for_gate = 200

        # Used for determining when to begin looking for the gate again.
        self.iteration_since_last_detection = 0
        # How many iterations without detection until starting to look for the gate again.
        self.iterations_before_detection_timeout = 100


        # Number of iterations of a turn when turning to look for the gate.
        self.detection_thrust_length = 10
        # Current iteration the turn.
        self.detection_thrust_count = 0

        # Number of iterations of waiting between turns when turning to look for the gate.
        self.wait_length = 10
        # Current iteration of the wait.
        self.current_wait = 0

    def look_for_detection(self):
        # Turn if not at max turn iterations.
        if self.detection_thrust_count <= self.detection_thrust_length:
            # TODO: Check if imu_ang_vel[0] is the correct attribute.
            if self.shared_memory_object.imu_ang_vel[0].value < self.y_turn_speed: # If turning too fast don't keep turning.
                self.motor_wrapper.turn_right(1)
            self.detection_thrust_count += 1
            return
        # Else wait for wait_length iterations.
        elif self.current_wait < self.wait_length:
            self.motor_wrapper.stop()
            self.current_wait += 1
            return
        # Switch to turning if at max wait iterations.
        else:
            self.current_wait = 0
            self.detection_thrust_count = 0

    def sit_at_depth(self):
        # print(self.shared_memory_object.depth.value)
        if self.shared_memory_object.depth.value < self.min_depth:
            self.motor_wrapper.move_down(.5)
        elif self.shared_memory_object.depth.value > self.max_depth:
            self.motor_wrapper.move_up(.4)
        pass

    def face_direction(self, target_direction):
        # TODO: Check if clockwise is negative and counter-clockwise is positive.
        #print(target - self.orientation_y.value)
        if self.shared_memory_object.imu_orientation[1].value - target_direction < -.001:
            # Turn proportional to how far away the sub is pointed from the target direction.
            self.motor_wrapper.turn_left(min(abs(target_direction - self.shared_memory_object.imu_orientation[1].value) * 3, 1))
            print("Correcting to the left")
        elif self.shared_memory_object.imu_orientation[1].value - target_direction > .001:
            # Turn proportional to how far away the sub is pointed from the target direction.
            self.motor_wrapper.turn_right(min(abs(target_direction - self.shared_memory_object.imu_orientation[1].value) * 3, 1))   
            print("Correcting to the right")  

    def correct_pitch(self):
        # print(self.shared_memory_object.imu_orientation[0].value)
        if self.shared_memory_object.imu_orientation[0].value < -.001:
            # Pitch proportional to how how far away from 0 the sub is pitched.
            self.motor_wrapper.turn_up(min(abs(self.shared_memory_object.imu_orientation[0].value) * 3, 1))
        elif self.shared_memory_object.imu_orientation[0].value > .001:
            # Pitch proportional to how how far away from 0 the sub is pitched.
            self.motor_wrapper.turn_down(min(self.shared_memory_object.imu_orientation[0].value * 3, 1))

    def correct_drift(self):
        # Don't correct drift if above the min depth.
        if self.shared_memory_object.depth.value > self.min_depth - .1:
            return
        # ---------------------------- Correct Yaw ---------------------------------
        if self.shared_memory_object.imu_orientation[1].value < -.1:
            # Turn proportional to how how far away from 0 the sub is turned.
            self.motor_wrapper.turn_left(self.shared_memory_object.imu_orientation[1].value / 2)
            print("turn left")
        elif self.shared_memory_object.imu_orientation[1].value > .1:
            # Turn proportional to how how far away from 0 the sub is turned.
            self.motor_wrapper.turn_right(self.shared_memory_object.imu_orientation[1].value / 2)
            print("turn right")
        # --------------------------- Correct Pitch --------------------------------
        if self.shared_memory_object.imu_orientation[0].value < -.1:
            # Pitch proportional to how how far away from 0 the sub is pitched.
            self.motor_wrapper.turn_up(self.shared_memory_object.imu_orientation[0].value / 2)
            print("turn up")
        elif self.shared_memory_object.imu_orientation[0].value > .1:
            # Pitch proportional to how how far away from 0 the sub is pitched.
            self.motor_wrapper.turn_down(self.shared_memory_object.imu_orientation[0].value / 2)
            print("turn down")
        # ---------------------------- Correct Roll ---------------------------------
        if self.shared_memory_object.imu_orientation[2].value < -.1:
            # Roll proportional to how how far away from 0 the sub is rolled.
            self.motor_wrapper.roll_left(self.shared_memory_object.imu_orientation[2].value / 2)
            print("roll left")
        elif self.shared_memory_object.imu_orientation[2].value > .1:
            # Roll proportional to how how far away from 0 the sub is rolled.
            self.motor_wrapper.roll_right(self.shared_memory_object.imu_orientation[2].value / 2)
            print("roll right")

    # Main function
    def run_loop(self):

        # Wait for imu to start
        while self.shared_memory_object.imu_lin_acc[0].value == 0.0: 
            pass

        while self.shared_memory_object.running.value:   
            # start = time.time()

            # if (self.iteration_since_last_detection > self.iterations_before_detection_timeout) and self.enable_yolo:
            #     self.look_for_detection()
            # else:
            #     self.current_wait = 0
            #     self.detection_thrust_count = 0

            # if self.shared_memory_object.gate_enable.value:
            #     print("Offset: ", self.shared_memory_object.color_offset[0])
            #     self.Object_Tracking.follow_object(
            #         offset_to_follow    = self.shared_memory_object.gate_offset.value,
            #         current_orientation = self.shared_memory_object.imu_orientation.value,
            #         current_distance    = self.shared_memory_object.distance_from_object.value
            #     )
            #     iterations_shooting_for_gate += 1
            # if self.shared_memory_object.enable_yolo.value:
            #     self.look_for_detection()
            #     self.Object_Tracking.follow_object(
            #         offset_to_follow    = self.shared_memory_object.yolo_offset.value,
            #         current_orientation = self.shared_memory_object.imu_orientation.value,
            #         current_distance    = self.shared_memory_object.distance_from_object.value
            #     )
                
            self.sit_at_depth()
            print("Sitting at depth")

            # If at max iterations shooting for the gate, switch to buoy task.
            if self.iterations_shooting_for_gate == self.max_iterations_shooting_for_gate:
                self.motor_wrapper.move_forward(1)
                self.shared_memory_object.gate_enable.value = False
                self.shared_memory_object.enable_yolo.value = True

            # Wait if the loop completes too quickly to avoid overloading can.
            end = time.time()
            if (.05 - (end - start)) > 0:
                time.sleep(.05 - (end - start))
            self.motor_wrapper.send_command()

# from modules.motors.hierarchical_state_machine   import HierarchicalStateMachine
# import time

# #from MotorWrapper import Can_Wrapper
# """
#     discord: @kialli
#     github: @kchan5071

#     This module is responsible for interfacing the shared memory object with the hierarchical state machine.
    
# """

# class MotorInterface:

#     def __init__(self, shared_memory_object):
#         self.shared_memory_object = shared_memory_object
#         self.heirarchical_state_machine = HierarchicalStateMachine()


#     def get_depth(self):
#         """
#         Get the depth from the shared memory object
#         """
#         return self.shared_memory_object.depth.value

#     #should start HFSM
#     def run_loop(self):
#         print("Hierarchical State Machine initialized.")
#         # Example usage

#         print("Current States:")
#         print(self.heirarchical_state_machine.states)

#         # Example of running the state machine
#         current_state = "Gate"  
#         while True:
#             next_state = self.heirarchical_state_machine.get_next_state(current_state, "on_complete")
#             if next_state:
#                 print(f"Transitioning from {current_state} to {next_state}")
#                 current_state = next_state
#             else:
#                 print(f"No transition found for state {current_state}")
            
#             # Simulate some processing time
#             time.sleep(1)





#         while self.shared_memory_object.running.value:   
#             pass