# Enhanced Logging System

The KFM project includes a flexible and powerful logging system that supports configurable verbosity levels, dynamic log level adjustment, and multiple configuration methods.

## Basic Usage

```python
from src.logger import setup_logger

# Create a logger with default settings (INFO level)
logger = setup_logger("my_module")

# Log messages at different levels
logger.debug("This is a debug message")  # Won't show by default
logger.info("This is an info message")   # Will show by default
logger.warning("This is a warning")
logger.error("This is an error")
logger.critical("This is a critical error")

# Create a logger that also logs to a file
file_logger = setup_logger("my_module.submodule", log_file="submodule.log")

# Create a logger with specific level
debug_logger = setup_logger("my_debug_module", level="DEBUG")  # or level=logging.DEBUG
```

## Changing Log Levels at Runtime

You can dynamically change the log level for any logger:

```python
from src.logger import set_log_level, set_all_loggers_level

# Change a specific logger's level
set_log_level("my_module", "DEBUG")  # or logging.DEBUG

# Change all loggers' levels at once
set_all_loggers_level("WARNING")
```

## Structured Log Output Formatting

The logging system supports different output formats to make logs more readable and filterable.

### JSON Formatting

For machine-readable logs, you can enable JSON output:

```python
from src.logger import setup_logger, set_log_format

# Enable JSON formatting globally
set_log_format(json_format=True)

# Create a logger with JSON formatting
json_logger = setup_logger("json_module", json_format=True)

# The log output will be in JSON format, e.g.:
# {"timestamp": "2023-06-15T14:30:22.123456", "level": "INFO", "logger": "json_module", "message": "User logged in", ...}
```

JSON output includes all standard fields plus any additional fields provided in the log record.

### Colored Console Output

For better readability in the console, you can enable colored output:

```python
from src.logger import setup_logger, set_colored_output

# Enable colored output globally
set_colored_output(enabled=True)

# Create a logger with colored output
color_logger = setup_logger("color_module", colored_output=True)

# The log output will use colors based on log level:
# DEBUG: Cyan
# INFO: Green
# WARNING: Yellow
# ERROR: Red
# CRITICAL: Magenta
```

### Log Filtering

You can filter logs based on message content or module name:

```python
from src.logger import add_log_filter, remove_log_filter, clear_log_filters
from src.logger import exclude_module, include_module, clear_module_exclusions

# Only show logs containing specific text (regex pattern)
add_log_filter("user.*login")  # Only show logs containing "user" followed by "login"

# Remove a specific filter
remove_log_filter("user.*login")

# Clear all filters
clear_log_filters()

# Exclude logs from specific modules
exclude_module("noisy_module")  # Exclude all logs from modules matching this pattern

# Re-include a previously excluded module
include_module("noisy_module")

# Clear all module exclusions
clear_module_exclusions()
```

## Configuration Options

### Environment Variables

The logging system can be configured using environment variables:

- `LOG_LEVEL`: Set the default logging level (e.g., `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`)
- `LOG_LEVEL_<MODULE>`: Set module-specific logging level (e.g., `LOG_LEVEL_CORE=DEBUG`)
- `LOG_DIR`: Directory to store log files (default: `logs/`)
- `LOG_FILE`: Default log file name (enables file logging)
- `LOG_CONSOLE`: Set to `false` to disable console logging
- `LOG_TO_FILE`: Set to `true` to enable file logging by default
- `LOG_JSON`: Set to `true` to enable JSON formatted logging
- `LOG_COLOR`: Set to `false` to disable colored console output
- `LOG_FILTERS`: Comma-separated list of regex patterns to filter log messages
- `LOG_EXCLUDE_MODULES`: Comma-separated list of module patterns to exclude from logging

Example:
```bash
# Set default level to DEBUG and core module to INFO
export LOG_LEVEL=DEBUG
export LOG_LEVEL_CORE=INFO
export LOG_TO_FILE=true
export LOG_FILE=application.log
export LOG_JSON=true  # Enable JSON formatting
export LOG_FILTERS="error,exception"  # Only show logs containing "error" or "exception"
```

### Configuration File

You can configure the logging system using a JSON configuration file:

```python
from src.logger import load_config_from_file

# Load configuration from a file
load_config_from_file("src/config/logger_config.json")
```

Example configuration file (`logger_config.json`):
```json
{
  "log_dir": "logs",
  "default_level": "INFO",
  "module_levels": {
    "src.core": "INFO",
    "src.debugging": "DEBUG",
    "src.tracing": "DEBUG"
  },
  "enable_console": true,
  "enable_file": true,
  "default_file_name": "app.log",
  "format": "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
  "json_format": false,
  "colored_output": true,
  "filters": ["error", "warning"],
  "excluded_modules": ["noisy_module"]
}
```

### Saving Current Configuration

You can save the current configuration to a file for later use:

```python
from src.logger import save_config_to_file

# Save the current configuration
save_config_to_file("my_logger_config.json")
```

## Advanced Features

### Shared File Logger

Set up a file logger that captures logs from all loggers in the application:

```python
from src.logger import setup_shared_file_logger

# Set up a shared file logger at INFO level
setup_shared_file_logger("application.log", level="INFO")
```

### Listing Configured Loggers

You can get information about all configured loggers:

```python
from src.logger import list_configured_loggers

# Get a list of all configured loggers and their settings
loggers = list_configured_loggers()
for logger_info in loggers:
    print(f"Logger: {logger_info['name']}, Level: {logger_info['level']}")
```

### Getting Current Configuration

You can get the current logger configuration:

```python
from src.logger import get_current_config

# Get the current configuration
config = get_current_config()
print(f"Default level: {config['default_level']}")
print(f"Module levels: {config['module_levels']}")
```

## Log Levels

The logging system supports the following log levels, from most to least verbose:

1. `DEBUG` - Detailed debugging information
2. `INFO` - Confirmation that things are working as expected
3. `WARNING` - Indication that something unexpected happened, or may happen in the near future
4. `ERROR` - Due to a more serious problem, the software has not been able to perform a function
5. `CRITICAL` - A serious error, indicating that the program itself may be unable to continue running
6. `NONE` - Disable logging completely for a specific logger (level set above CRITICAL)

## Best Practices

1. **Module-specific loggers**: Create a logger for each module with a name that reflects the module's path.
2. **Appropriate log levels**: Use the appropriate level for each message.
3. **Log file organization**: Use different log files for different components or aspects of the application.
4. **Avoid excessive logging**: In production, use higher log levels to avoid performance issues.
5. **Include context**: Include relevant context in log messages to aid debugging.
6. **Structured logs**: Use JSON formatting in production environments or when feeding logs to analytics tools.
7. **Colored output**: Use colored output in development for better readability, but disable in production.
8. **Filtering**: Use filters to focus on important messages in noisy environments.

```python
# Good logging practice
logger.debug(f"Processing item {item_id}: state={item.state}, status={item.status}")

# Don't log sensitive information
logger.info(f"User authenticated: {username}")  # Good
logger.info(f"User authenticated: {username}, password={password}")  # BAD - never log passwords
```

## Integration with Debugging Tools

The enhanced logger integrates well with the debugging tools in the `src.debugging` and `src.tracing` modules. See their respective documentation for details on how to use them together for comprehensive debugging capabilities.

## Examples of Different Log Formats

### Default Text Format

```
2023-06-15 14:30:22,123 - my_module - INFO - process_login:42 - User logged in: username=john_doe
```

### JSON Format

```json
{
  "timestamp": "2023-06-15T14:30:22.123456",
  "level": "INFO",
  "level_num": 20,
  "logger": "my_module",
  "message": "User logged in: username=john_doe",
  "module": "auth",
  "function": "process_login",
  "line": 42,
  "process_id": 12345,
  "thread_id": 140735505284096
}
```

### Colored Console Output

The console output with color shows log levels in different colors:
- `DEBUG` in cyan
- `INFO` in green
- `WARNING` in yellow
- `ERROR` in red
- `CRITICAL` in magenta

This makes it easy to spot important messages visually when debugging.

## Centralized Log Management

The KFM project includes a centralized log management system that provides advanced features such as:

- Log rotation and automatic backup
- Timestamped log directories organized by session
- Component-specific logging
- Log archiving for older logs
- Log aggregation across multiple components

### Setting Up Centralized Logging

```python
from src.logger import (
    setup_centralized_logging,
    setup_component_logger,
    create_timestamped_log_file,
    get_session_log_dir
)

# Initialize the centralized logging system
log_manager = setup_centralized_logging()

# Get the current session's log directory
session_dir = get_session_log_dir()
print(f"Logs will be written to: {session_dir}")

# Create a timestamped log file for a specific component
log_file = create_timestamped_log_file("my_component")
print(f"Component log file: {log_file}")

# Set up a logger for a specific component
component_logger = setup_component_logger("my_component", log_level="DEBUG")
component_logger.info("This is logged to the component's log file")
```

### Log Rotation

The log management system supports log rotation to prevent log files from growing too large:

```python
from src.logger import LogManager

# Create a log manager
log_manager = LogManager()

# Create a rotating file handler
handler = log_manager.create_rotating_handler(
    "my_application.log",
    max_bytes=10 * 1024 * 1024,  # 10 MB per file
    backup_count=5               # Keep 5 backup files
)

# Add the handler to a logger
my_logger = setup_logger("my_application")
my_logger.addHandler(handler)
```

### Session-Based Logging

The log management system organizes logs by session, with each run of your application getting a unique timestamped directory:

```python
# Get the current session's log directory
session_dir = get_session_log_dir()

# Create a timestamped log file in the session directory
log_file = create_timestamped_log_file("component_name")

# Set up a shared file logger to capture logs from all components
setup_shared_file_logger(os.path.basename(log_file))
```

### Log Archiving

The log management system can automatically archive old logs to save disk space:

```python
# Archive logs older than 30 days
log_manager = setup_centralized_logging()
log_manager.archive_old_logs(retention_days=30)
```

### Enhanced Shared File Logger

The enhanced shared file logger adds log rotation support:

```python
from src.logger import setup_shared_file_logger

# Set up a shared file logger with rotation
setup_shared_file_logger(
    "application.log", 
    level="INFO",
    max_bytes=5 * 1024 * 1024,  # 5 MB per file
    backup_count=3              # Keep 3 backup files
)
```

### Centralized Logging Example

Here's a complete example demonstrating the centralized logging system:

```python
import os
from src.logger import (
    setup_centralized_logging,
    setup_component_logger,
    create_timestamped_log_file,
    get_session_log_dir,
    setup_shared_file_logger
)

# Initialize the centralized logging system
log_manager = setup_centralized_logging()
session_dir = get_session_log_dir()
print(f"Log session directory: {session_dir}")

# Create individual component loggers
auth_logger = setup_component_logger("auth_service", log_level="INFO")
api_logger = setup_component_logger("api_gateway", log_level="DEBUG")
data_logger = setup_component_logger("data_processor", log_level="INFO")

# Create a shared log file that captures logs from all components
shared_log = create_timestamped_log_file("application")
setup_shared_file_logger(os.path.basename(shared_log))
print(f"Shared log file: {shared_log}")

# Log some messages to different components
auth_logger.info("User authentication successful")
api_logger.debug("Processing API request")
data_logger.warning("Data validation warning")

# All of these messages will appear in both their component-specific logs
# and in the shared log file
```

### Listing Configured Loggers

You can get information about all configured loggers:

```python
from src.logger import list_configured_loggers

# Get a list of all configured loggers and their settings
loggers = list_configured_loggers()
for logger_info in loggers:
    print(f"Logger: {logger_info['name']}, Level: {logger_info['level']}")
```
