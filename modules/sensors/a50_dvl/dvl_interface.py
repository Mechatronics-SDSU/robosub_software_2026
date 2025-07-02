from sensors.a50_dvl.dvl import DVL

class DVL_Interface:

    """
    discord: @kialli
    github: @kchan5071

    This class is used to interface with the DVL sensor. 
    It is used to get the data from the DVL sensor and update the position and orientation of the AUV.

    it takes data from the dvl class and updates the shared memory values of the AUV

    this class acts as a bridge, should be unproblematic(hopefully)
    """

    def __init__(self, shared_memory_object):
        self.shared_memory_object = shared_memory_object
        self.dvl = DVL()

    def update(self):
        message_type, dvl_data = self.dvl.recieveData()
        if dvl_data != None and message_type == "dead_reckoning":
            self.shared_memory_object.dvl_yaw.value = dvl_data[0]
            self.shared_memory_object.dvl_pitch.value = dvl_data[1]
            self.shared_memory_object.dvl_roll.value = dvl_data[2]
            self.shared_memory_object.dvl_x.value = dvl_data[3]
            self.shared_memory_object.dvl_y.value = dvl_data[4]
            self.shared_memory_object.dvl_z.value = dvl_data[5]
            print("dvl_yaw:", self.shared_memory_object.dvl_yaw.value)
            print("dvl_pitch:", self.shared_memory_object.dvl_pitch.value)
            print("dvl_roll:", self.shared_memory_object.dvl_roll.value)
            print("dvl_x:", self.shared_memory_object.dvl_x.value)
            print("dvl_y:", self.shared_memory_object.dvl_y.value)
            print("dvl_z:", self.shared_memory_object.dvl_z.value)
        elif dvl_data != None and message_type == "velocity":
            self.shared_memory_object.dvl_x_velocity.value = dvl_data[0]
            self.shared_memory_object.dvl_y_velocity.value = dvl_data[1]
            self.shared_memory_object.dvl_z_velocity.value = dvl_data[2]
            self.shared_memory_object.dvl_altitude.value = dvl_data[3]
            self.shared_memory_object.dvl_velocity_valid.value = dvl_data[4]
            self.shared_memory_object.dvl_status.value = dvl_data[5]
            print("dvl_x_velocity:", self.shared_memory_object.dvl_x_velocity.value)
            print("dvl_y_velocity:", self.shared_memory_object.dvl_y_velocity.value)
            print("dvl_z_velocity:", self.shared_memory_object.dvl_z_velocity.value)
            print("dvl_altitude:", self.shared_memory_object.dvl_altitude.value)
            print("dvl_velocity_valid:", self.shared_memory_object.dvl_velocity_valid.value)
            print("dvl_status:", self.shared_memory_object.dvl_status.value)

    def run_loop(self):
        self.update()
        while self.shared_memory_object.running.value:
            self.update()
            

