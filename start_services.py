#!/opt/homebrew/anaconda3/bin/python

from typing import List, Tuple
import os
import subprocess

import config_parser

def initialize_socket_directory(socket_directory: str) -> str:
    """
    Initializes the socket directory.
    If the directory does not exist, it creates it.
    """
    try:
        os.makedirs(socket_directory)
    except FileExistsError:
        pass
    return socket_directory

def get_process_name_list(user_directory: str=None) -> List[str]:
    """
    Lists all Python files in the specified directory.
    """
    process_name_list = []
    for file in os.listdir(user_directory):
        if file.endswith('.py'):
            process_name_list.append(file)

    return process_name_list

def start_service(service_name: str, service_directory: str, python_executable: str) -> Tuple[str, int]:
    """
    Starts the specified service by executing the Python file.
    Returns the service name and its process ID.
    """
    #search for python file and run it
    for file in os.listdir(service_directory):
        if file.endswith('.py') and file.startswith(service_name):
            #start process
            process = subprocess.Popen([python_executable, os.path.join(service_directory, service_name)], cwd=service_directory)
            pid = process.pid
            return (service_name, pid)
    return (None, None)

def start_services(user_directory: str, python_executable: str) -> List[Tuple[str, int]]:
    """
    Starts all services in the specified directory.
    Returns a list of tuples containing the service name and its process ID.
    """
    # Check if the directory exists, if not, create it
    if user_directory is None:
        print("No service directory provided, using default: cwd/services")
    user_directory = os.path.join(os.getcwd(), 'services')

    # List all Python files in the directory
    name_list = get_process_name_list(user_directory)

    # Start each python file as a service and store the process ID
    service_list = []
    for name in name_list:
        service_list.append(start_service(name, user_directory, python_executable))
        print(f'Started service {name}.')
    return service_list

def write_to_csv(services: List[Tuple[str, int]], filename: str) -> None:
    """
    Writes the service name and process ID to a CSV file.
    """
    # Check if the file exists, if not, create it
    if os.path.exists(filename):
        filename = os.path.join(os.getcwd(), filename)
    else:
        filename = os.path.join(os.getcwd(), 'services.csv')

    # Open the file in write mode and write the services
    with open(filename, 'w') as file:
        for service in services:
            file.write(f'{service[0]},{service[1]}\n')

if __name__ == '__main__':
    config_parser = config_parser.read_config('config.yaml')
    initialize_socket_directory(config_parser['socket_directory'])
    service_list = start_services(config_parser['service_directory'], config_parser['python_executable'])
    write_to_csv(service_list, config_parser['services_csv'])
    print('Services started.')
    print('Service list:', service_list)