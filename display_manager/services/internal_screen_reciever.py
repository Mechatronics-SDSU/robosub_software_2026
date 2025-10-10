import socket
import os
import time
import sys
import tkinter      as tk
# allow import from parent directory for socket_manager
sys.path.append("..")
import socket_manager

"""
    discord: @kialli
    github: @kchan5071

    simple display manager that creates a window and listens for data on a unix socket
    the data should be in the format "R G B,TITLE,SUBTITLE"

    the window will change to the specified color and display the title and subtitle
    if no data is received for WATCHDOG_TIMEOUT seconds, the connection will be closed and a
    new connection will be accepted

    socket name, window title, and window size can be configured below
    font and title sizes can also be configured below
    the socket directory is specified in config.yaml
"""

SOCKET_NAME = "screen_service.sock"
WINDOW_TITLE = "State Display"
WINDOW_SIZE = "800x600"

TITLE_SIZE = 72
SUBTITLE_SIZE = 28
FONT = "Segoe UI"

WATCHDOG_TIMEOUT = 2  # seconds

P_DEBUG = False  # Enable debug prints


class DisplayManager:
    def __init__(self):
        #request a unique socket name
        self.socket_address = socket_manager.get_available_socket_name(SOCKET_NAME)
        self.sock = None
        #
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
        """
        Updates the window with the current color, title, and subtitle.
        """
        # Update the background color (RGB to Hex)
        color = '#%02x%02x%02x' % self.color
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
        """
        Unlinks the socket file if it exists.
        this is to ensure that the socket can be recreated
        """
        try:
            os.unlink(self.socket_address)
        except FileNotFoundError:
            pass

    def run_server(self) -> None:
        """
        Runs the display manager server to listen for incoming connections and update the window.
        """
        while True:
            # Unlink the socket if it already exists
            if self.test_socket_connection():
                self.unlink_socket()

            # Create a socket
            self.create_server_socket()

            # Receive the data
            data = self.get_data()
            
            # Parse the received data
            if data:
                data = data.decode('utf-8')
            else:
                data = "No data received"
            data = data.split(',')
            color = data[0].split(' ')

            if P_DEBUG: 
                print(f"Received data: {data}")

            if len(data) < 3:
                if P_DEBUG:
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
        """
        Creates a server socket and waits for a connection.
        Sets an intial access time for the watchdog timer.
        """
        # Create a TCP/IP socket
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

        # Bind the socket to the address
        self.sock.bind(self.socket_address)

        self.sock.listen(1)

        # Wait for a connection
        self.connection, _ = self.sock.accept()
        self.last_access_time = time.time()

    def get_data(self) -> bytes:
        """
        Receives data from the socket connection.
        Implements a watchdog timer to close the connection if no data is received within WATCHDOG_TIMEOUT.
            """
        # Receive the data in small chunks and retransmit it
        while True:
            data = self.connection.recv(1024)
            if data:
                self.connection.sendall(data)
                return data
            else:
                if time.time() - self.last_access_time > WATCHDOG_TIMEOUT:
                    if P_DEBUG:
                        print("Watchdog timeout reached, closing connection.")
                    self.connection.close()
                    self.sock.close()
                    return None
                break


#this is the entrypoint for the service
if __name__ == '__main__':
    echo_server = DisplayManager()
    echo_server.run_server()
