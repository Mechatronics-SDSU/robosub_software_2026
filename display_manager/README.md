# Python Service Creator

this project starts and stops python services based on what is in the services folder, the current implementation supports unix-socket termination in /usr/python-services

the list of services started and their process ID's are stored in services.csv

## Usage

to start:
```Bash
./start_services.py
```

to stop:
```
./stop_services.py
```
