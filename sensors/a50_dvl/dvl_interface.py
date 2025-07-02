from a50_dvl.dvl import DVL

class DVL_Interface:

    """
    discord: @kialli
    github: @kchan5071

    This class is used to interface with the DVL sensor. 
    It is used to get the data from the DVL sensor and update the position and orientation of the AUV.

    it takes data from the dvl class and updates the shared memory values of the AUV

    this class acts as a bridge, should be unproblematic(hopefully)
    """

    def __init__(self, x, y, z, pitch, roll, yaw):
        self.x = x
        self.y = y
        self.z = z
        self.pitch = pitch
        self.roll = roll
        self.yaw = yaw
        self.dvl = DVL()

    def update(self):
        dvl_data = self.dvl.recieveData()
        if dvl_data != None:
            self.yaw = dvl_data[0]
            self.pitch = dvl_data[1]
            self.roll = dvl_data[2]
            self.x = dvl_data[3]
            self.y = dvl_data[4]
            self.z = dvl_data[5]

    def run_loop(self):
        self.update()

