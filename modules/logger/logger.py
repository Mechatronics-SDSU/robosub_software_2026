"""
Logger class for logging messages with different severity levels.
"""
import logging
import multiprocessing

class Logger:
    def __init__(self,):
        """
        Initialize the Logger instance with a process-specific logger.
        """
        self.logger = logging.getLogger()

        # Ascending order: DEBUG, INFO, WARNING, ERROR, CRITICAL
        level = logging.DEBUG  # Default level
        
        self.logger.setLevel(level)

        # Avoid adding handlers multiple times if this class is instantiated again
        if not self.logger.handlers:

            process_name = multiprocessing.current_process().name

            safe_process_name = "".join(
                each_process if each_process.isalnum() or each_process in ("-", "_") else "_"
                for each_process in process_name
            )

            formatter = logging.Formatter(
                "%(asctime)s - %(processName)s - %(levelname)s - "
                "%(filename)s:%(lineno)d - %(message)s",
                datefmt="%Y-%m-%d"
            )

            # Console handler
            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(formatter)
            stream_handler.setLevel(level)
            self.logger.addHandler(stream_handler)

            # File handler
            file_handler = logging.FileHandler(
                            f"log_{safe_process_name}.txt",
                            mode="a"
                            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(level)
            self.logger.addHandler(file_handler)

    def debug(self, message, state=None):
        """
        Log a debug message, optionally including the current state.
        """
        if state is not None:
            self.logger.debug(f"[{state}] {message}")
        else:
            self.logger.debug(message)

    def info(self, message, state=None):
        """
        Log an info message, optionally including the current state.
        """
        if state is not None:
            self.logger.info(f"[{state}] {message}")
        else:
            self.logger.info(message)

    def warning(self, message, state=None):
        """
        Log a warning message, optionally including the current state.
        """
        if state is not None:
            self.logger.warning(f"[{state}] {message}")
        else:
            self.logger.warning(message)

    def error(self, message, state=None):
        """
        Log an error message, optionally including the current state.
        """
        if state is not None:
            self.logger.error(f"[{state}] {message}")
        else:
            self.logger.error(message)

    def critical(self, message, state=None):
        """
        Log a critical message, optionally including the current state.
        """
        if state is not None:
            self.logger.critical(f"[{state}] {message}")
        else:
            self.logger.critical(message)
