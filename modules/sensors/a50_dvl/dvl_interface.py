from modules.logger.logger          import Logger
from modules.sensors.a50_dvl.dvl    import DVL

class DVL_Interface:

    """
    discord: @kialli
    github: @kchan5071

    This class is used to interface with the DVL sensor. 
    It is used to get the data from the DVL sensor and update the position and orientation of the AUV.

    it takes data from the dvl class and updates the shared memory values of the AUV

    this class acts as a bridge, should be unproblematic(hopefully)
    """

    P_DEBUG = True # FIXME

    def __init__(self, shared_memory_object):
        self.shared_memory_object = shared_memory_object
        self.dvl = DVL()
        self.logger = Logger()

    def update(self) -> None:
        try:
            message_type, dvl_data = self.dvl.recieveData()
            if dvl_data != None and message_type == "dead_reckoning":
                self.shared_memory_object.dvl_yaw.value = dvl_data[0]
                self.shared_memory_object.dvl_pitch.value = dvl_data[1]
                self.shared_memory_object.dvl_roll.value = dvl_data[2]
                self.shared_memory_object.dvl_x.value = -dvl_data[3]
                self.shared_memory_object.dvl_y.value = dvl_data[4]
                self.shared_memory_object.dvl_z.value = dvl_data[5]
            elif dvl_data != None and message_type == "velocity":
                self.shared_memory_object.dvl_x_velocity.value = dvl_data[0]
                self.shared_memory_object.dvl_y_velocity.value = dvl_data[1]
                self.shared_memory_object.dvl_z_velocity.value = dvl_data[2]
                self.shared_memory_object.dvl_altitude.value = dvl_data[3]
                self.shared_memory_object.dvl_velocity_valid.value = dvl_data[4]
                self.shared_memory_object.dvl_status.value = dvl_data[5]

            if self.P_DEBUG:
                self.logger.info(f"dvl_yaw: {self.shared_memory_object.dvl_yaw.value}")
                self.logger.info(f"dvl_pitch: {self.shared_memory_object.dvl_pitch.value}")
                self.logger.info(f"dvl_roll: {self.shared_memory_object.dvl_roll.value}")
                self.logger.info(f"dvl_x: {self.shared_memory_object.dvl_x.value}")
                self.logger.info(f"dvl_y: {self.shared_memory_object.dvl_y.value}")
                self.logger.info(f"dvl_z: {self.shared_memory_object.dvl_z.value}")
                self.logger.info(f"dvl_x_velocity: {self.shared_memory_object.dvl_x_velocity.value}")
                self.logger.info(f"dvl_y_velocity: {self.shared_memory_object.dvl_y_velocity.value}")
                self.logger.info(f"dvl_z_velocity: {self.shared_memory_object.dvl_z_velocity.value}")
                self.logger.info(f"dvl_altitude: {self.shared_memory_object.dvl_altitude.value}")
                self.logger.info(f"dvl_velocity_valid: {self.shared_memory_object.dvl_velocity_valid.value}")
                self.logger.info(f"dvl_status: {self.shared_memory_object.dvl_status.value}")
        except:
            self.logger.error("NO DVL DATA")

    def run_loop(self):
        self.update()
        while self.shared_memory_object.running.value:
            self.update()
            

