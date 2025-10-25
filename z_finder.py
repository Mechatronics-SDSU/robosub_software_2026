class Z_Finder:

    def __init__(self, shared_memory_object):

        self.shared_memory_object = shared_memory_object

        #holds whether sv ran from dv
        self.in_dv                     = False

        #holds whether that sensor is in range on this measurement
        self.is_dvl_good               = True
        self.is_trax_good              = True
        self.is_other_good             = True

        #holds whether that sensor is in range on the prevous measurement
        self.was_dvl_good              = True
        self.was_trax_good             = True
        self.was_other_good            = True
        
        #holds whether that sensor is double verified 
        self.is_dvl_double_good        = True
        self.is_trax_double_good       = True
        self.is_other_double_good      = True

        #higher the value means that one is used more often
        #might be worth while to have these be read from the/a config file
        #IMOPRTANT THESE VALUES SHOULD NEVER BE EQUAL!!!!!!!!
        self.dvl_priority              = 3
        self.trax_priority             = 2
        self.other_priority            = 1

        #min and max depths
        #might be worth while to have these be read from the/a config file
        self.min_depth = 0.5
        self.max_depth = 4

    
    def validate_sensors(self):
        
        #saving whether prevous reading is in range
        self.was_dvl_good           = self.is_dvl_good
        self.was_other_good         = self.is_other_good
        self.was_trax_good          = self.is_trax_good

        #saving whether curent reading is in range
        self.is_dvl_good            = (self.shared_memory_object.dvl_z.value >= self.min_depth and self.shared_memory_object.dvl_z.value <= self.max_depth)
        self.is_other_good          = (self.shared_memory_object.other_depth_z.value >= self.min_depth and self.shared_memory_object.other_depth_z <= self.max_depth)
        self.is_trax_good           = (self.shared_memory_object.trax_depth_z.value >= self.min_depth and self.shared_memory_object.trax_depth_z.value <=self.max_depth)

        #the sensor is only double verified if both the current reading and the prevous reading are in range
        self.is_dvl_double_good     = self.was_dvl_good and self.is_dvl_good
        self.is_other_double_good   = self.was_other_good and self.is_other_good
        self.is_trax_double_good    = self.was_trax_good and self.is_trax_good

    def use_dvl(self):
        self.shared_memory_object.used_dvl.value = self.shared_memory_object.used_dvl.value + 1
        self.shared_memory_object.validated_z.value = self.shared_memory_object.dvl_z.value

    def use_trax(self):
        self.shared_memory_object.used_trax.value = self.shared_memory_object.used_trax.value + 1
        self.shared_memory_object.validated_z.value = self.shared_memory_object.trax_depth_z.value

    def use_other(self):
        self.shared_memory_object.used_other.value = self.shared_memory_object.used_other.value + 1
        self.shared_memory_object.validated_z.value = self.shared_memory_object.other_depth_z.value

    def find_median(self):
        if(self.shared_memory_object.dvl_z.value > self.shared_memory_object.other_depth_z.value):
            if(self.shared_memory_object.dvl_z.value < self.shared_memory_object.trax_depth_z.value)
                self.use_dvl()
            else:
                self.use_trax()
        else:
            if(self.shared_memory_object.other_depth_z.value < self.shared_memory_object.trax_depth_z.value):
                self.use_other()
             else:
                self.use_trax()

    #sends finds the most approate z with only checking the most recent sensor values
    def send_z_sv(self):
        
        #only validates sensors if not ran inside of send_Z_dv
        if(not self.in_dv):
            self.validate_sensors()
        
        #-10 is the value sent if there is  a critical error
        #only sends critcal error if all depth sensor are out of range
        if((not self.is_dvl_good) and (not self.is_other_good) and (not self.is_trax_good)):
            pass
        
        #sends trax if it is the only one in range
        elif((not self.is_dvl_good) and (not self.is_other_good)):
            self.use_trax()
        
        #sends dvl if it is the only one in range
        elif((not self.is_other_good) and (not self.is_trax_good)):
            self.use_dvl()
        
        #sends other if it is the only one in range 
        elif((not self.is_dvl_good) and (not self.is_trax_good)):
            self.use_other()
        
        #if both trax and other are in range
        elif(not self.is_dvl_good):
            
            #sends the the one with higher priortiy 
            if(self.trax_priority > self.other_priority):
                 self.use_trax()
            else:
                self.use_other()

        #if both dvl and trax are in range
        elif(not self.is_other_good):
            
            #sends the the one with higher priortiy
            if(self.trax_priority > self.dvl_priority):
                self.use_trax()
            else:
                self.use_dvl()
           
        #if both dvl and other are in range
        elif(not self.is_trax_good):
            if(self.other_priority > self.dvl_priority):
                self.use_other()
            else:
                self.use_dvl()

         #if they all are in range find and send median    
        else:
            self.find_median()

    #sends z based on the curent and prevous sensor mesurments
    def send_z_dv(self):

        self.validate_sensors()

        #if none sensors are double verified reily on single verifaction 
        if((not self.is_dvl_double_good) and (not self.is_other_double_good) and (not self.is_trax_double_good)):
            self.in_dv = True
            self.send_z_sv()
            self.in_dv = False
        
        #sends trax if trax is the only one double verifed
        elif((not self.is_dvl_double_good) and (not self.is_other_double_good)):
            self.use_trax()
        
        #sends dvl if dvl is the only one double verifed
        elif((not self.is_other_double_good) and (not self.is_trax_double_good)):
            self.use_dvl()
        
        #sends other if other is the only one double verifed
        elif((not self.is_dvl_double_good) and (not self.is_trax_double_good)):
            self.use_other()
        
        #if both trax and other are double verifed
        elif(not self.is_dvl_double_good):
            
            #sends the the one with higher priortiy
            if(self.trax_priority > self.other_priority):
                self.use_trax()
            else:
                self.use_other()
        
        #if both dvl and trax are double verifed
        elif(not self.is_other_double_good):
            
            #sends the the one with higher priortiy
            if(self.trax_priority > self.dvl_priority):
                self.use_trax()
            else:
                self.use_dvl()
        
        #if both dvl and other are double verifed
        elif(not self.is_trax_double_good):
            
           #sends the the one with higher priortiy
            if(self.other_priority > self.dvl_priority):
                self.use_other()
            else:
                self.use_dvl()
        
        #if they all are double verifed find and send the median
        else:
            self.find_median()