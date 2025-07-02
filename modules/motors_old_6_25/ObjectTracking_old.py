from motors.MotorWrapper            import Can_Wrapper
from motors.MotorInterface          import MotorInterface
from multiprocessing                import Process, Value
import math
import time
import numpy as np

class Object_Tracking:

    def follow_object(self, color_offset, gate_offset, yolo_offset):
        


    def follow_buoy(self):   
        print(self.shared_memory_object.color_offset[0].value )
        #NO OBJECT
        if self.shared_memory_object.color_offset[0].value == 0 and self.shared_memory_object.imu_orientation[0].value < .1:
            self.iteration_since_last_detection += 1
            return
        #HARD DEADZONE
        #turn right if to the left of the hard deadzone
        elif(self.shared_memory_object.color_offset[0].value < -self.x_hard_deadzone):
            self.can.turn_right(abs(self.shared_memory_object.color_offset[0].value / self.normalizer_value * self.x_turn_speed / 3))
            self.iteration_since_last_detection = 0
        #turn left if to the right of the hard deadzone
        elif (self.shared_memory_object.color_offset[0].value > self.x_hard_deadzone):
            self.can.turn_left(abs(self.shared_memory_object.color_offset[0].value / self.normalizer_value * self.x_turn_speed / 3))
            self.iteration_since_last_detection = 0
        #SOFT DEADZONE
        #turn right and move forward if to the left of the soft deadzone
        elif (self.shared_memory_object.color_offset[0].value < -self.x_soft_deadzone):
            self.can.turn_right(abs(self.shared_memory_object.color_offset[0].value / self.normalizer_value * self.x_turn_speed))
            self.can.move_forward(self.speed)
            self.iteration_since_last_detection = 0
        #turn left and move forward if to the right of the soft deadzone
        elif (self.shared_memory_object.color_offset[0].value > self.x_soft_deadzone):
            self.can.turn_left(abs(self.shared_memory_object.color_offset[0].value / self.normalizer_value * self.x_turn_speed))
            self.can.move_forward(self.speed)
            self.iteration_since_last_detection = 0
        #CENTERED
        #move forward if inside soft deadzone    
        else: 
            self.can.move_forward(self.speed)
            self.iteration_since_last_detection = 0

    def follow_gate(self):   
        print("Offset x", self.shared_memory_object.gate_offset[0].value)
        #NO OBJECT 
        if self.shared_memory_object.gate_offset[0].value == 0 and self.shared_memory_object.imu_orientation[0].value < .1:
            self.iteration_since_last_detection += 1
            return
        #HARD DEADZONE
        #turn right if to the left of the hard deadzone
        elif(self.shared_memory_object.gate_offset[0].value < -self.x_hard_deadzone):
            self.can.turn_right(abs(self.shared_memory_object.gate_offset[0].value / self.normalizer_value * self.x_turn_speed))
            self.iteration_since_last_detection = 0
        #turn left if to the right of the hard deadzone
        elif (self.shared_memory_object.gate_offset[0].value > self.x_hard_deadzone):
            self.can.turn_left(abs(self.shared_memory_object.gate_offset[0].value / self.normalizer_value * self.x_turn_speed))
            self.iteration_since_last_detection = 0
        #SOFT DEADZONE
        #turn right and move forward if to the left of the soft deadzone
        elif (self.shared_memory_object.gate_offset[0].value < -self.x_soft_deadzone):
            self.can.turn_right(abs(self.shared_memory_object.gate_offset[0].value / self.normalizer_value * self.x_turn_speed))
            self.can.move_forward(self.speed)
            self.iteration_since_last_detection = 0
            self.iterations += 1
        #turn left and move forward if to the right of the soft deadzone
        elif (self.shared_memory_object.gate_offset[0].value > self.x_soft_deadzone):
            self.can.turn_left(abs(self.shared_memory_object.gate_offset[0].value / self.normalizer_value * self.x_turn_speed))
            self.can.move_forward(self.speed)
            self.iteration_since_last_detection = 0
            self.iterations += 1
        #CENTERED
        #move forward if inside soft deadzone    
        else: 
            self.can.move_forward(self.speed)
            self.iteration_since_last_detection = 0
            self.iterations += 1

    def follow_yolo(self):            
            #NO OBJECT ---
            if self.shared_memory_object.yolo_offset[0].value == 0.0 or self.shared_memory_object.distance_from_object.value > 10000:
                self.iteration_since_last_detection += 1
                return
            #HARD DEADZONE
            #turn right if to the left of the hard deadzone
            elif(self.shared_memory_object.yolo_offset[0].value < -self.x_hard_deadzone):
                self.can.turn_right(abs(self.shared_memory_object.yolo_offset[0].value / self.normalizer_value * self.x_turn_speed))
            #turn left if to the right of the hard deadzone
            elif (self.shared_memory_object.yolo_offset[0].value > self.x_hard_deadzone):
                self.can.turn_left(abs(self.shared_memory_object.yolo_offset[0].value / self.normalizer_value * self.x_turn_speed))
            #SOFT DEADZONE
            #turn right and move forward if to the left of the soft deadzone
            elif (self.shared_memory_object.yolo_offset[0].value < -self.x_soft_deadzone):
                self.can.turn_right(abs(self.shared_memory_object.yolo_offset[0].value / self.normalizer_value * self.x_turn_speed))
                self.can.move_forward(self.speed)
            #turn left and move forward if to the right of the soft deadzone
            elif (self.shared_memory_object.yolo_offset[0].value > self.x_soft_deadzone):
                self.can.turn_left(abs(self.shared_memory_object.yolo_offset[0].value / self.normalizer_value * self.x_turn_speed))
                self.can.move_forward(self.speed)
            #CENTERED
            #move forward if inside soft deadzone    
            else: 
                self.can.move_forward(self.speed)
            #STOP DEPTH
            self.iteration_since_last_detection = 0
            #stop if depth is less than stop value
            if (self.shared_memory_object.distance_from_object.value < self.distance_stop_value and self.shared_memory_object.distance_from_object.value != 0.0):
                print("stop")
                self.move_forward(1)
                self.shared_memory_object.enable_color.value = True
                self.shared_memory_object.enable_yolo.value = False
