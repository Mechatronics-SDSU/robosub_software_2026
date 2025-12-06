import logging
import time
import os
import yaml
from multiprocessing import Array, Value
from io import StringIO

class Better_Logger:
    def __init__(self):
        self.logger = logging.getLogger('BetterLogger')
        
        # Ascending order: DEBUG, INFO, WARNING, ERROR, CRITICAL
        level = logging.DEBUG  # Default level
        
        self.logger.setLevel(level)
        # Avoid adding handlers multiple times if this class is instantiated again
        if not self.logger.handlers:
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - "
                "%(filename)s:%(lineno)d - %(message)s"
            )

            # Console handler
            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(formatter)
            stream_handler.setLevel(logging.DEBUG)
            self.logger.addHandler(stream_handler)

            # File handler
            file_handler = logging.FileHandler('log.yaml', mode='a')
            file_handler.setFormatter(formatter)
            file_handler.setLevel(logging.DEBUG)
            self.logger.addHandler(file_handler)



    def info(self, message):
        self.logger.info(message)

    def debug(self, message):
        self.logger.debug(message)

    def warning(self, message):
        self.logger.warning(message)

    def error(self, message):
        self.logger.error(message)

    def critical(self, message):
        self.logger.critical(message)