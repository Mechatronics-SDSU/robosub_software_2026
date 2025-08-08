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
        self.title = "Window Started"
        self.subtitle = None
        self.color = (0, 0, 0)  # Default color
        self.window = tk.Tk()

        self.window.title("State Display")
        self.window.geometry("800x600")
        self.window.configure(bg=f'#{self.color[0]:02x}{self.color[1]:02x}{self.color[2]:02x}')
        
        # Create a canvas to display the image
        self.image = tk.Canvas(self.window, width=800, height=600, bg=f'#{self.color[0]:02x}{self.color[1]:02x}{self.color[2]:02x}')
        self.image.pack(fill=tk.BOTH, expand=True)
        
    def update_window(self):
        color = '#%02x%02x%02x' % self.color
        self.window.configure(bg=color)
        # Clear previous widgets
        for widget in self.window.winfo_children():
            widget.destroy()
        # Add title and subtitle
        tk.Label(self.window, text=self.title, font=("Segoe UI", 22, "bold"),
                bg=color, fg="white").pack(pady=(40, 6))
        tk.Label(self.window, text=self.subtitle, font=("Segoe UI", 12),
                bg=color, fg="white").pack()


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
            self.title = data[1]
            self.subtitle = data[2]

            print(color)
            # Set the image color based on the received data
            self.color = (int(color[0]), int(color[1]), int(color[2]))
            
            # Update the window with the new color, title, and subtitle
            self.update_window()
            
            # Update the window
            self.window.update()


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
