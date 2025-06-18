#!/usr/bin/env python3

import socket
import json


TCP_IP = '192.168.194.95' 
TCP_PORT = 16171 
BUFFER_SIZE = 2048

class DVL:
    def __init__(self):
        self.serv_addr = (TCP_IP, TCP_PORT)
        self.sock = self.connectToSocket()
        self.buffer = bytearray(BUFFER_SIZE) 
        self.resetDeadReckoning()

    def resetDeadReckoning(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(self.serv_addr)
            json_command = {"command": "reset_dead_reckoning"}
            sock.send(json.dumps(json_command).encode())
            sock.close()
        except Exception as e:
            print("Failed to reset dead reckoning:", e)

    def connectToSocket(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(self.serv_addr)
            return sock 
        except Exception as e:
            print("Failed to connect to socket:", e)
            return None 

    def parseJson(self, json_dict):
        try:
            vx = json_dict["vx"]
            vy = json_dict["vy"]
            vz = json_dict["vz"]
            fom = json_dict["fom"]
            cov = json_dict["covariance"]
            alt = json_dict["altitude"]
            transducers = json_dict["transducers"]
            valid = json_dict["velocity_valid"]
            status = json_dict["status"]
            time = json_dict["time"]
            time_of_validity = json_dict["time_of_validity"]
            type_ = json_dict["type"]
            return "velocity", [vx, vy, vz, alt, valid, status]
        except Exception as e:
            # print("not velocity data", e)
            pass
        try:    
            x = json_dict["x"]
            y = json_dict["y"]
            z = json_dict["z"]
            yaw = json_dict["yaw"]
            pitch = json_dict["pitch"]
            roll = json_dict["roll"]
            return "dead_reckoning", [yaw, pitch, roll, x, y, z]
        except Exception as e:
            # print("Failed to parse JSON:", e)

            return [] 

    def printData(self, a50_data):
        print("yaw:", a50_data[0], "pitch:", a50_data[1], "roll:", a50_data[2])
        print("x:", a50_data[3], "y:", a50_data[4], "z:", a50_data[5])

        #a50_data = [yaw, pitch, roll, x, y, z]

    def recieveData(self):
        dvl_data = ""
        try:
            bytesRead = self.sock.recv(BUFFER_SIZE)
            dvl_data = bytesRead.decode()
            # print("dvl_data:", dvl_data)
        except Exception as e:
            print("Error in getting A50 data:", e)
            self.sock.close()
            self.sock = self.connectToSocket()
        message_type, ret = self.parseJson(json.loads(dvl_data))
        # print("message_type:", message_type)
        # print("ret:", ret)
        return message_type, ret
        
    def run(self):
        if self.sock:
            while True:
                self.recieveData() 


if __name__ == "__main__":
    a50_node = DVL()
    a50_node.run()
