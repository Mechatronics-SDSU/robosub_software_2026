import json, time, os, threading
from .  import views

"""
    discord: @314_piekitty
    github: @malaikajoiner
    
    Object created from start.py that attaches the shared memory to the rest of the GUI files.
    This object will be constantly updating a JSON file with the shared memory values.
    
"""

class Gui_launch:

    def __init__(self, shared_memory_object):
        self.shared_memory_object = shared_memory_object
        views.recieveMemory(self.shared_memory_object)

        self.FILE = os.environ.get(
                    "TELEMETRY_FILE",
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "telemetry.json")) #finds telemetry.json filepath
        )
        
        self.thread = threading.Thread(
            target=self.write_shared_memory,
            daemon=True
        )
        self.thread.start()

    def get_value(self, value):
        return value.value if hasattr(value, "value") else value

    def write_shared_memory(self):
        while True:
            #Writes to JSON file
            telemetry = {
                "dvl": {
                    "x": self.shared_memory_object.dvl_x.value,
                    "y": self.shared_memory_object.dvl_y.value,
                    "z": self.shared_memory_object.dvl_z.value,
                    "yaw": self.shared_memory_object.dvl_yaw.value,
                    "pitch": self.shared_memory_object.dvl_pitch.value,
                    "roll": self.shared_memory_object.dvl_roll.value,
                    "vx": self.shared_memory_object.dvl_x_velocity.value,
                    "vy": self.shared_memory_object.dvl_y_velocity.value,
                    "vz": self.shared_memory_object.dvl_z_velocity.value
                    },
                "motors": {
                         "motor0": self.shared_memory_object.motor_values[0],
                         "motor1": self.shared_memory_object.motor_values[1],
                         "motor2": self.shared_memory_object.motor_values[2],
                         "motor3": self.shared_memory_object.motor_values[3],
                         "motor4": self.shared_memory_object.motor_values[4],
                         "motor5": self.shared_memory_object.motor_values[5],
                         "motor6": self.shared_memory_object.motor_values[6],
                         "motor7": self.shared_memory_object.motor_values[7]
                }
            }

            tmp = self.FILE + ".tmp"  #writes into a temp json file and replaces old file once done writing
            with open(tmp, "w") as f:
                json.dump(telemetry, f, indent=2)
            os.replace(tmp, self.FILE)
            time.sleep(1)
   

    