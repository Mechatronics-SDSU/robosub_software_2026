import logging
import time
import shared_memory
import os
from matplotlib import pyplot as plt
from multiprocessing import Array, Value


class Logger:
    def __init__(self, shared_memory_object, log_file='tmp.log', log_frequency=.1,log_dir='logs'):
        
        self.log_file = log_file
        self.shared_memory_object = shared_memory_object
        self.log_frequency = log_frequency
        self.log_dir = log_dir

    def log_shared_memory(self):
        # Set up logging
        logging.basicConfig(filename=self.log_file, level=logging.DEBUG,
                            format='%(asctime)s %(levelname)s:%(message)s')
        self.logger = logging.getLogger()
        self.logger.info('Logger started.')
        attributes = self.shared_memory_object.__dict__.keys()
        while (self.shared_memory_object.running.value):
            # Log the values from shared memory
            # Add more shared memory logs as needed
            # Sleep for a short duration to avoid excessive logging
            for attribute in attributes:
                value = getattr(self.shared_memory_object, attribute)
                if isinstance(value, type(Array('d', 3))):
                    value = list(value)
                    for i in range(len(value)):
                        self.logger.debug(f'{attribute}[{i}]: {value[i]}')
                elif isinstance(value, type(Value)):
                    value = value.value
                    self.logger.debug(f'{attribute}: {value}')
                else:   
                    self.logger.debug(f'{attribute}: {value.value}')
            # Log the shared memory values
            time.sleep(self.log_frequency)
            self.logger.debug('break')
        self.logger.info('Logger stopped.')
        # Move the log file to the specified directory
        self.graph_logs()
        self.move_log_file()

    def move_log_file(self):
        # Move the log file to the specified directory
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
        new_log_file_path = os.path.join(self.log_dir, os.path.basename(str(time.time()) + '.log'))
        os.rename(self.log_file, new_log_file_path)
        self.log_file = new_log_file_path
        print(f"Log file moved to {self.log_dir}")

    def graph_logs(self):
        self.logger.setLevel(logging.WARNING)
        # Read the log file and plot the values
        with open(self.log_file, 'r') as f:
            lines = f.readlines()

        # Extract values from the log file
        imu_lin_acc = []
        imu_ang_vel = []
        distance_from_object = []
        depth = []
        dvl_status = []
        dvl_velocity_valid = []

        for line in lines:
            if 'imu_lin_acc[0]' in line:
                imu_lin_acc.append(eval(line.split(': ')[1]))
            elif 'imu_ang_vel[0]' in line:
                imu_ang_vel.append(eval(line.split(': ')[1]))
            elif 'distance_from_object' in line:
                distance_from_object.append(float(line.split(': ')[1]))
            elif 'depth' in line:
                depth.append(float(line.split(': ')[1]))
            elif 'running' in line:
                dvl_status.append(bool(line.split(': ')[1]))
            elif 'dvl_velocity_valid' in line:
                dvl_velocity_valid.append(bool(line.split(': ')[1]))

        # Plot the values
        plt.figure(figsize=(10, 6))
        plt.subplot(3, 2, 1)
        plt.plot(imu_lin_acc)
        plt.title('IMU Linear Acceleration')

        plt.subplot(3, 2, 2)
        plt.plot(imu_ang_vel)
        plt.title('IMU Angular Velocity')

        plt.subplot(3, 2, 3)
        plt.plot(distance_from_object)
        plt.title('Distance from Object')

        plt.subplot(3, 2, 4)
        plt.plot(depth)
        plt.title('Depth')

        plt.subplot(3, 2, 5)
        plt.plot(dvl_status)
        plt.title('DVL Status')

        plt.subplot(3, 2, 6)
        plt.plot(dvl_velocity_valid)
        plt.title('DVL Velocity Valid')

        plt.tight_layout()
        plt.show()
        print("Graphing complete.")
        self.logger.info('Graphing complete.')
        

