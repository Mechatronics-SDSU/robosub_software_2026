import socket
import os
import tkinter as tk
import numpy as np

import sys
sys.path.append("..")


import socket_manager


class DisplayManager:
    def __init__(self):
        self.socket_address = socket_manager.get_available_socket_name("screen_service.sock")
        self.sock = None
        self.image = np.zeros((400, 600, 3), dtype=np.uint8) # 400x600 black image

        self.data = "Echo Service Running"
        self.window_name = "State"
        #create a Tkinter window to display the image
        self.root = tk.Tk()
        self.root.title(self.window_name)
        self.root.geometry("600x400")
        self.canvas = tk.Canvas(self.root, width=600, height=400)
        self.canvas.pack()


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

            #set the image color and set the title and subtitle
            self.image[:] = np.array(color, dtype=np.uint8).reshape(1, 1, 3) * 255
            self.root.title(title)
            self.canvas.delete("all")
            self.tk_image = tk.PhotoImage(master=self.root, width=600, height=400)
            self.tk_image.put(self.image.reshape(400, 600, 3).tolist(),
                              to=(0, 0, 600, 400))
            self.canvas.create_image(0, 0, image=self.tk_image, anchor=tk.NW)

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
