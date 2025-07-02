class Object_Tracking:

    def __init__(self):
        self.iterations = 0
        self.iteration_since_last_detection = 0
        #--------------------Deadzones--------------------------------
        # Unit: number of pixels from the center of an image.
        # When looking for the gate, if the center of the gate is outside of this value, turn towards gate only.
        self.x_hard_deadzone = 400
        # When looking for the gate, if the center of the gate is outside of this value,
        # but inside the hard_deadzone value, turn towards gate and move forward.
        # If inside of this value, move foward only.
        self.x_soft_deadzone = 200

    def follow_object(self, offset_to_follow, current_orientation, current_distance):

        #-------------------------------------- NO OBJECT -------------------------------------------------
        if offset_to_follow == 0 and current_orientation < .1 or current_distance > 1000:
            self.iteration_since_last_detection += 1
            return
        
        #------------------------------------- HARD DEADZONE ---------------------------------------------
        # Turn right if to the left of the hard deadzone
        elif(offset_to_follow < -self.x_hard_deadzone):
            # Turn proportional to how far away the center of the buoy is from the center of the image.
            self.can.turn_right(abs(offset_to_follow / self.normalizer_value * self.x_turn_speed))
        #turn left if to the right of the hard deadzone
        elif (offset_to_follow > self.x_hard_deadzone):
            # Turn proportional to how far away the center of the buoy is from the center of the image.
            self.can.turn_left(abs(offset_to_follow / self.normalizer_value * self.x_turn_speed))
        
        #--------------------------------- SOFT DEADZONE ----------------------------------------------
        # Turn right and move forward if to the left of the soft deadzone
        elif (offset_to_follow < -self.x_soft_deadzone):
            # Turn proportional to how far away the center of the buoy is from the center of the image.
            self.can.turn_right(abs(offset_to_follow / self.normalizer_value * self.x_turn_speed))
            self.can.move_forward(self.speed)
        # Turn left and move forward if to the right of the soft deadzone
        elif (offset_to_follow > self.x_soft_deadzone):
            # Turn proportional to how far away the center of the buoy is from the center of the image.
            self.can.turn_left(abs(offset_to_follow / self.normalizer_value * self.x_turn_speed))
            self.can.move_forward(self.speed)

        #------------------------------------ CENTERED ---------------------------------------------------
        else: 
            self.can.move_forward(self.speed)
            if ( offset_to_follow == self.shared_memory_object.gate_offset[0]):
                self.iterations += 1

        self.iteration_since_last_detection = 0
