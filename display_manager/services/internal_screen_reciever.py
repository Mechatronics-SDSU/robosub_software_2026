import socket
import os
import time
import sys
sys.path.append("..")


import tkinter  as tk
import socket_manager

SOCKET_NAME = "screen_service.sock"
WINDOW_TITLE = "State Display"
WINDOW_SIZE = "800x600"

TITLE_SIZE = 72
SUBTITLE_SIZE = 28
FONT = "Segoe UI"

WATCHDOG_TIMEOUT = 2  # seconds


class DisplayManager:
    def __init__(self):
        self.socket_address = socket_manager.get_available_socket_name(SOCKET_NAME)
        self.sock = None
        self.title = "Window Started"
        self.subtitle = None
        self.color = (0, 0, 0)  # Default color
        self.window = tk.Tk()

        self.window.title(WINDOW_TITLE)
        self.window.geometry(WINDOW_SIZE)
        self.window.configure(bg=f'#{self.color[0]:02x}{self.color[1]:02x}{self.color[2]:02x}')
        
        # Create a canvas to display the image
        self.image = tk.Canvas(self.window, width=800, height=600, bg=f'#{self.color[0]:02x}{self.color[1]:02x}{self.color[2]:02x}')
        self.image.pack(fill=tk.BOTH, expand=True)

        self.last_access_time = None
        
    def update_window(self) -> None:
        color = '#%02x%02x%02x' % self.color
        print(color)
        self.window.configure(bg=color)
        # Clear previous widgets
        for widget in self.window.winfo_children():
            widget.destroy()
        # Add title and subtitle
        tk.Label(self.window, text=self.title, font=(FONT, TITLE_SIZE, "bold"),
                bg=color, fg="white").pack(pady=(40, 6))
        tk.Label(self.window, text=self.subtitle, font=(FONT, SUBTITLE_SIZE, "bold"),
                bg=color, fg="white").pack()        
            
    def unlink_socket(self) -> None:
        try:
            os.unlink(self.socket_address)
        except FileNotFoundError:
            pass

    def run_server(self) -> None:
        while True:
            # Unlink the socket if it already exists
            if self.test_socket_connection():
                self.unlink_socket()


            # Create a socket
            self.create_server_socket()

            data = self.get_data()


            if data:
                data = data.decode('utf-8')
            else:
                data = "No data received"
            
            # Parse the received data
            data = data.split(',')

            print(f"Received data: {data}")

            color = data[0].split(' ')

            if len(data) < 3:
                print("Insufficient data received, using defaults.")
                self.color = (0, 0, 0)
                self.title = "No Title"
                self.subtitle = "No Subtitle"
            else: 
                if data[1] is not None:
                    self.title = data[1]
                else:
                    self.title = "No Title"

                if data[2] is not None:
                    self.subtitle = data[2]
                else:
                    self.subtitle = "No Subtitle"

                # Set the image color based on the received data
                self.color = (int(color[0]), int(color[1]), int(color[2]))
            
            # Update the window with the new color, title, and subtitle
            self.update_window()

            self.window.update_idletasks()

            # Clean up the connection
            self.connection.close()
            self.sock.close()
            
    def test_socket_connection(self) -> bool:
        try:
            os.unlink(self.socket_address)
        except Exception:
            return True
        return False

    def create_server_socket(self) -> None:
        # Create a TCP/IP socket
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

        # Bind the socket to the address
        self.sock.bind(self.socket_address)

        self.sock.listen(1)

        # Wait for a connection
        self.connection, _ = self.sock.accept()
        self.last_access_time = time.time()

    def get_data(self) -> bytes:
        # Receive the data in small chunks and retransmit it
        while True:
            data = self.connection.recv(1024)
            if data:
                self.connection.sendall(data)
                return data
            else:
                if time.time() - self.last_access_time > WATCHDOG_TIMEOUT:
                    print("Watchdog timeout reached, closing connection.")
                    self.connection.close()
                    self.sock.close()
                    return None
                break



if __name__ == '__main__':
    echo_server = DisplayManager()
    echo_server.run_server()
