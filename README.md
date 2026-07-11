# Robosub Software 2026
This is the codebase for the SDSU Mechatronics Club competing in Robosub 2026, which manages sensor data, motor control, computer vision, and mission control, among other things. 

### Outline

- Date Created: 01/01/2026
- Contributors:
    - Ryan Sundermeyer (GitHub: @rsunderr, Discord: @.kech)
    - Kai Chan (GitHub: @kchan5071, Discord: @kialli)
    - Andy Chen (GitHub: @AndyC534, Discord: @creatine4053)
    - Sam Georges (GitHub: @thesamgeorges, Discord: @smoonth.)
    - Joe Lofrese (GitHub: @Joelofrese, Discord: @croppie_luvr)
    - Juan Cota (GitHub: @Juanlo01, Discord: @chewchew0366)
    - Malaika Joiner (GitHub: @malaikajoiner, Discord: @314piekitty)
    - Alice Vo (GitHub: @alicvo, Discord: @alicvo)
- Dependencies:
    - Python 3.11+
    - Yolov5 7.0.13
    - Argparse 1.4.0
    - Inputs 0.5
    - Python-can 3.3.3
    - cffi 1.16.0
    - onnx 1.16.1
    - PyYAML 6.0
    - Pyserial 3.5
    - Matplotlib 3.7.2
    - Zed SDK
    - NVIDIA Orin SDK

### Key Directories

- modules
    - Where the key features of the code are kept, primarily sensor handling, PIDs, and motor control
- utils
    - Miscellanious helper or setup scripts not used in real-time
- fsm
    - Where the various mode state machines are kept, which handle decision making
- docs
    - Documentation and templates stored here
- display_manager
    - Display code kept here

### Key Files

- launch.py
    - The primary file of the code base, manages mission control by switching between modes and handling subprocesses
- shared_memory.py
    - How all of the different files communicate, through a list of shared variables passed through an object
- objects.yaml
    - The config file for the whole code base, lets you choose the pool at the top and customize coordinates
- btn_press.py
    - This script will read input from the button on caracara and run launch.py when green is pressed, running the sub
- pyproject.toml
    - Auto generated file tracking python dependencies

### Usage

- Edit the objects.yaml config file to choose what course to follow and target locations, read comments (IMPORTANT)
- Run "python3 btn_press.py" to run the sub after the green button is pressed
- Run "python3 launch.py" to run the sub immediately
- Run "stop" or "kill" to instantly kill the motors using an alias from the bashrc

### Notes

- Modes: The process of completing a single objective in the pool
- States: A specific step within a mode
- If you are a contributor, please write your code in a branch, create a pull request, and a software lead will merge after a code review

### Status

- Current status: In Progress
