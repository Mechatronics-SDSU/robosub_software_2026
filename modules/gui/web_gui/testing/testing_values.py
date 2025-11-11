
import json
import random
import time, os
from test_memory_wrapper import SharedMemoryWrapper
#import views


#File for creating fake testing values for telemetry

FILE = os.environ.get(
    "TEST_FILE",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../", "testVals.json")) #finds testVals.json filepath
)

def main():
    sm = SharedMemoryWrapper()

    #views.recieveMemory(sm)
    #delete if not testing

    while sm.running.value:
            sm.dvl_yaw.value = random.uniform(-180, 180)
            sm.dvl_pitch.value = random.uniform(-90, 90)
            sm.dvl_roll.value = random.uniform(-180, 180)
            sm.dvl_x_velocity.value = random.uniform(-2, 2)
            sm.dvl_y_velocity.value = random.uniform(-2, 2)
            sm.dvl_z_velocity.value = random.uniform(-2, 2)
            sm.dvl_x.value = random.uniform(-2, 2)
            sm.dvl_y.value = random.uniform(-2, 2)
            sm.dvl_z.value = random.uniform(-2, 2)

            #Writes to JSON file
            telemetry = {
                "dvl": {
                "yaw": sm.dvl_yaw.value,
                "pitch": sm.dvl_pitch.value,
                "roll": sm.dvl_roll.value,
                "vx": sm.dvl_x_velocity.value,
                "vy": sm.dvl_y_velocity.value,
                "vz": sm.dvl_z_velocity.value,
                "x": sm.dvl_x.value,
                "y": sm.dvl_y.value,
                "z": sm.dvl_z.value
               }
            }   

            tmp = FILE + ".tmp"  #writes into a temp json file and replaces old file once done writing
            with open(tmp, "w") as f:
                json.dump(telemetry, f, indent=2)
            os.replace(tmp, FILE)
            time.sleep(1)

if __name__ == "__main__":
    main()
