import socket
import json
import time
from random import choice, uniform

# # Define constants
TCP_IP = "localhost"  # IP address of the A50 sensor
TCP_PORT = 56789  # Port number the A50 sensor is listening on
BUFFER_SIZE = 1024  # Size of the receive buffer

def generate_fake_data():
    fake_data = {}
    
    
    # Generate random values for orientation or skip
    if choice([True, False]):    # Generate random values for position
        fake_data["x"] = uniform(0, 100)
        fake_data["y"] = uniform(0, 100)
        fake_data["z"] = uniform(0, 100)
        fake_data["yaw"] = uniform(-180, 180)
        fake_data["pitch"] = uniform(-180, 180)
        fake_data["roll"] = uniform(-180, 180)

        
    else:
        # Alternatively, include "sx", "sy", "sz" without orientation info
        fake_data["sx"] = uniform(0, 100)
        fake_data["sy"] = uniform(0, 100)
        fake_data["sz"] = uniform(0, 100)
    
    return fake_data

def run_mock_server():
    # Create a socket and listen on the specified IP address and port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        # server_socket.bind((TCP_IP, TCP_PORT))
        server_socket.bind((TCP_IP, TCP_PORT))
        server_socket.listen(1)
        print("Mock server started. Listening on {}:{}".format(TCP_IP, TCP_PORT))
        while True:
            # Accept incoming connections
            conn, addr = server_socket.accept()
            print("Connection from:", addr)
            try:
                # Generate fake A50 data
                fake_data = generate_fake_data()
                # Convert data to JSON format
                json_data = json.dumps(fake_data)
                # Send JSON data to the client
                conn.send(json_data.encode())
                print("Sent fake A50 data:", json_data)
            except Exception as e:
                print("Error sending fake data:", e)
            finally:
                # Close the connection
                conn.close()

if __name__ == "__main__":
    run_mock_server()
