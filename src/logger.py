import logging
import os
import sys
import json
import re
import time
import datetime
from typing import Optional, Dict, Any, List, Union, Set, Pattern
import logging.config
import logging.handlers
from pathlib import Path

# Default log directory
DEFAULT_LOG_DIR = 'logs'

# Create logs directory if it doesn't exist
os.makedirs(DEFAULT_LOG_DIR, exist_ok=True)

# Define log levels and their names for easier reference
LOG_LEVELS = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL,
    'NONE': logging.CRITICAL + 10  # Level to disable logging
}

# ANSI color codes for console output
COLORS = {
    'DEBUG': '\033[36m',     # Cyan
    'INFO': '\033[32m',      # Green
    'WARNING': '\033[33m',   # Yellow
    'ERROR': '\033[31m',     # Red
    'CRITICAL': '\033[35m',  # Magenta
    'RESET': '\033[0m'       # Reset to default
}

# Default configuration
DEFAULT_CONFIG = {
    'log_dir': DEFAULT_LOG_DIR,
    'default_level': 'INFO',
    'module_levels': {},
    'enable_console': True,
    'enable_file': False,
    'default_file_name': 'app.log',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
    'json_format': False,     # Enable JSON formatting
    'colored_output': True,   # Enable colored console output
    'filters': [],            # Log output filters (regex patterns)
    'excluded_modules': []    # Module name patterns to exclude from logging
}

# Store logger configuration
_config = DEFAULT_CONFIG.copy()
# Track configured loggers
_configured_loggers: Set[str] = set()
# Track active filters
_active_filters: List[Pattern] = []
# Track excluded modules
_excluded_modules: List[Pattern] = []

# Constants for log rotation and archiving
DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10 MB per log file by default
DEFAULT_BACKUP_COUNT = 5              # Keep 5 backup files by default
DEFAULT_LOG_RETENTION_DAYS = 30       # Keep logs for 30 days by default

# Global log level
_log_level = logging.INFO

# Cache for loggers
_loggers: Dict[str, logging.Logger] = {}

# Define log directories
LOG_DIR = "logs"
NODE_LOG_DIR = os.path.join(LOG_DIR, "nodes")
ERROR_LOG_DIR = os.path.join(LOG_DIR, "errors")
PERFORMANCE_LOG_DIR = os.path.join(LOG_DIR, "performance")
STATE_LOG_DIR = os.path.join(LOG_DIR, "states")

# Default log file size and count
MAX_LOG_SIZE = 5 * 1024 * 1024  # 5 MB
BACKUP_COUNT = 5

# Make sure log directories exist
def _ensure_log_directories():
    """Create log directories if they don't exist."""
    for directory in [LOG_DIR, NODE_LOG_DIR, ERROR_LOG_DIR, PERFORMANCE_LOG_DIR, STATE_LOG_DIR]:
        os.makedirs(directory, exist_ok=True)

_ensure_log_directories()

# Formatter classes must be defined before they are used
class ColorFormatter(logging.Formatter):
    """Formatter that adds colors to console output based on log level."""
    
    def __init__(self, fmt=None, datefmt=None, style='%', use_colors=True):
        """Initialize the color formatter.
        
        Args:
            fmt: Format string for the log message
            datefmt: Format string for the date
            style: Style of the format string
            use_colors: Whether to use colors
        """
        super().__init__(fmt, datefmt, style)
        self.use_colors = use_colors and sys.stdout.isatty()  # Only use colors if stdout is a terminal
    
    def format(self, record):
        """Format the record with colors based on level."""
        # Get the original formatted message
        formatted_message = super().format(record)
        
        if not self.use_colors:
            return formatted_message
            
        # Determine the color based on log level
        level_name = record.levelname
        color = COLORS.get(level_name, COLORS['RESET'])
        
        # Apply color to the level name in the formatted message
        # This assumes the level name appears in the message
        if level_name in formatted_message:
            colored_level = f"{color}{level_name}{COLORS['RESET']}"
            formatted_message = formatted_message.replace(level_name, colored_level)
            
        return formatted_message

class JSONFormatter(logging.Formatter):
    """Formatter that outputs log records as JSON objects."""
    
    def __init__(self, include_stack_info=False):
        """Initialize the JSON formatter.
        
        Args:
            include_stack_info: Whether to include stack info in the output
        """
        super().__init__()
        self.include_stack_info = include_stack_info
    
    def format(self, record):
        """Format the record as a JSON object."""
        # Create a dictionary of log record attributes
        log_data = {
            'timestamp': datetime.datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'level_num': record.levelno,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'process_id': record.process,
            'thread_id': record.thread
        }
        
        # Add exception info if available
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': self.formatException(record.exc_info)
            }
        
        # Add stack info if requested and available
        if self.include_stack_info and record.stack_info:
            log_data['stack_info'] = record.stack_info
            
        # Add custom fields from record.__dict__
        for key, value in record.__dict__.items():
            if key not in log_data and not key.startswith('_') and isinstance(value, (str, int, float, bool, type(None))):
                log_data[key] = value
                
        return json.dumps(log_data)

# Log formatters
STANDARD_FORMAT = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

DETAILED_FORMAT = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Replace the incorrect JSON_FORMAT definition with a proper instance of JSONFormatter
JSON_FORMAT = JSONFormatter()

class LogFilter(logging.Filter):
    """Filter that only allows log records matching a specific pattern."""
    
    def __init__(self, pattern: str):
        """Initialize the filter with a regex pattern.
        
        Args:
            pattern: Regular expression pattern to match against log messages
        """
        super().__init__()
        self.pattern = re.compile(pattern)
    
    def filter(self, record):
        """Check if the record should be logged based on pattern."""
        return bool(self.pattern.search(record.getMessage()))

class ModuleFilter(logging.Filter):
    """Filter that excludes logs from specific modules."""
    
    def __init__(self, excluded_patterns: List[str]):
        """Initialize the filter with module patterns to exclude.
        
        Args:
            excluded_patterns: List of regex patterns for module names to exclude
        """
        super().__init__()
        self.excluded_patterns = [re.compile(pattern) for pattern in excluded_patterns]
    
    def filter(self, record):
        """Check if the record should be logged based on module exclusion."""
        if not self.excluded_patterns:
            return True
            
        # Check if the module name matches any exclusion pattern
        for pattern in self.excluded_patterns:
            if pattern.search(record.name):
                return False
                
        return True

def load_config_from_file(config_path: str) -> bool:
    """Load logger configuration from a JSON file.
    
    Args:
        config_path (str): Path to the configuration file
        
    Returns:
        bool: True if configuration was loaded successfully, False otherwise
    """
    global _config, _active_filters, _excluded_modules
    
    try:
        if not os.path.exists(config_path):
            print(f"Logger configuration file not found: {config_path}")
            return False
            
        with open(config_path, 'r') as f:
            file_config = json.load(f)
            
        # Merge with default config, keeping default values for missing keys
        new_config = DEFAULT_CONFIG.copy()
        new_config.update(file_config)
        _config = new_config
        
        # Compile any filter patterns
        if 'filters' in _config and _config['filters']:
            _active_filters = [re.compile(pattern) for pattern in _config['filters']]
            
        # Compile excluded module patterns
        if 'excluded_modules' in _config and _config['excluded_modules']:
            _excluded_modules = [re.compile(pattern) for pattern in _config['excluded_modules']]
        
        print(f"Loaded logger configuration from {config_path}")
        
        # Apply new configuration to existing loggers
        _reconfigure_existing_loggers()
        
        return True
    except Exception as e:
        print(f"Error loading logger configuration: {e}")
        return False

def load_config_from_env() -> None:
    """Load logger configuration from environment variables."""
    global _config, _active_filters, _excluded_modules
    
    # Check for environment variables and update config
    if 'LOG_LEVEL' in os.environ:
        level = os.environ['LOG_LEVEL'].upper()
        if level in LOG_LEVELS:
            _config['default_level'] = level
            print(f"Set default log level from environment: {level}")
    
    # Support for module-specific log levels via environment
    # Format: LOG_LEVEL_MODULENAME=LEVEL (e.g. LOG_LEVEL_CORE=DEBUG)
    module_levels = {}
    for var, value in os.environ.items():
        if var.startswith('LOG_LEVEL_') and var != 'LOG_LEVEL':
            module_name = var[10:].lower().replace('_', '.')
            level = value.upper()
            if level in LOG_LEVELS:
                module_levels[module_name] = level
                print(f"Set {module_name} log level from environment: {level}")
    
    if module_levels:
        _config['module_levels'].update(module_levels)
    
    # Other configuration options
    if 'LOG_DIR' in os.environ:
        _config['log_dir'] = os.environ['LOG_DIR']
        # Ensure the directory exists
        os.makedirs(_config['log_dir'], exist_ok=True)
    
    if 'LOG_FILE' in os.environ:
        _config['default_file_name'] = os.environ['LOG_FILE']
        _config['enable_file'] = True
    
    # Console logging can be disabled
    if 'LOG_CONSOLE' in os.environ:
        _config['enable_console'] = os.environ['LOG_CONSOLE'].lower() != 'false'
    
    # File logging can be enabled/disabled
    if 'LOG_TO_FILE' in os.environ:
        _config['enable_file'] = os.environ['LOG_TO_FILE'].lower() == 'true'
        
    # JSON formatting can be enabled/disabled
    if 'LOG_JSON' in os.environ:
        _config['json_format'] = os.environ['LOG_JSON'].lower() == 'true'
        
    # Colored output can be enabled/disabled
    if 'LOG_COLOR' in os.environ:
        _config['colored_output'] = os.environ['LOG_COLOR'].lower() != 'false'
        
    # Filter patterns can be set
    if 'LOG_FILTERS' in os.environ:
        filter_patterns = os.environ['LOG_FILTERS'].split(',')
        _config['filters'] = filter_patterns
        _active_filters = [re.compile(pattern.strip()) for pattern in filter_patterns if pattern.strip()]
        
    # Excluded modules can be set
    if 'LOG_EXCLUDE_MODULES' in os.environ:
        exclude_patterns = os.environ['LOG_EXCLUDE_MODULES'].split(',')
        _config['excluded_modules'] = exclude_patterns
        _excluded_modules = [re.compile(pattern.strip()) for pattern in exclude_patterns if pattern.strip()]
        
    # Apply new configuration to existing loggers
    _reconfigure_existing_loggers()

def _reconfigure_existing_loggers() -> None:
    """Reconfigure existing loggers with new configuration."""
    for logger_name in _configured_loggers:
        logger = logging.getLogger(logger_name)
        
        # Set level based on module-specific configuration or default
        level_name = _get_module_level(logger_name)
        logger.setLevel(LOG_LEVELS[level_name])
        
        # Update handler levels and formatters
        for handler in logger.handlers:
            handler.setLevel(LOG_LEVELS[level_name])
            
            # Update formatter based on configuration
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                if _config['json_format']:
                    handler.setFormatter(JSONFormatter())
                elif _config['colored_output']:
                    handler.setFormatter(ColorFormatter(_config['format']))
                else:
                    handler.setFormatter(logging.Formatter(_config['format']))
            elif isinstance(handler, logging.FileHandler):
                if _config['json_format']:
                    handler.setFormatter(JSONFormatter())
                else:
                    handler.setFormatter(logging.Formatter(_config['format']))
            
            # Apply filters if defined
            handler.filters.clear()
            
            # Add message pattern filters
            for pattern in _active_filters:
                handler.addFilter(LogFilter(pattern.pattern))
                
            # Add module exclusion filter
            if _excluded_modules:
                handler.addFilter(ModuleFilter([p.pattern for p in _excluded_modules]))

def get_log_level_name(level: int) -> str:
    """Convert a numeric log level to its name.
    
    Args:
        level (int): Numeric logging level
        
    Returns:
        str: Level name ('DEBUG', 'INFO', etc.)
    """
    for name, value in LOG_LEVELS.items():
        if value == level:
            return name
    return 'UNKNOWN'

def get_log_level(level_name: str) -> int:
    """Convert a log level name to its numeric value.
    
    Args:
        level_name (str): Level name ('DEBUG', 'INFO', etc.)
        
    Returns:
        int: Numeric logging level
    """
    return LOG_LEVELS.get(level_name.upper(), logging.INFO)

def _get_module_level(module_name: str) -> str:
    """Get the configured log level for a module.
    
    Args:
        module_name (str): Module name
        
    Returns:
        str: Log level name
    """
    # Check if there's a specific configuration for this module or its parents
    parts = module_name.split('.')
    
    # Try increasingly specific module paths
    for i in range(len(parts), 0, -1):
        prefix = '.'.join(parts[:i])
        if prefix in _config['module_levels']:
            return _config['module_levels'][prefix]
    
    # Fall back to default level
    return _config['default_level']

def setup_logger(
    name: str, 
    level: Optional[Union[int, str]] = None,
    console: bool = True,
    file: bool = True,
    file_level: Optional[Union[int, str]] = None,
    json_format: bool = False,
    log_dir: Optional[str] = None
) -> logging.Logger:
    """
    Set up a logger with console and/or file handlers.
    
    Args:
        name: Name of the logger
        level: Log level for console output (defaults to global level)
        console: Whether to log to console
        file: Whether to log to file
        file_level: Log level for file output (defaults to level)
        json_format: Whether to use JSON format for file logs
        log_dir: Custom log directory
        
    Returns:
        Configured logger
    """
    # Check if logger already exists
    if name in _loggers:
        return _loggers[name]
    
    # Use global log level if not specified
    if level is None:
        level = _log_level
        
    # File level defaults to same as console level
    if file_level is None:
        file_level = level
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # Set to lowest possible level
    logger.propagate = False  # Don't propagate to parent loggers
    
    # Add console handler if requested
    if console and not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(STANDARD_FORMAT)
        logger.addHandler(console_handler)
    
    # Add file handler if requested
    if file:
        # Determine log directory based on logger name
        if log_dir is None:
            if "node" in name.lower():
                log_dir = NODE_LOG_DIR
            elif "error" in name.lower():
                log_dir = ERROR_LOG_DIR
            elif "performance" in name.lower() or "profile" in name.lower():
                log_dir = PERFORMANCE_LOG_DIR
            elif "state" in name.lower():
                log_dir = STATE_LOG_DIR
            else:
                log_dir = LOG_DIR
        
        # Ensure directory exists
        os.makedirs(log_dir, exist_ok=True)
        
        # Create file path
        log_file = os.path.join(log_dir, f"{name}.log")
        
        # Create rotating file handler
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=MAX_LOG_SIZE,
            backupCount=BACKUP_COUNT
        )
        file_handler.setLevel(file_level)
        
        # Set formatter
        if json_format:
            file_handler.setFormatter(JSONFormatter())
        else:
            file_handler.setFormatter(DETAILED_FORMAT)
            
        logger.addHandler(file_handler)
    
    # Cache and return
    _loggers[name] = logger
    return logger

def set_log_level(level: Union[int, str]):
    """Set the global log level for all loggers."""
    global _log_level
    
    # Convert string to int if needed
    if isinstance(level, str):
        level = getattr(logging, level.upper())
    
    _log_level = level
    
    # Update existing loggers
    for logger in _loggers.values():
        # Only update console handlers
        for handler in logger.handlers:
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                handler.setLevel(level)

def get_log_level() -> int:
    """Get the current global log level."""
    return _log_level

def add_file_handler(
    logger_name: str, 
    file_path: str, 
    level: Optional[Union[int, str]] = None,
    json_format: bool = False
) -> None:
    """
    Add an additional file handler to an existing logger.
    
    Args:
        logger_name: Name of the logger to modify
        file_path: Path to the log file
        level: Log level for this handler
        json_format: Whether to use JSON format
    """
    if logger_name not in _loggers:
        raise ValueError(f"Logger {logger_name} not found")
    
    logger = _loggers[logger_name]
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    # Use global level if not specified
    if level is None:
        level = _log_level
    
    # Create file handler
    file_handler = logging.handlers.RotatingFileHandler(
        file_path,
        maxBytes=MAX_LOG_SIZE,
        backupCount=BACKUP_COUNT
    )
    file_handler.setLevel(level)
    
    # Set formatter
    if json_format:
        file_handler.setFormatter(JSONFormatter())
    else:
        file_handler.setFormatter(DETAILED_FORMAT)
        
    logger.addHandler(file_handler)

def create_session_log_dir(session_id: str) -> str:
    """
    Create a directory for a specific logging session.
    
    Args:
        session_id: Unique session identifier
        
    Returns:
        Path to the created directory
    """
    session_dir = os.path.join(LOG_DIR, "sessions", session_id)
    os.makedirs(session_dir, exist_ok=True)
    return session_dir

def setup_file_logger(log_file: str, json_format: bool = None) -> logging.FileHandler:
    """Set up a file handler for logging.
    
    Args:
        log_file (str): Log file name to write to (inside logs directory)
        json_format (bool, optional): Whether to use JSON formatting. If None, uses config.
        
    Returns:
        logging.FileHandler: Configured file handler
    """
    # Ensure logs directory exists
    os.makedirs(_config['log_dir'], exist_ok=True)
    
    # Construct full path if not already provided
    log_path = log_file if os.path.dirname(log_file) else os.path.join(_config['log_dir'], log_file)
    
    # Create file handler
    file_handler = logging.FileHandler(log_path)
    
    # Use provided format option or fall back to config
    use_json = json_format if json_format is not None else _config['json_format']
    
    # Apply the appropriate formatter
    if use_json:
        file_formatter = JSONFormatter()
    else:
        file_formatter = logging.Formatter(_config['format'])
        
    file_handler.setFormatter(file_formatter)
    
    # Apply filters if defined
    for pattern in _active_filters:
        file_handler.addFilter(LogFilter(pattern.pattern))
        
    # Add module exclusion filter
    if _excluded_modules:
        file_handler.addFilter(ModuleFilter([p.pattern for p in _excluded_modules]))
    
    return file_handler

def setup_shared_file_logger(log_file: str, level=None) -> None:
    """Set up a shared file logger that logs all messages to a file.
    
    Args:
        log_file (str): Path to the log file
        level (str/int, optional): Log level for this handler. Defaults to None (use INFO).
    """
    # Check if log file is an absolute path
    if not os.path.isabs(log_file):
        log_file = os.path.join(_config['log_dir'], log_file)
    
    # Determine log level
    if level is None:
        level = logging.INFO
    elif isinstance(level, str):
        level = get_log_level(level)
    
    # Create the log directory if it doesn't exist
    log_dir = os.path.dirname(log_file)
    os.makedirs(log_dir, exist_ok=True)
    
    # Create a rotating file handler for better log management
    handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=DEFAULT_MAX_BYTES,
        backupCount=DEFAULT_BACKUP_COUNT
    )
    handler.setLevel(level)
    
    # Set formatter
    if _config.get('json_format', False):
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(logging.Formatter(_config.get('format', DEFAULT_CONFIG['format'])))
    
    # Add the handler to the root logger
    logging.getLogger().addHandler(handler)
    
    print(f"Shared file logger set up at {log_file}")
    
    return handler

def set_log_format(json_format: bool) -> None:
    """Set whether to use JSON formatting for logs.
    
    Args:
        json_format (bool): Whether to use JSON formatting
    """
    global _config
    
    _config['json_format'] = json_format
    
    print(f"Set log format to {'JSON' if json_format else 'text'}")
    
    # Apply new configuration to existing loggers
    _reconfigure_existing_loggers()

def set_colored_output(enabled: bool) -> None:
    """Set whether to use colored output for console logs.
    
    Args:
        enabled (bool): Whether to use colored output
    """
    global _config
    
    _config['colored_output'] = enabled
    
    print(f"Set colored output to {'enabled' if enabled else 'disabled'}")
    
    # Apply new configuration to existing loggers
    _reconfigure_existing_loggers()

def add_log_filter(pattern: str) -> None:
    """Add a filter pattern to log messages.
    
    Args:
        pattern (str): Regular expression pattern to match against log messages
    """
    global _config, _active_filters
    
    try:
        # Compile the pattern to validate it
        compiled_pattern = re.compile(pattern)
        
        # Add to active filters
        _active_filters.append(compiled_pattern)
        
        # Update config
        if 'filters' not in _config:
            _config['filters'] = []
        
        _config['filters'].append(pattern)
        
        print(f"Added log filter pattern: {pattern}")
        
        # Apply to existing loggers
        _reconfigure_existing_loggers()
    except re.error as e:
        print(f"Invalid regex pattern: {str(e)}")

def remove_log_filter(pattern: str) -> bool:
    """Remove a filter pattern from log messages.
    
    Args:
        pattern (str): Pattern to remove
        
    Returns:
        bool: True if pattern was removed, False if not found
    """
    global _config, _active_filters
    
    # Remove from config
    if 'filters' in _config and pattern in _config['filters']:
        _config['filters'].remove(pattern)
    else:
        print(f"Filter pattern not found: {pattern}")
        return False
    
    # Remove from active filters
    for i, compiled_pattern in enumerate(_active_filters):
        if compiled_pattern.pattern == pattern:
            _active_filters.pop(i)
            print(f"Removed log filter pattern: {pattern}")
            
            # Apply to existing loggers
            _reconfigure_existing_loggers()
            return True
    
    return False

def clear_log_filters() -> None:
    """Clear all log filters."""
    global _config, _active_filters
    
    _config['filters'] = []
    _active_filters = []
    
    print("Cleared all log filters")
    
    # Apply to existing loggers
    _reconfigure_existing_loggers()

def exclude_module(module_pattern: str) -> None:
    """Exclude a module from logging based on a pattern.
    
    Args:
        module_pattern (str): Regular expression pattern to match against module names
    """
    global _config, _excluded_modules
    
    try:
        # Compile the pattern to validate it
        compiled_pattern = re.compile(module_pattern)
        
        # Add to excluded modules
        _excluded_modules.append(compiled_pattern)
        
        # Update config
        if 'excluded_modules' not in _config:
            _config['excluded_modules'] = []
        
        _config['excluded_modules'].append(module_pattern)
        
        print(f"Excluded module pattern: {module_pattern}")
        
        # Apply to existing loggers
        _reconfigure_existing_loggers()
    except re.error as e:
        print(f"Invalid regex pattern: {str(e)}")

def include_module(module_pattern: str) -> bool:
    """Remove a module exclusion pattern.
    
    Args:
        module_pattern (str): Pattern to remove
        
    Returns:
        bool: True if pattern was removed, False if not found
    """
    global _config, _excluded_modules
    
    # Remove from config
    if 'excluded_modules' in _config and module_pattern in _config['excluded_modules']:
        _config['excluded_modules'].remove(module_pattern)
    else:
        print(f"Module exclusion pattern not found: {module_pattern}")
        return False
    
    # Remove from excluded modules
    for i, compiled_pattern in enumerate(_excluded_modules):
        if compiled_pattern.pattern == module_pattern:
            _excluded_modules.pop(i)
            print(f"Removed module exclusion pattern: {module_pattern}")
            
            # Apply to existing loggers
            _reconfigure_existing_loggers()
            return True
    
    return False

def clear_module_exclusions() -> None:
    """Clear all module exclusion patterns."""
    global _config, _excluded_modules
    
    _config['excluded_modules'] = []
    _excluded_modules = []
    
    print("Cleared all module exclusions")
    
    # Apply to existing loggers
    _reconfigure_existing_loggers()

# Initialize from environment variables
load_config_from_env()

class LogManager:
    """Centralized log management system that handles rotation, archiving, and aggregation."""
    
    def __init__(self, base_log_dir=None):
        """Initialize the log manager.
        
        Args:
            base_log_dir (str, optional): Base directory for all logs. Defaults to DEFAULT_LOG_DIR.
        """
        self.base_log_dir = base_log_dir or DEFAULT_LOG_DIR
        self.session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.handlers = {}
        self.session_dir = None
        self.create_session_directory()
        
    def create_session_directory(self):
        """Create a timestamped directory for the current logging session."""
        # Create directory structure: logs/YYYYMMDD_HHMMSS/
        # Make self.session_dir an absolute path
        self.session_dir = os.path.abspath(os.path.join(self.base_log_dir, self.session_id))
        os.makedirs(self.session_dir, exist_ok=True)
        
        # Create subdirectories for different log types
        self.detailed_dir = os.path.join(self.session_dir, 'detailed')
        self.summary_dir = os.path.join(self.session_dir, 'summary')
        self.error_dir = os.path.join(self.session_dir, 'errors')
        
        os.makedirs(self.detailed_dir, exist_ok=True)
        os.makedirs(self.summary_dir, exist_ok=True)
        os.makedirs(self.error_dir, exist_ok=True)
        
        return self.session_dir
    
    def get_rotating_file_handler(self, log_file, max_bytes=DEFAULT_MAX_BYTES, 
                                 backup_count=DEFAULT_BACKUP_COUNT, 
                                 level=logging.INFO, 
                                 formatter=None):
        """Create a rotating file handler for automatic log rotation.
        
        Args:
            log_file (str): Name or path to the log file
            max_bytes (int): Maximum size in bytes before rotating
            backup_count (int): Number of backup files to keep
            level (int): Logging level for this handler
            formatter: Log formatter to use
            
        Returns:
            logging.handlers.RotatingFileHandler: Configured handler
        """
        if not os.path.isabs(log_file):
            # If not an absolute path, use the session directory
            log_file = os.path.join(self.session_dir, log_file)
            
        # Create the handler
        handler = logging.handlers.RotatingFileHandler(
            log_file, 
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        handler.setLevel(level)
        
        # Set formatter if provided, otherwise use a default one
        if formatter:
            handler.setFormatter(formatter)
        else:
            # Choose appropriate formatter based on config
            if _config.get('json_format', False):
                handler.setFormatter(JSONFormatter())
            else:
                handler.setFormatter(logging.Formatter(_config.get('format', DEFAULT_CONFIG['format'])))
        
        return handler
    
    def create_component_logger(self, component_name, log_level=None, 
                              detailed=True, summary=True, errors=True,
                              json_format=None):
        """Create a logger with appropriate handlers for a component.
        
        Args:
            component_name (str): Name of the component (used as logger name)
            log_level (str, optional): Log level for this component. Defaults to None (use config).
            detailed (bool): Whether to create a detailed log file. Defaults to True.
            summary (bool): Whether to create a summary log file. Defaults to True.
            errors (bool): Whether to create an error-only log file. Defaults to True.
            json_format (bool, optional): Whether to use JSON formatting. Defaults to None (use config).
            
        Returns:
            logging.Logger: Configured logger for the component
        """
        # First create/get the logger
        logger = setup_logger(component_name, level=log_level, 
                            json_format=json_format)
        
        # Create handlers based on requested configuration
        handlers = []
        
        if detailed:
            file_path = os.path.join(self.detailed_dir, f"{component_name.replace('.', '_')}.log")
            detailed_handler = self.get_rotating_file_handler(
                file_path, 
                level=logging.DEBUG if log_level is None else get_log_level(log_level)
            )
            logger.addHandler(detailed_handler)
            handlers.append(detailed_handler)
        
        if summary:
            file_path = os.path.join(self.summary_dir, f"{component_name.replace('.', '_')}_summary.log")
            summary_handler = self.get_rotating_file_handler(
                file_path, 
                level=logging.INFO
            )
            logger.addHandler(summary_handler)
            handlers.append(summary_handler)
        
        if errors:
            file_path = os.path.join(self.error_dir, f"{component_name.replace('.', '_')}_errors.log")
            error_handler = self.get_rotating_file_handler(
                file_path, 
                level=logging.ERROR
            )
            logger.addHandler(error_handler)
            handlers.append(error_handler)
        
        # Store handlers for later management
        self.handlers[component_name] = handlers
        
        return logger
    
    def add_shared_file_logger(self, log_file, level=None, formatter=None, max_bytes=DEFAULT_MAX_BYTES, backup_count=DEFAULT_BACKUP_COUNT):
        """Create a shared file logger that logs all configured loggers to a common file.
        
        Args:
            log_file (str): Name of the log file (will be placed in session directory if not absolute)
            level (int/str, optional): Log level for this handler. Defaults to None (use INFO).
            formatter: Custom formatter to use. Defaults to None.
            max_bytes (int): Maximum file size before rotation
            backup_count (int): Number of backup files to keep
            
        Returns:
            logging.handlers.RotatingFileHandler: The created handler
        """
        # Determine level
        if level is None:
            level = logging.INFO
        elif isinstance(level, str):
            level = get_log_level(level)
            
        # Create the handler with rotation
        handler = self.get_rotating_file_handler(log_file, max_bytes, backup_count, level, formatter)
            
        # Add handler to all current loggers
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        
        return handler
    
    def create_timed_rotating_logger(self, name, log_file, when='midnight', interval=1, backup_count=DEFAULT_BACKUP_COUNT, level=None):
        """Create a logger with a timed rotating file handler.
        
        Args:
            name (str): Logger name
            log_file (str): Log file name (will be placed in session directory if not absolute)
            when (str): Rotation timing - 'S', 'M', 'H', 'D', 'midnight', 'W0'-'W6'
            interval (int): Interval for rotation
            backup_count (int): Number of backup files to keep
            level (int/str, optional): Log level. Defaults to None (use config).
            
        Returns:
            logging.Logger: Configured logger
        """
        logger = setup_logger(name, level=level)
        
        if not os.path.isabs(log_file):
            log_file = os.path.join(self.session_dir, log_file)
            
        # Create a timed rotating file handler
        handler = logging.handlers.TimedRotatingFileHandler(
            log_file,
            when=when,
            interval=interval,
            backupCount=backup_count
        )
        
        # Set level
        if level is None:
            handler.setLevel(logging.INFO)
        elif isinstance(level, str):
            handler.setLevel(get_log_level(level))
        else:
            handler.setLevel(level)
            
        # Use appropriate formatter
        if _config.get('json_format', False):
            handler.setFormatter(JSONFormatter())
        else:
            handler.setFormatter(logging.Formatter(_config.get('format', DEFAULT_CONFIG['format'])))
            
        logger.addHandler(handler)
        
        # Store handler for later management
        if name not in self.handlers:
            self.handlers[name] = []
        self.handlers[name].append(handler)
        
        return logger
    
    def cleanup_old_logs(self, max_age_days=DEFAULT_LOG_RETENTION_DAYS):
        """Clean up log files older than the specified age.
        
        Args:
            max_age_days (int): Maximum age in days for logs to keep
            
        Returns:
            int: Number of files/directories removed
        """
        removed_count = 0
        current_time = time.time()
        max_age_seconds = max_age_days * 24 * 60 * 60
        
        try:
            # Iterate through all items in the base log directory
            for item in os.listdir(self.base_log_dir):
                item_path = os.path.join(self.base_log_dir, item)
                
                # Skip the current session directory
                if item_path == self.session_dir:
                    continue
                    
                # Check if the item is old enough to be removed
                if os.path.isdir(item_path):
                    # For directories, check modification time
                    mtime = os.path.getmtime(item_path)
                    if current_time - mtime > max_age_seconds:
                        # Remove the entire directory
                        import shutil
                        shutil.rmtree(item_path)
                        removed_count += 1
                elif os.path.isfile(item_path):
                    # For files, check modification time
                    mtime = os.path.getmtime(item_path)
                    if current_time - mtime > max_age_seconds:
                        # Remove the file
                        os.remove(item_path)
                        removed_count += 1
        except Exception as e:
            print(f"Error cleaning up old logs: {e}")
            
        return removed_count
    
    def compress_old_logs(self, days_before_compression=7):
        """Compress log files older than the specified age.
        
        Args:
            days_before_compression (int): Age in days before compression
            
        Returns:
            int: Number of files compressed
        """
        import zipfile
        import glob
        
        compressed_count = 0
        current_time = time.time()
        compression_age_seconds = days_before_compression * 24 * 60 * 60
        
        try:
            # Find session directories older than the threshold
            for item in os.listdir(self.base_log_dir):
                item_path = os.path.join(self.base_log_dir, item)
                
                # Skip the current session directory and non-directories
                if item_path == self.session_dir or not os.path.isdir(item_path):
                    continue
                
                # Check if the directory is old enough to be compressed
                mtime = os.path.getmtime(item_path)
                if current_time - mtime > compression_age_seconds:
                    # Check if it's already compressed (has a corresponding zip file)
                    zip_path = f"{item_path}.zip"
                    if os.path.exists(zip_path):
                        continue
                    
                    # Create a zip file
                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        # Add all files in the directory to the zip
                        for root, _, files in os.walk(item_path):
                            for file in files:
                                file_path = os.path.join(root, file)
                                # Add file to zip with relative path
                                arcname = os.path.relpath(file_path, self.base_log_dir)
                                zipf.write(file_path, arcname)
                    
                    # Remove the original directory if zip was successful
                    if os.path.exists(zip_path):
                        import shutil
                        shutil.rmtree(item_path)
                        compressed_count += 1
        except Exception as e:
            print(f"Error compressing old logs: {e}")
            
        return compressed_count

# Global LogManager instance
_log_manager = None

def get_log_manager():
    """Get the global log manager instance, creating it if necessary.
    
    Returns:
        LogManager: The global log manager instance
    """
    global _log_manager
    if _log_manager is None:
        _log_manager = LogManager()
    return _log_manager

def setup_centralized_logging(base_dir=None, create_default_handlers=True):
    """Initialize the centralized logging system.
    
    Args:
        base_dir (str, optional): Base directory for logs. Defaults to None (use DEFAULT_LOG_DIR).
        create_default_handlers (bool): Whether to create default handlers. Defaults to True.
        
    Returns:
        LogManager: The initialized log manager
    """
    global _log_manager
    
    # Create the log manager
    _log_manager = LogManager(base_dir)
    
    if create_default_handlers:
        # Create a shared log file for all messages
        _log_manager.add_shared_file_logger("all.log")
        
        # Create an error-only log file
        error_handler = _log_manager.get_rotating_file_handler(
            os.path.join(_log_manager.session_dir, "errors.log"),
            level=logging.ERROR
        )
        logging.getLogger().addHandler(error_handler)
    
    return _log_manager

def setup_component_logger(component_name, log_level=None, detailed=True, summary=True, errors=True):
    """Set up a logger for a component with centralized management.
    
    Args:
        component_name (str): Name of the component
        log_level (str, optional): Log level for this component. Defaults to None (use config).
        detailed (bool): Whether to create a detailed log file. Defaults to True.
        summary (bool): Whether to create a summary log file. Defaults to True.
        errors (bool): Whether to create an error-only log file. Defaults to True.
        
    Returns:
        logging.Logger: Configured logger for the component
    """
    # Ensure the log manager exists
    log_manager = get_log_manager()
    
    # Create the component logger
    return log_manager.create_component_logger(
        component_name, 
        log_level=log_level,
        detailed=detailed,
        summary=summary,
        errors=errors
    )

def create_timestamped_log_file(filename_prefix, directory=None):
    """Create a timestamped log file name.
    
    Args:
        filename_prefix (str): Prefix for the file name
        directory (str, optional): Directory to place the file in. Defaults to None (use session dir).
        
    Returns:
        str: Full path to the timestamped log file
    """
    log_manager = get_log_manager()
    
    # Create timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{filename_prefix}_{timestamp}.log"
    
    # Determine directory
    if directory is None:
        directory = log_manager.session_dir
    elif not os.path.isabs(directory):
        directory = os.path.join(log_manager.session_dir, directory)
        
    # Ensure directory exists
    os.makedirs(directory, exist_ok=True)
    
    # Return full path
    return os.path.join(directory, filename)

def setup_shared_rotating_file_logger(log_file, level=None, max_bytes=DEFAULT_MAX_BYTES, backup_count=DEFAULT_BACKUP_COUNT):
    """Enhanced version of setup_shared_file_logger with rotation support.
    
    Args:
        log_file (str): Name or path to the log file
        level (str/int, optional): Log level for this handler. Defaults to None (use INFO).
        max_bytes (int): Maximum size in bytes before rotating
        backup_count (int): Number of backup files to keep
        
    Returns:
        logging.handlers.RotatingFileHandler: The created handler
    """
    log_manager = get_log_manager()
    return log_manager.add_shared_file_logger(log_file, level, None, max_bytes, backup_count)

def cleanup_old_logs(max_age_days=DEFAULT_LOG_RETENTION_DAYS):
    """Clean up log files older than the specified age.
    
    Args:
        max_age_days (int): Maximum age in days for logs to keep
        
    Returns:
        int: Number of files/directories removed
    """
    log_manager = get_log_manager()
    return log_manager.cleanup_old_logs(max_age_days)

def compress_old_logs(days_before_compression=7):
    """Compress log files older than the specified age.
    
    Args:
        days_before_compression (int): Age in days before compression
        
    Returns:
        int: Number of files compressed
    """
    log_manager = get_log_manager()
    return log_manager.compress_old_logs(days_before_compression)

def get_session_log_dir():
    """Get the current session log directory.
    
    Returns:
        str: Path to the current session log directory
    """
    log_manager = get_log_manager()
    return log_manager.session_dir 