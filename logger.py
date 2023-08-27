"""
logger.py

Description:
    This module provides a configurable logging setup for applications. It supports different types of logging, including console, file, and remote logging. 
    Configuration parameters are loaded from a YAML file, enabling easy adjustments to the logging behavior without changing the code. 
    The module also supports both synchronous and asynchronous logging using a queue mechanism.

Key Features:
    - JSON formatted logs for easy parsing and structured logging.
    - Supports console, file, and remote logging methods.
    - Asynchronous logging using queue mechanism.
    - Configurable using an external YAML configuration file.

Classes:
    - JSONFormatter: Custom log formatter to output logs in JSON format.
    - LoggerConfig: Singleton class to fetch and hold the logger configuration.
    - LoggerBase: Base class for logger setup containing shared attributes and methods.
    - ConsoleLogger: Logger setup for console-based logging.
    - FileLogger: Logger setup for file-based logging.
    - RemoteLogger: Logger setup for remote logging.
    - LoggerFactory: Factory class for setting up and initializing loggers.

Usage:
    This module initializes a logger instance `app_logger` upon import. Logging configurations are loaded from `config.yaml`. 
    Example of usage:
        from logger import app_logger
        app_logger.info("This is an info log")

Note:
    When adjusting settings in the `config.yaml`, ensure that all necessary fields are populated to avoid errors.

Dependencies:
    - logging
    - logging.handlers
    - yaml
    - json
    - queue
    - urllib.parse

Author:
    Arash Naderian
Date:
    2023-08-27

Version:
    1.0.0
"""

import logging
import logging.handlers
import yaml
import json
import queue
from logging.handlers import QueueListener
from urllib.parse import urlparse

# Define defaults in a separate sector
DEFAULTS = {
    'LOGGER_NAME': 'APP',
    'LOGGER_DATEFMT': '%Y-%m-%d %H:%M:%S',
    'CONSOLE_HANDLER_LEVEL': 'INFO',
    'FILE_HANDLER_LEVEL': 'DEBUG',
    'FILE_NAME': 'app.log',
    'MAX_BYTES': 10485760,
    'BACKUP_COUNT': 3,
    'REMOTE_HANDLER_LEVEL': 'WARNING'
}


class JSONFormatter(logging.Formatter):
    """
    Formatter for emitting logs in JSON format.
    """
    def format(self, record) -> str:
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        return json.dumps(log_entry)


class LoggerConfig:
    _config = None

    @classmethod
    def get_config(cls) -> dict:
        """Loads the logger configuration from the config file. If no configuration is found, uses empty defaults."""
        if cls._config is None:
            try:
                with open('config.yaml', 'r') as file:
                    cls._config = yaml.safe_load(file)['logger']
            except (FileNotFoundError, KeyError, yaml.YAMLError) as e:
                print(f"Error loading logger configuration: {e}")
                cls._config = {}
        return cls._config


class LoggerBase:
    """
    Base class for logger setup. Contains shared attributes and methods.
    """
    def __init__(self):
        self.config = LoggerConfig.get_config()
        self.formatter = JSONFormatter(datefmt=self.config.get('logger_datefmt', DEFAULTS['LOGGER_DATEFMT']))
        self.log_queue = queue.Queue(-1)
        self.queue_handler = logging.handlers.QueueHandler(self.log_queue)


class ConsoleLogger(LoggerBase):
    """
    Logger setup for console-based logging.
    """
    LOG_TYPE = 'console'

    def setup(self) -> logging.Handler:
        """Set up and return console handler."""
        ch = logging.StreamHandler()
        ch.setFormatter(self.formatter)
        ch.setLevel(getattr(logging, self.config['console'].get('logger_console_handler_level', DEFAULTS['CONSOLE_HANDLER_LEVEL'])))
        return ch


class FileLogger(LoggerBase):
    """
    Logger setup for file-based logging.
    """
    LOG_TYPE = 'file'

    def setup(self) -> logging.Handler:
        """Set up and return file handler."""
        rf_handler = logging.handlers.RotatingFileHandler(
            self.config['file'].get('logger_file_name', DEFAULTS['FILE_NAME']),
            maxBytes=self.config['file'].get('logger_max_bytes', DEFAULTS['MAX_BYTES']),
            backupCount=self.config['file'].get('logger_backup_count', DEFAULTS['BACKUP_COUNT'])
        )
        rf_handler.setLevel(getattr(logging, self.config['file'].get('logger_file_handler_level', DEFAULTS['FILE_HANDLER_LEVEL'])))
        rf_handler.setFormatter(self.formatter)
        return rf_handler


class RemoteLogger(LoggerBase):
    """
    Logger setup for remote logging.
    """
    LOG_TYPE = 'remote'

    def setup(self) -> logging.Handler:
        """Set up and return remote handler if a remote logging URL is provided."""
        remote_level = self.config['remote'].get('logger_remote_handler_level', DEFAULTS['REMOTE_HANDLER_LEVEL'])
        remote_url = self.config['remote'].get('logger_remote_logging_url')
        
        if remote_level != 'NONE' and remote_url:
            parsed_url = urlparse(remote_url)
            http_handler = logging.handlers.HTTPHandler(
                host=f"{parsed_url.hostname}:{parsed_url.port or '80'}",
                url=parsed_url.path or "/log",
                method="POST",
            )
            http_handler.setLevel(getattr(logging, remote_level))
            http_handler.setFormatter(self.formatter)
            return http_handler
        return None


def get_handlers_with_listeners(logger_classes: list) -> tuple:
    """
    Return handlers and listeners based on given logger classes.
    """
    handlers = []
    listeners = []
    base_logger = LoggerBase()
    for logger_class in logger_classes:
        if base_logger.config[logger_class.LOG_TYPE].get('async', False):
            handler = logger_class().setup()
            if handler:   # Check if handler is not None
                listener = QueueListener(base_logger.log_queue, handler)
                listeners.append(listener)
                handlers.append(base_logger.queue_handler)
        else:
            handler = logger_class().setup()
            if handler:   # Check if handler is not None
                handlers.append(handler)
    return handlers, listeners


class LoggerFactory:
    """
    Factory for setting up loggers.
    """
    @staticmethod
    def setup() -> tuple:
        """Set up logger and listeners and return them."""
        config = LoggerConfig.get_config()
        root_logger = logging.getLogger(config.get('logger_name', DEFAULTS['LOGGER_NAME']))
        root_logger.setLevel(logging.DEBUG)

        handlers, listeners = get_handlers_with_listeners([ConsoleLogger, FileLogger, RemoteLogger])
        for handler in handlers:
            root_logger.addHandler(handler)
        for listener in listeners:
            listener.start()

        return root_logger, listeners


# Initialization
app_logger, log_listeners = LoggerFactory.setup()
