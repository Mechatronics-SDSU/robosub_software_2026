import pyzed.sl as sl
import socket
import cv2
from modules.sensors.depth_sensor import DepthSensor

"""
    discord: @kialli
    github: @kchan5071

    zed implementation, sensor testing

"""

def test_depth_sensor():
    print("DEPTH SENSOR")
    depth_sensor = DepthSensor()
    depth = depth_sensor.recieve_data()
    if depth is None:
        return False
    return True

def test_zed_camera():
    print("ZED CAM")
    zed = sl.Camera()
    init_params = sl.InitParameters()
    init_params.camera_resolution = sl.RESOLUTION.HD720
    init_params.camera_fps = 60
    init_params.coordinate_system = sl.COORDINATE_SYSTEM.RIGHT_HANDED_Y_UP
    init_params.depth_mode = sl.DEPTH_MODE.NEURAL
    state = zed.open(init_params)
    if state != sl.ERROR_CODE.SUCCESS:
        return False
    return True

def test_DVL():
    print("DVL")
    try:
        serv_addr = ('192.168.194.95' , 16171)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(serv_addr)
        bytesRead = sock.recv(1024)
        if bytesRead is None:
            return False
        return True
    except:
        return False
    


if __name__ == '__main__':
    if test_depth_sensor():
        print("CONNECTED")
    else:
        print("NOT CONNECTED")
    if test_zed_camera():
        print("CONNECTED")
    else:
        print("NOT CONNECTED")
    if test_DVL():
        print("CONNECTED")
    else:
        print("NOT CONNECTED")
    

    