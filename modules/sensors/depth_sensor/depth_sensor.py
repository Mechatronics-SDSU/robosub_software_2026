from serial import Serial

PORT = '/dev/ttyACM0'
BACKUP_PORT = '/dev/ttyACM1'
BAUDRATE = 115200

class DepthSensor:
    def __init__(self):
        try:
            self.ser = Serial(PORT,BAUDRATE)
            self.ser.flushInput()
        except:
            self.ser = Serial(BACKUP_PORT,BAUDRATE)
            self.ser.flushInput()
    
    def print_data(self, depth):
        print("z:", depth)
        pass

    def receive_data(self):
        try:
            data = self.ser.readline().decode('ascii')
            print("data: ", data)
            if "Depth: " in data:
                # print(data)
                data_stripped = data.strip()
                if data_stripped is not None:
                    return data_stripped.split('Depth:')[1]
        except:
            return -1

    def run(self):
        while True:
            if self.ser:
                try:
                    data = self.receive_data() 
                    # print(data)
                except IndexError as e:
                    print(e)
                    self.ser.flushInput()




if __name__ == "__main__":
    depth_node = DepthSensor()
    print("depth sensor connected")
    depth_node.run()