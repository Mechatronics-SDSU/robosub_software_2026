import logging
import time
import os
from multiprocessing import Array, Value

class Better_Logger:
    def __init__(self):
        self.logger = logging.getLogger('BetterLogger')
        
        # Ascending order: DEBUG, INFO, WARNING, ERROR, CRITICAL
        level = logging.DEBUG  # Default level
        self.logger.setLevel(level)
        
        """
        Create a formatter with filename and lineno
        asctime: time of the log
        name: name of the logger
        levelname: level of the log
        filename: file where the log was called
        lineno: line number in the file
        message: the log message
        """
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
        # Create a console handler and set the formatter
        self.logger.handlers.clear()
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        # Add the handler to the logger
        self.logger.addHandler(ch)

    def write_log(self, message):
        with open(os.path.expanduser("~/robosub_software_2025/modules/logger/logs.yaml"), 'w') as file:
            file.write(message)

    def info(self, message):
        self.logger.info(message)
        self.write_log(message)

    def debug(self, message):
        self.logger.debug(message)
        self.write_log(message)

    def warning(self, message):
        self.logger.warning(message)
        self.write_log(message)

    def error(self, message):
        self.logger.error(message)
        self.write_log(message)

    def critical(self, message):
        self.logger.critical(message)
        self.write_log(message)
    