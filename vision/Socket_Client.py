#opencv import
import cv2
#socket import
import socket
#import for packing
import pickle
import struct

class Client:
    """
    discord: @kialli
    github: @kchan5071
    
    connects to server and sends video data from numpy arrays to server

    this class is not used in production code, but is used for testing
    
    """
    def __init__(self, host, port):
        self.HOST = host
        self.PORT = port
        self.client_socket = None
        print("Set Client Variables")

    def connect_to_server(self):
        """
            connects to server
        """
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            print("Connecting to the server...")
            self.client_socket.connect((self.HOST, self.PORT))
            print(f"Connected to the server at {self.HOST}")
        except Exception as e:
            print(f"Connection error: {e}")
            self.client_socket = None

    def send_video(self, frame):
        """
            turns frame into bytes and sends to server using send_bytes
            input:
                frame: np_array
        """
        try:
            small_frame = cv2.resize(frame, None, fx=0.4, fy=0.4)
            data = pickle.dumps(small_frame)
        except Exception as exception:
            raise Exception(f"Error occurred while preparing image to be sent: {exception}")
    
        try:
            self.send_bytes(data = struct.pack("=L", len(data)) + data, data_description = "image")
        except Exception as exception:
            raise exception
        
    def send_bytes(self, data: bytes, data_description: str = "data"):
        """
            Sends bytes to the connected socket.
            input:
                data: bytes to send
                data_description: description of data to send
        """
        if self.client_socket is None:
            raise Exception(f"Connection not established. Cannot send {data_description} to socket.")
        
        try:
            data = self.client_socket.sendall(data)
        except Exception as exception:
            raise Exception(f"Error occurred while sending {data_description} to socket: {exception}")