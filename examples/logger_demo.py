#!/usr/bin/env python
"""
Logger demo - demonstrates the enhanced logger functionality.

This script shows how to use the various features of the enhanced logger system.
"""

import os
import sys
import time
import random

# Add the project root to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.logger import (
    setup_logger,
    set_log_level,
    load_config_from_file,
    save_config_to_file,
    load_config_from_env,
    set_all_loggers_level,
    setup_shared_file_logger,
    list_configured_loggers,
    get_current_config,
    # New imports for structured logging
    set_log_format,
    set_colored_output,
    add_log_filter,
    remove_log_filter,
    clear_log_filters,
    exclude_module,
    include_module,
    clear_module_exclusions
)

# Create a logger for this module
logger = setup_logger("examples.logger_demo")

def log_at_different_levels():
    """Demonstrate logging at different levels."""
    logger.info("=== LOGGING AT DIFFERENT LEVELS ===")
    
    logger.debug("This is a DEBUG message - detailed information for debugging")
    logger.info("This is an INFO message - confirmation that things are working as expected")
    logger.warning("This is a WARNING message - something unexpected happened")
    logger.error("This is an ERROR message - a more serious problem occurred")
    logger.critical("This is a CRITICAL message - a serious error, program may be unable to continue")
    
    # Demonstrate that debug messages are hidden at INFO level
    logger.info("\nBy default, DEBUG messages are hidden at INFO level")

def change_log_levels():
    """Demonstrate changing log levels at runtime."""
    logger.info("\n=== CHANGING LOG LEVELS ===")
    
    # Show current level
    logger.info(f"Current log level: {logger.level}")
    
    # Change to DEBUG
    logger.info("Changing log level to DEBUG...")
    set_log_level("examples.logger_demo", "DEBUG")
    
    # Show debug messages now visible
    logger.debug("This DEBUG message should now be visible")
    
    # Change back to INFO
    logger.info("Changing log level back to INFO...")
    set_log_level("examples.logger_demo", "INFO")
    
    # Show debug messages hidden again
    logger.debug("This DEBUG message should be hidden again")
    logger.info("The above DEBUG message should be hidden at INFO level")

def log_with_context():
    """Demonstrate logging with contextual information."""
    logger.info("\n=== LOGGING WITH CONTEXT ===")
    
    # Create fictional user data
    user = {
        "id": 12345,
        "username": "example_user",
        "email": "user@example.com",
        "last_login": "2023-06-15 14:30:22"
    }
    
    # Log with context
    logger.info(f"User logged in: id={user['id']}, username={user['username']}")
    
    # Log at different levels based on conditions
    items_processed = 1500
    if items_processed > 1000:
        logger.warning(f"High number of items processed: {items_processed}")
    else:
        logger.info(f"Normal number of items processed: {items_processed}")
    
    # Simulate an error with context
    try:
        result = 10 / 0
    except Exception as e:
        logger.error(f"Error during calculation: {str(e)}", exc_info=True)

def work_with_config_file():
    """Demonstrate working with config files."""
    logger.info("\n=== WORKING WITH CONFIG FILES ===")
    
    # Save current configuration
    config_file = "logger_demo_config.json"
    logger.info(f"Saving current config to {config_file}")
    save_config_to_file(config_file)
    
    # Modify config and save again
    logger.info("Setting all loggers to DEBUG level")
    set_all_loggers_level("DEBUG")
    
    # Display current config
    config = get_current_config()
    logger.info(f"Current config: default_level={config['default_level']}")
    
    # Load the original config back
    logger.info(f"Loading config from {config_file}")
    load_config_from_file(config_file)
    
    # Display loaded config
    config = get_current_config()
    logger.info(f"Loaded config: default_level={config['default_level']}")
    
    # Clean up
    if os.path.exists(config_file):
        os.remove(config_file)
        logger.info(f"Removed temporary config file: {config_file}")

def simulate_component_logging():
    """Simulate logging from different components at different levels."""
    logger.info("\n=== SIMULATING COMPONENT LOGGING ===")
    
    # Create loggers for different components
    db_logger = setup_logger("examples.logger_demo.database")
    api_logger = setup_logger("examples.logger_demo.api")
    auth_logger = setup_logger("examples.logger_demo.auth")
    
    # Set different log levels
    set_log_level("examples.logger_demo.database", "DEBUG")
    set_log_level("examples.logger_demo.api", "INFO") 
    set_log_level("examples.logger_demo.auth", "WARNING")
    
    # Create a shared log file for all components
    setup_shared_file_logger("component_demo.log")
    
    # Simulate logging from different components
    logger.info("Main application: Starting components...")
    
    db_logger.debug("Database: Connecting to database server")
    db_logger.info("Database: Connection established")
    
    api_logger.debug("API: Debug message (should not be visible at INFO level)")
    api_logger.info("API: Server listening on port 8000")
    
    auth_logger.debug("Auth: Debug message (should not be visible at WARNING level)")
    auth_logger.info("Auth: Info message (should not be visible at WARNING level)")
    auth_logger.warning("Auth: Invalid login attempt")
    
    # List configured loggers
    all_loggers = list_configured_loggers()
    logger.info(f"Configured loggers: {len(all_loggers)}")
    for log_info in all_loggers:
        logger.info(f"  - {log_info['name']}: {log_info['level']}")

def demonstrate_json_formatting():
    """Demonstrate JSON formatted logging."""
    logger.info("\n=== JSON FORMATTED LOGGING ===")
    
    # Create a JSON logger
    json_logger = setup_logger("examples.logger_demo.json", json_format=True)
    
    logger.info("Standard logger output (text format)")
    json_logger.info("JSON logger output (JSON format)")
    
    # Enable JSON formatting globally
    logger.info("Enabling JSON formatting globally...")
    set_log_format(True)
    
    # Show the effect on existing loggers
    logger.info("This should now be in JSON format")
    
    # Create a new JSON logger after global setting
    global_json_logger = setup_logger("examples.logger_demo.global_json")
    global_json_logger.info("Logger created after global JSON setting")
    
    # Disable JSON formatting globally
    logger.info("Disabling JSON formatting globally...")
    set_log_format(False)
    
    # Show the effect on existing loggers
    logger.info("This should now be back to text format")

def demonstrate_colored_output():
    """Demonstrate colored console output."""
    logger.info("\n=== COLORED CONSOLE OUTPUT ===")
    
    # Create a logger with colored output
    color_logger = setup_logger("examples.logger_demo.color", colored_output=True)
    
    logger.info("Demonstrating colored output...")
    
    # Log at different levels to show different colors
    color_logger.debug("This DEBUG message should be in cyan")
    color_logger.info("This INFO message should be in green")
    color_logger.warning("This WARNING message should be in yellow")
    color_logger.error("This ERROR message should be in red")
    color_logger.critical("This CRITICAL message should be in magenta")
    
    # Toggle colored output
    logger.info("Disabling colored output globally...")
    set_colored_output(False)
    
    color_logger.info("This should now be without color")
    
    logger.info("Re-enabling colored output globally...")
    set_colored_output(True)
    
    color_logger.info("This should have color again")

def demonstrate_log_filtering():
    """Demonstrate log message filtering."""
    logger.info("\n=== LOG MESSAGE FILTERING ===")
    
    # Create a logger for filtering
    filter_logger = setup_logger("examples.logger_demo.filter")
    
    # Log some messages before filtering
    logger.info("Logging some messages before applying filters:")
    filter_logger.info("User signed up: username=john_doe")
    filter_logger.info("Processing payment: amount=$50.00")
    filter_logger.warning("Failed login attempt: username=anonymous")
    filter_logger.error("Database connection error: timeout")
    
    # Add a filter to only show messages about users
    logger.info("\nAdding filter for 'user' messages:")
    add_log_filter("user")
    
    # Log the same messages with filter applied
    filter_logger.info("User signed up: username=john_doe")  # Should show
    filter_logger.info("Processing payment: amount=$50.00")  # Should not show
    filter_logger.warning("Failed login attempt: username=anonymous")  # Should not show
    filter_logger.error("Database connection error: timeout")  # Should not show
    
    # Replace with a more complex filter
    logger.info("\nReplacing with filter for 'error|warning':")
    clear_log_filters()
    add_log_filter("error|warning")
    
    # Log the same messages with new filter
    filter_logger.info("User signed up: username=john_doe")  # Should not show
    filter_logger.info("Processing payment: amount=$50.00")  # Should not show
    filter_logger.warning("Failed login attempt: username=anonymous")  # Should show
    filter_logger.error("Database connection error: timeout")  # Should show
    
    # Clear all filters
    logger.info("\nClearing all filters:")
    clear_log_filters()
    
    # Log one more message to show filter is cleared
    filter_logger.info("All messages should show now")

def demonstrate_module_exclusion():
    """Demonstrate module exclusion filtering."""
    logger.info("\n=== MODULE EXCLUSION FILTERING ===")
    
    # Create loggers for different modules
    module1_logger = setup_logger("examples.logger_demo.module1")
    module2_logger = setup_logger("examples.logger_demo.module2")
    
    # Log some messages before exclusion
    logger.info("Logging from different modules before exclusion:")
    module1_logger.info("Message from module1")
    module2_logger.info("Message from module2")
    
    # Exclude module1
    logger.info("\nExcluding module1:")
    exclude_module("examples\\.logger_demo\\.module1")
    
    # Log messages after exclusion
    module1_logger.info("Message from module1 (should be filtered out)")
    module2_logger.info("Message from module2 (should show)")
    
    # Include module1 again
    logger.info("\nIncluding module1 again:")
    include_module("examples\\.logger_demo\\.module1")
    
    # Log messages after inclusion
    module1_logger.info("Message from module1 (should show again)")
    module2_logger.info("Message from module2 (should show)")
    
    # Clear module exclusions
    clear_module_exclusions()

def main():
    """Run the logger demo."""
    logger.info("Starting Logger Demo")
    
    # Run the demonstrations
    log_at_different_levels()
    change_log_levels()
    log_with_context()
    work_with_config_file()
    simulate_component_logging()
    
    # Run new demonstrations for structured logging
    demonstrate_json_formatting()
    demonstrate_colored_output()
    demonstrate_log_filtering()
    demonstrate_module_exclusion()
    
    logger.info("\nLogger Demo Completed")

if __name__ == "__main__":
    main() 