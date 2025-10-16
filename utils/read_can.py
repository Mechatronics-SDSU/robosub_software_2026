import can
import time
from subprocess         import run, call
from multiprocessing    import Process, Value
import os 

"""
    discord: @kialli
    github: @kchan5071

    Waits for start button to run code

"""

LIGHT_ENABLE_COMMAND = bytearray([0x04, 0x00, 0x00, 0x00, 0x01])
LIGHT_ON_COMMAND     = bytearray([0x04, 0x00, 0x04, 0x00, 0x32])
LIGHT_OFF_COMMAND    = bytearray([0x04, 0x00, 0x04, 0x00, 0x00])
WRITE_CAN_ID = 34

LIGHT_ON_LENGTH  = 5

filters = [{"can_id": 0x007, "can_mask": 0x7FF}]
bus = can.Bus(interface='socketcan',channel = 'can0', receive_own_messages=True, can_filters = filters)

while True:
    message = bus.recv()

    if message == None:
        continue
    data = message.data
    if data[0] == None:
        continue

    if message.arbitration_id == 0x007: # if start button pressed
        if data[0] == 4:
            print("STARTING", data[0])
            os.system("pkill -f zed")
            os.system("pkill -f depth")

            message = can.Message(arbitration_id = 10, is_extended_id = False, data = None)
            bus.send(message)
            launch_process = Process(target=launch)

            message = can.Message(arbitration_id = WRITE_CAN_ID, is_extended_id = False, data = LIGHT_ENABLE_COMMAND)
            bus.send(message)

            message = can.Message(arbitration_id = WRITE_CAN_ID, is_extended_id = False, data = LIGHT_ON_COMMAND)
            bus.send(message)

            time.sleep(LIGHT_ON_LENGTH)

            message = can.Message(arbitration_id = WRITE_CAN_ID, is_extended_id = False, data = LIGHT_OFF_COMMAND)
            bus.send(message)

            # start launch process
            launch_process.start()
            launch_process.join()

        elif data[0] == 0: # if stop button is NOT pressed
            print("STOPPED, READY")
        else:
            print("it didnt work bitch") #thanks sam
    time.sleep(.1)
