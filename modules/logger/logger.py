"""
Logger class for logging messages with different severity levels.
"""

import logging
from pathlib import Path

class Logger:
    def __init__(self, file=None):
        if file is None:
            logger_name = "default"
            log_filename = "default.log"
        else:
            logger_name = Path(file).stem
            log_filename = f"{logger_name}.log"

        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False

        if not self.logger.handlers:
            formatter = logging.Formatter(
                "%(asctime)s - %(processName)s - %(levelname)s - "
                "%(filename)s:%(lineno)d - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )

            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(formatter)
            stream_handler.setLevel(logging.DEBUG)
            self.logger.addHandler(stream_handler)

            file_handler = logging.FileHandler(log_filename, mode="a")
            file_handler.setFormatter(formatter)
            file_handler.setLevel(logging.DEBUG)
            self.logger.addHandler(file_handler)

    def debug(self, message, state=None):
        self.logger.debug(
            f"[{state}] {message}" if state is not None else message,
            stacklevel=2
        )

    def info(self, message, state=None):
        self.logger.info(
            f"[{state}] {message}" if state is not None else message,
            stacklevel=2
        )

    def warning(self, message, state=None):
        self.logger.warning(
            f"[{state}] {message}" if state is not None else message,
            stacklevel=2
        )

    def error(self, message, state=None):
        self.logger.error(
            f"[{state}] {message}" if state is not None else message,
            stacklevel=2
        )

    def critical(self, message, state=None):
        self.logger.critical(
            f"[{state}] {message}" if state is not None else message,
            stacklevel=2
        )