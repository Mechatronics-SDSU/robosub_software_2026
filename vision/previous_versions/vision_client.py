#opencv import
import cv2
#socket import
import socket
#import for packing
import sys
import pickle
import struct
import pyzed.sl as sl

HOST = '146.244.98.14'
PORT = 8089

import socket
import cv2
import pickle
import struct

class Client:
    def __init__(self, host, port):
        self.HOST = host
        self.PORT = port

    def connect_to_server(self):
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            print("Connecting to the server...")
            self.client_socket.connect((self.HOST, self.PORT))
            print(f"Connected to the server at {self.HOST}")
        except Exception as e:
            print(f"Connection error: {e}")
            self.client_socket = None

    def send_video(self):
        if self.client_socket is None:
            print("Connection not established. Cannot send video.")
            return

        cap = cv2.VideoCapture(0)
        print("Video feed set")

        try:
            while True:
                _, frame = cap.read()
                small_frame = cv2.resize(frame, None, fx=0.4, fy=0.4)
                data = pickle.dumps(small_frame)
                self.client_socket.sendall(struct.pack("=L", len(data)) + data)
        except KeyboardInterrupt:
            print("Video streaming stopped.")
        except Exception as e:
            print(f"Error sending video data: {e}")
        finally:
            self.client_socket.close()

def main():
        # Create a ZED camera object

    host = '146.244.98.37'
    port = 8089
    client = Client(host, port)
    client.connect_to_server()
    client.send_video()

if __name__ == "__main__":
    main()