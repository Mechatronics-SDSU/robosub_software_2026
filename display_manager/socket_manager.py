import socket
import os
from typing import List

from config_parser import read_config

import random
def get_available_socket_name(socket_name: str=None) -> str:
    """
    Generates a unique socket name by appending a random number to the provided socket name.
    If no socket name is provided, it generates a random socket name.
    """
    # Get the socket directory from the configuration
    socket_directory = read_config('../config.yaml')['socket_directory']

    # generate a random socket name if none is provided
    if socket_name is None:
        socket_name = f"socket_{random.randint(1000, 9999)}.sock"

    # check if the socket name already exists, if so, generate a new one 
    name_found = False
    while not name_found:
        if os.path.exists(os.path.join(socket_directory, socket_name)):
            socket_name = f"socket_{random.randint(1000, 9999)}.sock"
        else:
            name_found = True
    return socket_directory + '/' + socket_name
    

def list_open_sockets(socket_directory: str) -> List[str]:
    """
    Lists all open sockets in the specified directory.
    """
    # Ensure the directory exists
    if not os.path.exists(socket_directory):
        os.makedirs(socket_directory)

    # List all files that end with .sock in the directory    
    sockets = []
    for file in os.listdir(socket_directory):
        if file.endswith('.sock'):
            sockets.append(os.path.join(socket_directory, file))

    # Check if the sockets are available
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    for socket_name in sockets:
        try:
            sock.connect(socket_name)
            sock.close()
        except socket.error:
            # Socket is not available
            sockets.remove(socket_name)

    return sockets