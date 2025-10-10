import socket
import json


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
        # print("message_type:", message_type)
        # print("ret:", ret)
        return message_type, ret
        
    def run(self) -> None: #only for testing

        frames = 1

        recent_velocity_x = [0] * frames
        recent_velocity_y = [0] * frames
        recent_velocity_z = [0] * frames

        recent_position_x = [0] * frames
        recent_position_y = [0] * frames
        recent_position_z = [0] * frames

        average_velocity_x = 0
        average_velocity_y = 0
        average_velocity_z = 0

        average_position_x = 0
        average_position_y = 0
        average_position_z = 0

        yaw = 0
        pitch = 0
        roll = 0

        if self.sock:
            while True:
                message_type, ret = self.recieveData()
                if message_type == "velocity":
                    if ret[4] == True:
                        # x
                        recent_velocity_x.pop(0)
                        recent_velocity_x.append(ret[0])
                        average_velocity_x = 0
                        for velocity_x in recent_velocity_x:
                            average_velocity_x += velocity_x
                        average_velocity_x = round(average_velocity_x / frames, 3)
                        # y
                        recent_velocity_y.pop(0)
                        recent_velocity_y.append(ret[1])
                        average_velocity_y = 0
                        for velocity_y in recent_velocity_y:
                            average_velocity_y += velocity_y
                        average_velocity_y = round(average_velocity_y / frames, 3)
                        # z
                        recent_velocity_z.pop(0)
                        recent_velocity_z.append(ret[2])
                        average_velocity_z = 0
                        for velocity_z in recent_velocity_z:
                            average_velocity_z += velocity_z
                        average_velocity_z = round(average_velocity_z / frames, 3)
                elif message_type == "dead_reckoning":
                    # x
                    recent_position_x.pop(0)
                    recent_position_x.append(ret[3])
                    average_position_x = 0
                    for position_x in recent_position_x:
                        average_position_x += position_x
                    average_position_x = round(average_position_x / frames, 3)
                    # y
                    recent_position_y.pop(0)
                    recent_position_y.append(ret[4])
                    average_position_y = 0
                    for position_y in recent_position_y:
                        average_position_y += position_y
                    average_position_y = round(average_position_y / frames, 3)
                    # z
                    recent_position_z.pop(0)
                    recent_position_z.append(ret[5])
                    average_position_z = 0
                    for position_z in recent_position_z:
                        average_position_z += position_z
                    average_position_z = round(average_position_z / frames, 3)

                    yaw = ret[0]
                    pitch = ret[1]
                    roll = ret[2]


                print(f"avg velocity x: {average_velocity_x:.3f}")
                print(f"avg velocity y: {average_velocity_y:.3f}")
                print(f"avg velocity z: {average_velocity_z:.3f}")
                print()
                print(f"avg position x: {average_position_x:.3f}")
                print(f"avg position y: {average_position_y:.3f}")
                print(f"avg position z: {average_position_z:.3f}")
                print()
                print(f"yaw: {yaw:.3f}")
                print(f"pitch: {pitch:.3f}")
                print(f"roll: {roll:.3f}")
                print()


if __name__ == "__main__":
    a50_node = DVL()
    a50_node.run()
