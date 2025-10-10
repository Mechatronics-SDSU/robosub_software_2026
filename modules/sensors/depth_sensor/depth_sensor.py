from serial import Serial

PORT = '/dev/ttyACM0'
BAUDRATE = 115200

class DepthSensor:
    def __init__(self):
        self.ser = Serial(PORT,BAUDRATE)
        self.ser.flushInput()
    
    def print_data(self, depth: str) -> None:
        print("z:", depth)

    def receive_data(self) -> str | None:
        try:
            return self.ser.readline().decode('ascii')
        except:
            pass

    def run(self) -> None:
        while True:
            if self.ser:
                data = self.receive_data() 
                if data.split():
                    print(data.split()[1])


if __name__ == "__main__":
    depth_node = DepthSensor()
    depth_node.run()