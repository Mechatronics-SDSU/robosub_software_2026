#!/opt/homebrew/anaconda3/bin/python

import subprocess
import os
import shutil

import config_parser

def get_service_pids(service_csv: str) -> dict:
    """
    Reads the service CSV file and returns a dictionary of service names and their PIDs.
    """
    service_pids = {}
    with open(service_csv, 'r') as file:
        for line in file:
            # parse the line to get service name and PID assuming name,pid format
            service, pid = line.strip().split(',')
            service_pids[service] = pid
    return service_pids

def stop_service(service: str, pid: str):
    """
    Stops the service with the given PID.
    """
    # try to kill the subprocess
    try:
        process = subprocess.Popen(['kill', pid])
        process.wait()
        print(f'Stopped service {service} with pid {pid}.')
    except:
        print(f'Could not stop service {service}.')

def stop_services(service_csv: str):
    """
    Stops all services listed in the service CSV file using the PIDs.
    """
    # Check if the CSV file exists, if not, use the default
    if os.path.exists(service_csv):
        service_csv = os.path.join(os.getcwd(), service_csv)
    else:
        service_csv = os.path.join(os.getcwd(), config_parser.read_config('config.yaml')['services_csv'])
 
    # Read the service CSV file and get the PIDs
    service_pids = get_service_pids(service_csv)

    # Stop each service using the PID
    for service, pid in service_pids.items():
        stop_service(service, pid)
    print('All services stopped.')

def clear_sockets(socket_directory: str):
    """
    Clears all sockets in the specified directory.
    """
    # basically nuke the directory containing the sockets and remake it
    try:
        shutil.rmtree(socket_directory)
    except FileNotFoundError:
        print('No sockets to clear.')
        return
    os.makedirs('/tmp/python-services')
    print('Sockets cleared.')

if __name__ == '__main__':
    config = config_parser.read_config('config.yaml')
    if config['clear_socket']:
        clear_sockets(config['socket_directory'])
    if config['stop_services']:
        stop_services(config['services_csv'])
