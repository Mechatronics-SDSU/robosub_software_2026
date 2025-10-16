import socket
import json

"""
    original author unknown

    maintatiners
    discord: @.kech, @kialli
    github: @rsunderr, @kchan5071

    DVL A50 driver, connects to DVL over TCP socket
    recieves JSON data, parses it, and provides methods to get velocity and position data
    
"""

UDP_IP = '192.168.194.95' 
UDP_PORT = 16171 
BUFFER_SIZE = 2048

class DVL:
    def __init__(self):
        self.serv_addr = (UDP_IP, UDP_PORT)
        self.sock = self.connectToSocket()
        self.buffer = bytearray(BUFFER_SIZE) 
        self.resetDeadReckoning()

    def resetDeadReckoning(self) -> None:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(self.serv_addr)
            json_command = {"command": "reset_dead_reckoning"}
            sock.send(json.dumps(json_command).encode())
            sock.close()
        except Exception as e:
            print("Failed to reset dead reckoning:", e)

    def connectToSocket(self) -> socket.socket | None:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(self.serv_addr)
            return sock 
        except Exception as e:
            print("Failed to connect to socket:", e)
            return None 

    def parseJson(self, json_dict: dict) -> tuple[str, list] | list:
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
            print("Failed to parse JSON:", e)

            return [] 

    def printData(self, a50_data: list) -> None:
        print("yaw:", a50_data[0], "pitch:", a50_data[1], "roll:", a50_data[2])
        print("x:", a50_data[3], "y:", a50_data[4], "z:", a50_data[5])

    def recieveData(self) -> tuple[str, list] | list:
        dvl_data = ""
        try:
            # print("reading")
            bytesRead = self.sock.recv(BUFFER_SIZE)
            dvl_data = bytesRead.decode()
            # print("dvl_data:", dvl_data)
        except Exception as e:
            print("Error in getting A50 data:", e)
            self.sock.close()
            self.sock = self.connectToSocket()
        message_type, ret = self.parseJson(json.loads(dvl_data))
        return message_type, ret

if __name__ == "__main__":
    a50_node = DVL()
    while True:
        message_type, a50_data = a50_node.recieveData()
        if a50_data != None and message_type == "dead_reckoning":
            a50_node.printData(a50_data)