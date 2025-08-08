import socket
import os
import cv2
import numpy as np

import sys
sys.path.append("..")


import socket_manager


class EchoServer:
    def __init__(self):
        self.socket_address = socket_manager.get_available_socket_name("screen_service.sock")
        self.sock = None
        self.image = np.zeros((400, 600, 3), dtype=np.uint8) # 400x600 black image

        self.data = "Echo Service Running"
        org = (50, 50)
        fontFace = cv2.FONT_HERSHEY_SIMPLEX
        fontScale = 1
        color = (255, 255, 255) # White color
        thickness = 2
        self.image = cv2.putText(self.image, self.data, org, fontFace, fontScale, color, thickness, cv2.LINE_AA)


    def run_server(self):
        while True:
            # Check if the socket file exists
            if not self.test_socket_connection():
                try:
                    os.unlink(self.socket_address)
                except FileNotFoundError:
                    pass

            # Create a socket
            self.create_server_socket()
            self.sock.listen(1)

            # Wait for a connection
            self.connection, _ = self.sock.accept()
            self.image.fill(0)  # Clear the image
            # perform the echo operation
            data = self.echo()

            if data:
                data = data.decode('utf-8')
            else:
                data = "No data received"
            
            # Parse the received data
            data = data.split(',')

            print(f"Received data: {data}")

            color = data[0].split(' ')
            title = data[1]
            subtitle = data[2]

            print(color)
            # Set the image color based on the received data
            color = (color[0], color[1], color[2])

            #set the image color
            self.image[:] = color
            self.image = cv2.cvtColor(self.image, cv2.COLOR_BGR2RGB)

            # Display a the message in the OpenCV window
            cv2.putText(self.image, f"Title: {title}", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(self.image, f"Subtitle: {subtitle}", (50, 150), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.imshow("Sub Viewer", self.image)
            cv2.waitKey(1)


            # Clean up the connection
            self.connection.close()
            self.sock.close()
            
    def test_socket_connection(self):
        try:
            os.unlink(self.socket_address)
        except Exception:
            return True
        return False

    def create_server_socket(self):
        # Create a TCP/IP socket
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

        # Bind the socket to the address
        self.sock.bind(self.socket_address)

    def echo(self):
        # Receive the data in small chunks and retransmit it
        while True:
            data = self.connection.recv(1024)
            if data:
                self.connection.sendall(data)
                return data
            else:
                break

if __name__ == '__main__':
    echo_server = EchoServer()
    echo_server.run_server()
