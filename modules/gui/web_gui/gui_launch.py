
import json
import time, os
import views # may or may not get angry at trying to import views idk

class Gui_launch:

    def __init__(self, shared_memory_object):
        self.shared_memory_object = shared_memory_object
        views.recieveMemory(shared_memory_object)
        self.FILE = os.environ.get(
                    "TELEMETRY_FILE",
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "telemetry.json")) #finds telemetry.json filepath
        )
        self.write_values()

    def write_values(self):
        while self.running.value:

            #Writes to JSON file
            telemetry = {
                "dvl": {
                    "x": self.dvl_x.value,
                    "y": self.dvl_y.value,
                    "z": self.dvl_z.value,
                    "yaw": self.dvl_yaw.value,
                    "pitch": self.dvl_pitch.value,
                    "roll": self.dvl_roll.value,
                    "vx": self.dvl_x_velocity.value,
                    "vy": self.dvl_y_velocity.value,
                    "vz": self.dvl_z_velocity.value,
                }
            }

            tmp = self.FILE + ".tmp"  #writes into a temp json file and replaces old file once done writing
            with open(tmp, "w") as f:
                json.dump(telemetry, f, indent=2)
            os.replace(tmp, self.FILE)
            time.sleep(1)
    
    def DVL_RESET(self):
        #might delete. moved this function to views.
        self.shared_memory_object.dvl_x.value = 0
        self.shared_memory_object.dvl_y.value = 0
        self.shared_memory_object.dvl_z.value = 0


        
