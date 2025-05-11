# src/core/logging_setup.py
import logging
import os
import sys
import json # Added for JsonFormatter
import traceback # Added for JsonFormatter
from typing import Optional, Dict, Any # Added for JsonFormatter type hints
from src.config.models import GlobalConfig # To get logging config

class JsonFormatter(logging.Formatter):
    """
    Custom formatter to output log records as JSON strings.
    Handles exc_info automatically to include traceback.
    """
    def format(self, record: logging.LogRecord) -> str:
        log_record: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "funcName": record.funcName,
            "lineno": record.lineno,
            "process": record.process,
            "thread": record.threadName,
        }

        if record.exc_info:
            exc_type, exc_value, exc_tb = record.exc_info
            log_record['exception_type'] = str(exc_type.__name__) if exc_type else None
            log_record['exception_message'] = str(exc_value) if exc_value else None
            log_record['traceback'] = traceback.format_exception(exc_type, exc_value, exc_tb) if exc_tb else None
        else:
            log_record['exception_type'] = None
            log_record['exception_message'] = None
            log_record['traceback'] = None
        
        # Include any extra fields passed to the logger
        if hasattr(record, '__dict__'):
            for key, value in record.__dict__.items():
                if key not in log_record and key not in ['args', 'asctime', 'created', 'exc_info', 'exc_text', 'filename', 'levelname', 'levelno', 'msecs', 'msg', 'pathname', 'processName', 'relativeCreated', 'stack_info', 'thread']: # standard, already handled or internal
                    log_record[key] = value

        return json.dumps(log_record, ensure_ascii=False, default=str) # Add default=str for non-serializable

def setup_logging(config: GlobalConfig):
    """
    Configures logging based on settings in GlobalConfig.
    Sets up a general logger (console and/or file) and a dedicated JSON error logger (file).
    """
    log_level_str = config.log_level
    log_level_numeric = getattr(logging, log_level_str.upper(), logging.INFO)
    
    root_logger = logging.getLogger()
    # Clear any existing handlers from the root logger to avoid duplicates if this is called multiple times
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
    
    root_logger.setLevel(log_level_numeric) # Set level on root logger
    
    # General Console Handler (always add)
    console_handler = logging.StreamHandler(sys.stdout) # Use stdout for general logs
    console_handler.setFormatter(logging.Formatter(config.log_format))
    console_handler.setLevel(log_level_numeric) # Console mirrors root logger level or can be set differently
    root_logger.addHandler(console_handler)
    
    # General File Handler (if path is provided for general logs)
    if config.log_file_path:
        try:
            log_dir = os.path.dirname(config.log_file_path)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir)
            general_file_handler = logging.FileHandler(config.log_file_path, mode='a')
            general_file_handler.setFormatter(logging.Formatter(config.log_format))
            general_file_handler.setLevel(log_level_numeric) 
            root_logger.addHandler(general_file_handler)
            log_file_msg = config.log_file_path
        except Exception as e:
            print(f"Error setting up general file logger at '{config.log_file_path}': {e}. General logs to console only.", file=sys.stderr)
            log_file_msg = "Console Only (general file log error)"
    else:
        log_file_msg = "Console Only (general file log not configured)"

    # Dedicated JSON Error File Handler (if path is provided for error logs)
    error_log_file_msg = "Not configured"
    if config.error_log_file_path:
        try:
            error_log_dir = os.path.dirname(config.error_log_file_path)
            if error_log_dir and not os.path.exists(error_log_dir):
                os.makedirs(error_log_dir)
            error_file_handler = logging.FileHandler(config.error_log_file_path, mode='a')
            # JsonFormatter will use its own structure; fmt from config is mainly for datefmt via base Formatter
            # Pass the config.error_log_format which might just be a simple string or a JSON string for datefmt extraction.
            # The base Formatter.__init__ (which JsonFormatter inherits) handles datefmt from the fmt string.
            json_formatter_datefmt_source = config.error_log_format
            try:
                # If error_log_format is a JSON string, try to extract datefmt if specified there.
                # This is a bit of a hack. A dedicated datefmt field in config would be cleaner.
                json_fmt_dict = json.loads(config.error_log_format)
                if isinstance(json_fmt_dict, dict) and 'datefmt' in json_fmt_dict and isinstance(json_fmt_dict['datefmt'], str):
                    json_formatter_datefmt_source = json_fmt_dict['datefmt'] 
            except (json.JSONDecodeError, TypeError):
                pass # Use original error_log_format string, Formatter will try to parse datefmt from it.

            error_file_handler.setFormatter(JsonFormatter(fmt=json_formatter_datefmt_source)) # Pass potential datefmt source
            error_file_handler.setLevel(logging.ERROR) # This handler only processes ERROR and CRITICAL
            root_logger.addHandler(error_file_handler)
            error_log_file_msg = config.error_log_file_path
        except Exception as e:
            print(f"Error setting up JSON error file logger at '{config.error_log_file_path}': {e}. JSON error logs may not be written.", file=sys.stderr)
            error_log_file_msg = f"Error ({e})"

    # Initial log message to confirm setup
    # Get a logger instance for this module to log the setup confirmation
    setup_logger = logging.getLogger(__name__)
    setup_logger.info(f"Logging configured. Level: {log_level_str}. General log: {log_file_msg}. Error log (JSONL): {error_log_file_msg}.")

if __name__ == '__main__':
    # Example Usage:
    print("--- Testing logging_setup --- ")
    
    class MockGlobalConfig:
        def __init__(self, level, path=None, fmt=None, error_path=None, error_fmt=None):
            self.log_level = level
            self.log_file_path = path
            self.log_format = fmt if fmt else '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            self.error_log_file_path = error_path
            # A sample JSON format for testing the JsonFormatter directly
            self.error_log_format = error_fmt if error_fmt else '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "name": "%(name)s", "message": "%(message)s"}'

    # Ensure temp log directory exists for tests
    if not os.path.exists("./temp_logs"): os.makedirs("./temp_logs")

    # Test 1: Basic INFO level to console, no file logs
    print("\nTest 1: INFO to console only")
    cfg1 = MockGlobalConfig(level='INFO')
    setup_logging(cfg1) # type: ignore
    logging.debug("This is a DEBUG message (Test 1) - should not appear")
    logging.info("This is an INFO message (Test 1) - should appear on console")
    logging.warning("This is a WARNING message (Test 1) - should appear on console")
    try:
        raise ValueError("Test exception for Test 1")
    except ValueError:
        logging.error("This is an ERROR message (Test 1) - should appear on console", exc_info=True)

    # Test 2: DEBUG level to a general file and console, plus ERROR to JSONL file
    print("\nTest 2: DEBUG to general file & console, ERROR to JSONL file")
    general_log_file = "./temp_logs/general_test.log"
    error_log_file = "./temp_logs/error_test.jsonl"
    
    # More complex error format similar to what's in verification_config.yaml
    detailed_error_fmt = '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger_name": "%(name)s", "module": "%(module)s", "funcName": "%(funcName)s", "lineno": "%(lineno)s", "message": "%(message)s", "exception_type": "%(exc_info_type)s", "exception_message": "%(exc_info_message)s", "traceback": "%(exc_info_traceback)s"}'

    cfg2 = MockGlobalConfig(level='DEBUG', 
                            path=general_log_file, 
                            fmt='%(levelname)s - %(name)s: %(message)s',
                            error_path=error_log_file,
                            error_fmt=detailed_error_fmt)
    setup_logging(cfg2) # type: ignore
    
    logging.debug("This is a DEBUG message (Test 2) - should appear in general file & console")
    logging.info("This is an INFO message (Test 2) - should appear in general file & console")
    logging.warning("This is a WARNING message (Test 2) - should appear in general file & console")
    try:
        x = 1 / 0
    except ZeroDivisionError:
        logging.error("This is an ERROR message (Test 2) for ZeroDivisionError - should appear in all three (console, general file, error file as JSON)", exc_info=True)
    
    logging.critical("This is a CRITICAL message (Test 2) - should also go to error file as JSON and others")

    if os.path.exists(general_log_file):
        print(f"\nGeneral log file created: {general_log_file}. Contents:")
        with open(general_log_file, 'r') as f_read:
            print(f_read.read())
        # os.remove(general_log_file)
    else:
        print(f"ERROR: General log file {general_log_file} was not created.")

    if os.path.exists(error_log_file):
        print(f"\nError log file created: {error_log_file}. Contents (should be JSONL):")
        with open(error_log_file, 'r') as f_read:
            for line in f_read:
                print(line.strip()) # Print each JSON line
                try:
                    json.loads(line) # Validate if it's proper JSON
                    print("  \\-> Valid JSON line.")
                except json.JSONDecodeError as je:
                    print(f"  \\-> INVALID JSON: {je}")
        # os.remove(error_log_file)
    else:
        print(f"ERROR: Error log file {error_log_file} was not created.")
    
    print("\nLogging setup tests finished. Check temp_logs directory.") 