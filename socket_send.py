import socket
import typing
import time

"""
    discord: @kialli
    github: @kchan5071

    Displays information on monitor in caracara

"""

SOCKET_DIRECTORY = '/tmp/python-services/'
SOCKET_NAME = 'screen_service.sock'


def send_message(socket_name: str, message: str):
    """
    Sends a message to the server through the specified socket.
    """
    sock = create_client_socket(socket_name)
    try:
        time.sleep(1)  # Wait for the server to be ready
        # Send data
        sock.sendall(message.encode('utf-8'))
        # Look for the response
        amount_received = 0
        amount_expected = len(message)
        while amount_received < amount_expected:
            data = sock.recv(1024)
            amount_received += len(data)
            print('Received:', data.decode())
    finally:
        sock.close()

def create_client_socket(socket_name: str) -> socket.socket:
    """
    Creates a client socket and connects it to the server.
    """
    # Create a TCP/IP socket
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

    server_address = SOCKET_DIRECTORY + socket_name
    # Connect the socket to the server
    print('connecting to %s' % server_address)
    sock.connect(server_address)
    return sock

def set_screen(color: typing.Tuple[int, int, int], title: str, subtitle: str):
    """
    Sets the screen with the specified color, title, and subtitle.
    """
    if color[0] < 0 or color[0] > 255:
        print("invalid red color value")
        return
    if color[1] < 0 or color[1] > 255:
        print("invalid green color value")
        return
    if color[2] < 0 or color[2] > 255:
        print("invalid blue color value")
        return

    message = str(color[0]) + ' ' + str(color[1]) + ' ' + str(color[2]) + ',' + title + ',' + subtitle
    send_message(SOCKET_NAME, str(message))



if __name__ == '__main__':
    # Example usage
    screen_color = (255, 0, 0)  # Red color
    screen_title = "Test_Title"
    screen_subtitle = "Test_Subtitle"
    set_screen(screen_color, screen_title, screen_subtitle)