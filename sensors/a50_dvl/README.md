# A50 Sensor Data Acquisition and Publication

## Overview
This Python script enables the acquisition, parsing, and publication of A50 sensor data from the robot. The A50 sensor data is retrieved from a web server using TCP/IP communication (sockets). Here we will take that information and regurgitate it out. The script connects to the specified IP address and port, receives the data stream in JSON format, parses it, and publishes the extracted sensor data.

## Setup
### A50 Sensor Configuration:
- Ensure that the origin computer (computer in the sub) is turned on and connected to power.
- Confirm that the A50 sensor is properly configured and running.
- Verify that batteries are connected to the submarine and adequately charged.
- Check that all necessary cables are securely connected to the origin computer running Ubuntu 20.04 LTS.

### Network Configuration:
- Check network connectivity between the origin computer and the A50 sensor. You can use utilities like `ping` or traceroute to verify connectivity (whatever IP address set on the orin or by default `192.168.194.25`)
- Type `nc -v 192.168.1.4 16171` (assuming your ip has the same subnet mask) or `nc -v 192.168.194.25 16171` (default ip value) in the command line to can see the data.

## Usage:
1. Modify the `TCP_IP` and `TCP_PORT` constants in the script to match the IP address and port number of your A50 sensor.
2. Run the script using the following command:
   ```
   python3 get_a50_data.py
   ```
3. Once the script is running, it will continuously receive and process A50 sensor data.

## Features:
- Automatically reconnects to the socket in case of connection errors.
- Parses JSON data for specific sensor values such as yaw, pitch, roll, x, y, and z coordinates.
- Publishes the extracted sensor data in the terminal for further processing or visualization.

## Dependencies:
- Python 3.x
- The script uses the built-in `socket` and `json` modules, which are included in Python's standard library.

## Note:
- Ensure that the A50 sensor is properly configured and running, and the specified IP address and port are accessible from your network.
- Handle any errors or exceptions encountered during script execution appropriately to maintain continuous data acquisition.

**Author:**
`@Zix` on discord
- [C++ codebase](https://github.com/Mechatronics-SDSU/Mechatronics-2023/blob/beta/ros2_ws/src/a50_node/src/a50_node.cpp)

**Contributor:**
-  Halie (`@duh` on discord)
