#!/usr/bin/env python3

import socket
import json


TCP_IP = '192.168.194.95' 
TCP_PORT = 16171 
BUFFER_SIZE = 1024

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
            x = json_dict["x"]
            y = json_dict["y"]
            z = json_dict["z"]
            yaw = json_dict["yaw"]
            pitch = json_dict["pitch"]
            roll = json_dict["roll"]
            return [yaw, pitch, roll, x, y, z]
        except Exception as e:
            print("Failed to parse JSON:", e)
            return [] 

    def printData(self, a50_data):
        print("yaw:", a50_data[0], "pitch:", a50_data[1], "roll:", a50_data[2])
        print("x:", a50_data[3], "y:", a50_data[4], "z:", a50_data[5])

        #a50_data = [yaw, pitch, roll, x, y, z]

    def recieveData(self):
        dvl_data = None
        while dvl_data == None:
            try:
                bytesRead = self.sock.recv(BUFFER_SIZE)
                if len(bytesRead) < 600:
                    json_dict = json.loads(bytesRead)
                    a50_data = self.parseJson(json_dict)
                    self.printData(a50_data)
                    dvl_data = a50_data
            except Exception as e:
                print("Error in getting A50 data:", e)
                self.sock.close()
                self.sock = self.connectToSocket() 
        return dvl_data

    def run(self):
        if self.sock:
            while True:
                self.recieveData() 

if __name__ == "__main__":
    a50_node = DVL()
    a50_node.run()
