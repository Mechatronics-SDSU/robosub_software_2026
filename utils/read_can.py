import can
import time
from subprocess import run, call
from multiprocessing import Process, Value
import os 

"""
    discord: @kialli
    github: @kchan5071

    Waits for start button to run code

"""

filters = [{"can_id": 0x007, "can_mask": 0x7FF}]
bus = can.Bus(interface='socketcan',channel = 'can0', receive_own_messages=True, can_filters = filters)

#launch_arbitration_ID =  0x007

        #if msg.arbitration_id == launch_arbitration_ID:
while True:
    time.sleep(.1)
    message = bus.recv()
    if message == None:
        continue
    data = message.data
    if data[0] == None:
        continue
    if message.arbitration_id == 0x007:
        if data[0] == 4:
            print("STARTING", data[0])
            os.system("pkill -f zed")
            os.system("pkill -f depth")
            #pkill -f depth
            #pkill -f zed
            message = can.Message(arbitration_id = 10, is_extended_id = False, data = None)
            bus.send(message)
            launch_process = Process(target=launch)
            light_enable = bytearray([0x04, 0x00, 0x00, 0x00, 0x01])
            message = can.Message(arbitration_id = 34, is_extended_id = False, data = light_enable)
            bus.send(message)
            light_on = bytearray([0x04, 0x00, 0x04, 0x00, 0x32])
            message = can.Message(arbitration_id = 34, is_extended_id = False, data = light_on)
            bus.send(message)
            time.sleep(10)
            light_off = bytearray([0x04, 0x00, 0x04, 0x00, 0x00])
            message = can.Message(arbitration_id = 34, is_extended_id = False, data = light_off)
            bus.send(message)
            launch_process.start()
            launch_process.join()
        elif data[0] == 0:
            try:
                print("READY")
            except:
                pass
        else:
            print("it didnt work bitch")
    # filter.filter
    #arbitration ID ytes()
    #filter out any command thats not 007
