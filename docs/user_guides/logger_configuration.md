# Logger Configuration

This guide explains how to configure the enhanced logging system in the KFM debugging tools to effectively capture and monitor graph execution details.

## Logger Overview

The KFM debugging toolkit includes an advanced logging system that provides detailed insights into graph execution. Key features include:

- **Multi-level logging** - Control verbosity with different log levels
- **Contextual information** - Automatically capture node names, timestamps, and state changes
- **Custom formatters** - Format log messages to highlight important information
- **Multiple outputs** - Log to console, files, or custom destinations
- **Structured logging** - Access structured log data for programmatic analysis

## Basic Configuration

### Setting the Log Level

Control the verbosity of logging by setting the log level:

```python
from kfm_debugging import Debugger, LogLevel

# Create a debugger with a specific log level
debugger = Debugger(graph, log_level=LogLevel.INFO)

# Or change the log level after initialization
debugger.set_log_level(LogLevel.DEBUG)
```

Available log levels (from least to most verbose):

- `LogLevel.ERROR` - Only log errors and critical issues
- `LogLevel.WARNING` - Log warnings and errors
- `LogLevel.INFO` - Log general information (default)
- `LogLevel.DEBUG` - Log detailed debugging information
- `LogLevel.TRACE` - Log extensive tracing information

### Configuring Output Destinations

Direct logs to different destinations:

```python
# Log to a file
debugger.configure_logger(log_file="debug_output.log")

# Log to both console and file
debugger.configure_logger(
    log_file="debug_output.log",
    console_output=True
)

# Specify a directory for log files
debugger.configure_logger(
    log_directory="logs/",
    log_filename="debug_{timestamp}.log",
    console_output=True
)
```

## Advanced Configuration

### Custom Log Formatting

Customize log message format:

```python
debugger.configure_logger(
    log_format="[{timestamp}] [{level}] {node}: {message}",
    timestamp_format="%Y-%m-%d %H:%M:%S.%f"
)
```

Common format placeholders:
- `{timestamp}` - Time when the log entry was created
- `{level}` - Log level (ERROR, WARNING, INFO, etc.)
- `{node}` - Name of the graph node
- `{message}` - The log message content
- `{execution_id}` - Unique ID for the current execution
- `{step}` - Current execution step number

### Log Filtering

Filter logs based on nodes or patterns:

```python
# Include logs only from specific nodes
debugger.configure_logger(include_nodes=["node1", "node2"])

# Exclude logs from specific nodes
debugger.configure_logger(exclude_nodes=["verbose_node"])

# Filter logs using a custom filter function
debugger.configure_logger(
    filter_function=lambda log_entry: "important" in log_entry.message
)
```

### Structured Logging

Enable structured logging for programmatic analysis:

```python
# Enable structured logging to a JSON file
debugger.configure_logger(
    structured_log_file="structured_logs.json",
    structured_format="json"
)

# Access structured logs programmatically
structured_logs = debugger.get_structured_logs()
for log in structured_logs:
    if log.level == LogLevel.ERROR:
        print(f"Error in node {log.node}: {log.message}")
```

## Log Categories

The logger supports different categories of log messages:

```python
# Configure specific categories
debugger.configure_logger(
    categories={
        "state": LogLevel.INFO,     # State changes
        "execution": LogLevel.DEBUG, # Node execution
        "performance": LogLevel.WARNING, # Performance information
        "error": LogLevel.ERROR     # Error information
    }
)
```

Available categories:
- `state` - Logs related to state changes
- `execution` - Logs related to node execution
- `performance` - Logs related to performance metrics
- `error` - Logs related to errors and exceptions
- `warning` - Logs related to warnings and potential issues
- `system` - Logs related to system operations

## Customizing Log Handlers

For advanced use cases, you can add custom log handlers:

```python
import logging
from kfm_debugging import Debugger

# Create a custom handler
custom_handler = logging.StreamHandler()
custom_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Add the custom handler to the debugger's logger
debugger = Debugger(graph)
debugger.logger.addHandler(custom_handler)
```

## Integration with External Logging Systems

Integrate with external logging systems:

```python
# Example: Integrate with application-wide logging
import logging
app_logger = logging.getLogger("my_application")

debugger.configure_logger(external_logger=app_logger)
```

## Best Practices

- **Set appropriate log levels**: Use higher verbosity (DEBUG/TRACE) during development and lower (INFO/WARNING) in production
- **Include timestamps**: Always include timestamps for debugging sequence-dependent issues
- **Organize log files**: Use separate log files for different components or execution runs
- **Rotate logs**: For long-running applications, configure log rotation to manage file sizes
- **Filter noise**: Use node filtering to focus on relevant parts of the graph
- **Structured for analysis**: Use structured logging for automated log analysis

## Troubleshooting

Common logging issues and solutions:

- **High volume of logs**: Increase log level (ERROR/WARNING) or filter specific nodes
- **Missing information**: Decrease log level (DEBUG/TRACE) to see more details
- **Performance impact**: Disable console logging for performance-critical code
- **Missing log files**: Check write permissions in the log directory
- **Timestamp issues**: Ensure the timestamp format is compatible with your analysis tools

## Next Steps

- [State Difference Visualization](state_diff_visualization.md) for detailed state analysis
- [Breakpoint System](breakpoint_system.md) for execution control
- [Error Handling and Recovery](error_handling.md) for error management

For a practical example of logger configuration, see the [Logger Configuration Example](../examples/logger_configuration_example.md). 