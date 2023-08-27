import logging
import logging.handlers
import yaml
import json
import queue
from logging.handlers import QueueListener
from urllib.parse import urlparse

class JSONFormatter(logging.Formatter):
    """
    Emit logs in JSON format.
    """
    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            # Add more fields if needed
        }
        return json.dumps(log_entry)


class LoggerBase:
    def __init__(self):
        self.config = self.load_config()
        self.formatter = JSONFormatter(datefmt=self.config.get('logger_datefmt', '%Y-%m-%d %H:%M:%S'))
        self.log_queue = queue.Queue(-1)
        self.queue_handler = logging.handlers.QueueHandler(self.log_queue)

    def load_config(self):
        with open('config.yaml', 'r') as file:
            return yaml.safe_load(file)['logger']


class ConsoleLogger(LoggerBase):
    def setup(self):
        ch = logging.StreamHandler()
        ch.setFormatter(self.formatter)
        ch.setLevel(getattr(logging, self.config['console'].get('logger_console_handler_level', 'INFO')))
        return ch



class FileLogger(LoggerBase):
    def setup(self):
        rf_handler = logging.handlers.RotatingFileHandler(
            self.config['file'].get('logger_file_name', 'app.log'),
            maxBytes=self.config['file'].get('logger_max_bytes', 10485760),
            backupCount=self.config['file'].get('logger_backup_count', 3)
        )
        rf_handler.setLevel(getattr(logging, self.config['file'].get('logger_file_handler_level', 'DEBUG')))
        rf_handler.setFormatter(self.formatter)
        return rf_handler


class RemoteLogger(LoggerBase):
    def setup(self):
        remote_level = self.config['remote'].get('logger_remote_handler_level', 'INFO')
        if remote_level != 'NONE' and self.config['remote'].get('logger_remote_logging_url'):
            parsed_url = urlparse(self.config['remote'].get('logger_remote_logging_url'))
            http_handler = logging.handlers.HTTPHandler(
                host=f"{parsed_url.hostname}:{parsed_url.port or '80'}",  # Use default HTTP port if not specified
                url=parsed_url.path or "/log",  # Use the provided path or default to "/log"
                method="POST",
            )
            http_handler.setLevel(getattr(logging, remote_level))
            http_handler.setFormatter(self.formatter)
            return http_handler
        return None


class LoggerFactory:
    @staticmethod
    def setup():
        base_logger = LoggerBase()
        config = base_logger.load_config()
        root_logger = logging.getLogger(config.get('logger_name', 'MarketMiner'))
        root_logger.setLevel(logging.DEBUG)
        listeners = []

        # Console
        if base_logger.config['console'].get('async', False):
            console_logger = ConsoleLogger().setup()
            listener = QueueListener(base_logger.log_queue, console_logger)
            listeners.append(listener)
            root_logger.addHandler(base_logger.queue_handler)
        else:
            root_logger.addHandler(ConsoleLogger().setup())

        # File
        if base_logger.config['file'].get('async', False):
            file_logger = FileLogger().setup()
            listener = QueueListener(base_logger.log_queue, file_logger)
            listeners.append(listener)
            root_logger.addHandler(base_logger.queue_handler)
        else:
            root_logger.addHandler(FileLogger().setup())

        # Remote
        remote_logger = RemoteLogger().setup()
        if remote_logger:
            if base_logger.config['remote'].get('async', False):
                listener = QueueListener(base_logger.log_queue, remote_logger)
                listeners.append(listener)
                root_logger.addHandler(base_logger.queue_handler)
            else:
                root_logger.addHandler(remote_logger)

        # Start all listeners
        for listener in listeners:
            listener.start()

        return root_logger, listeners


# Initialization
app_logger, log_listeners = LoggerFactory.setup()
