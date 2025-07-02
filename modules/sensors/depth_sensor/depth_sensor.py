from serial import Serial

PORT = '/dev/ttyACM0'
BAUDRATE = 115200

class DepthSensor:
    def __init__(self):
        self.ser = Serial(PORT,BAUDRATE)
        self.ser.flushInput()
    
    def print_data(self, depth):
        print("z:", depth)

    def recieve_data(self):
        try:
            return self.ser.readline().decode('ascii')
        except:
            pass

    def run(self):
        while True:
            if self.ser:
                self.recieveData() 

if __name__ == "__main__":
    depth_node = DepthSensor()
    depth_node.run()