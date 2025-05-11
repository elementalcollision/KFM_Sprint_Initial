#!/usr/bin/env python
"""
Centralized Logger Demo - demonstrates the centralized log management functionality.

This script shows how to use the various features of the centralized log management system,
including log rotation, session-based logging, and timestamped directories.
"""

import os
import sys
import time
import random
import threading
import logging

# Add the project root to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.logger import (
    # Basic logger functions
    setup_logger,
    set_log_level,
    
    # Centralized log management functions
    setup_centralized_logging,
    setup_component_logger,
    setup_shared_rotating_file_logger,
    create_timestamped_log_file,
    get_session_log_dir,
    cleanup_old_logs,
    compress_old_logs,
    get_log_manager
)

def demonstrate_session_based_logging():
    """Demonstrate the basic session-based logging functionality."""
    print("\n=== DEMONSTRATING SESSION-BASED LOGGING ===")
    
    # Initialize the centralized logging system
    log_manager = setup_centralized_logging()
    session_dir = get_session_log_dir()
    print(f"Created session directory: {session_dir}")
    
    # Create a main logger
    main_logger = setup_logger("examples.centralized_demo.main")
    main_logger.info("This is the main logger for the demo")
    
    # Create component loggers (these will automatically output to the session directory)
    db_logger = setup_component_logger("examples.centralized_demo.database")
    api_logger = setup_component_logger("examples.centralized_demo.api")
    auth_logger = setup_component_logger("examples.centralized_demo.auth")
    
    # Log messages at different levels
    db_logger.debug("Database: Debug message - connecting to database")
    db_logger.info("Database: Successfully connected to database")
    
    api_logger.info("API: Server starting on port 8000")
    api_logger.warning("API: Performance warning - high load detected")
    
    auth_logger.info("Auth: User authentication system initialized")
    auth_logger.error("Auth: Failed login attempt for user 'admin'")
    
    # Show the directory structure
    print("\nLog directory structure created:")
    for root, dirs, files in os.walk(session_dir):
        level = root.replace(session_dir, '').count(os.sep)
        indent = ' ' * 4 * level
        print(f"{indent}{os.path.basename(root)}/")
        sub_indent = ' ' * 4 * (level + 1)
        for file in files:
            print(f"{sub_indent}{file}")

def simulate_application_logging():
    """Simulate an application generating logs across different components."""
    print("\n=== SIMULATING APPLICATION LOGGING ===")
    
    # Create loggers for different components
    app_logger = setup_component_logger("examples.centralized_demo.app")
    data_logger = setup_component_logger("examples.centralized_demo.data")
    ui_logger = setup_component_logger("examples.centralized_demo.ui")
    
    app_logger.info("Application starting...")
    
    # Simulate a user session
    app_logger.info("User session starting")
    
    # Simulate data loading
    data_logger.debug("Loading data from source")
    data_logger.info("Data loaded successfully: 1000 records")
    
    # Simulate UI rendering
    ui_logger.info("Rendering main interface")
    ui_logger.debug("Drawing 50 UI components")
    
    # Simulate an error condition
    try:
        # Simulate a division by zero error
        result = 100 / 0
    except Exception as e:
        app_logger.error(f"Error in calculation: {str(e)}", exc_info=True)
    
    # Simulate more activity
    for i in range(5):
        component = random.choice(["app", "data", "ui"])
        level = random.choice(["debug", "info", "warning", "error"])
        
        logger = {
            "app": app_logger,
            "data": data_logger,
            "ui": ui_logger
        }[component]
        
        message = f"Random {component} message #{i+1}"
        
        if level == "debug":
            logger.debug(message)
        elif level == "info":
            logger.info(message)
        elif level == "warning":
            logger.warning(message)
        else:
            logger.error(message)
            
    app_logger.info("Application shutting down")

def demonstrate_log_rotation():
    """Demonstrate log rotation functionality."""
    print("\n=== DEMONSTRATING LOG ROTATION ===")
    
    # Create a logger with a rotating file handler
    rotation_logger = setup_logger("examples.centralized_demo.rotation")
    
    # Set up a shared rotating file logger
    handler = setup_shared_rotating_file_logger(
        "rotation_demo.log",
        max_bytes=1024,  # Set a small size for demonstration
        backup_count=3
    )
    
    # Add the handler to our logger
    rotation_logger.addHandler(handler)
    
    print("Writing logs to trigger rotation...")
    
    # Generate enough logs to trigger rotation
    for i in range(50):
        # Create a message with some random data to increase size
        random_data = ''.join([random.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(20)])
        rotation_logger.info(f"Log message #{i+1} with random data: {random_data}")
    
    print("Log rotation demonstration complete. Check the following files in the session directory:")
    session_dir = get_session_log_dir()
    
    # List rotation files
    rotation_files = [f for f in os.listdir(session_dir) if f.startswith("rotation_demo.log")]
    for file in rotation_files:
        path = os.path.join(session_dir, file)
        size = os.path.getsize(path)
        print(f" - {file} ({size} bytes)")

def demonstrate_timestamped_log_files():
    """Demonstrate creating timestamped log files."""
    print("\n=== DEMONSTRATING TIMESTAMPED LOG FILES ===")
    
    # Create loggers with timestamped file names
    for i in range(3):
        # Create a timestamped log file
        log_file = create_timestamped_log_file(f"process_{i}")
        print(f"Created timestamped log file: {os.path.basename(log_file)}")
        
        # Create a logger for this file
        process_logger = setup_logger(f"examples.centralized_demo.process_{i}")
        
        # Add a file handler using the timestamped file
        handler = logging.FileHandler(log_file)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        process_logger.addHandler(handler)
        
        # Log some messages
        process_logger.info(f"Process {i} starting")
        process_logger.info(f"Process {i} running task")
        process_logger.info(f"Process {i} completed")
        
        # Small delay to ensure different timestamps
        time.sleep(1)
    
    print("Timestamped log files demonstration complete.")

def demonstrate_component_specific_logging():
    """Demonstrate component-specific logging with different configurations."""
    print("\n=== DEMONSTRATING COMPONENT-SPECIFIC LOGGING ===")
    
    # Create component loggers with different configurations
    # Full logging (detailed, summary, errors)
    full_logger = setup_component_logger(
        "examples.centralized_demo.full_component",
        log_level="DEBUG",
        detailed=True,
        summary=True,
        errors=True
    )
    
    # Summary-only logging
    summary_logger = setup_component_logger(
        "examples.centralized_demo.summary_component",
        log_level="INFO",
        detailed=False,
        summary=True,
        errors=True
    )
    
    # Errors-only logging
    errors_logger = setup_component_logger(
        "examples.centralized_demo.errors_component",
        log_level="WARNING",
        detailed=False,
        summary=False,
        errors=True
    )
    
    # Log messages at different levels to each logger
    print("Logging to full component logger (all levels):")
    full_logger.debug("DEBUG message to full logger")
    full_logger.info("INFO message to full logger")
    full_logger.warning("WARNING message to full logger")
    full_logger.error("ERROR message to full logger")
    
    print("\nLogging to summary component logger (INFO and above):")
    summary_logger.debug("DEBUG message to summary logger (should not appear in detailed logs)")
    summary_logger.info("INFO message to summary logger")
    summary_logger.warning("WARNING message to summary logger")
    summary_logger.error("ERROR message to summary logger")
    
    print("\nLogging to errors component logger (WARNING and above):")
    errors_logger.debug("DEBUG message to errors logger (should not appear)")
    errors_logger.info("INFO message to errors logger (should not appear)")
    errors_logger.warning("WARNING message to errors logger")
    errors_logger.error("ERROR message to errors logger")
    
    print("\nComponent-specific logging demonstration complete.")
    print("Check the detailed/, summary/, and errors/ directories in the session directory.")

def demonstrate_multi_threaded_logging():
    """Demonstrate multi-threaded logging to shared files."""
    print("\n=== DEMONSTRATING MULTI-THREADED LOGGING ===")
    
    # Create a shared log file for all threads
    shared_log_file = create_timestamped_log_file("threaded_demo")
    
    # Shared file handler
    handler = logging.FileHandler(shared_log_file)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(threadName)s - %(name)s - %(levelname)s - %(message)s'))
    
    def worker_function(worker_id):
        # Create a logger for this worker
        worker_logger = setup_logger(f"examples.centralized_demo.worker{worker_id}")
        worker_logger.addHandler(handler)
        
        # Log some messages
        worker_logger.info(f"Worker {worker_id} starting")
        
        # Simulate some work
        for i in range(3):
            worker_logger.debug(f"Worker {worker_id} - debug message {i}")
            worker_logger.info(f"Worker {worker_id} - info message {i}")
            # Random sleep to mix up the log messages
            time.sleep(random.uniform(0.1, 0.5))
            
        worker_logger.info(f"Worker {worker_id} completed")
    
    # Create and start worker threads
    threads = []
    for i in range(5):
        thread = threading.Thread(
            target=worker_function, 
            args=(i,),
            name=f"Worker-{i}"
        )
        threads.append(thread)
        thread.start()
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    print(f"Multi-threaded logging complete. Check {os.path.basename(shared_log_file)}")
    print("Threads logged concurrently to the same file with thread identification.")

def simulate_log_cleanup_and_compression():
    """Simulate log cleanup and compression operations."""
    print("\n=== SIMULATING LOG CLEANUP AND COMPRESSION ===")
    
    print("This is a simulated demonstration - in a real environment, these functions")
    print("would manage log files based on their age:")
    
    print("\n1. cleanup_old_logs(max_age_days=30)")
    print("   - Removes log files and directories older than 30 days")
    print("   - Returns the number of files/directories removed")
    
    print("\n2. compress_old_logs(days_before_compression=7)")
    print("   - Compresses log directories older than 7 days into zip files")
    print("   - Preserves the logs but reduces disk space usage")
    print("   - Returns the number of directories compressed")
    
    print("\nThese functions help maintain log storage by:")
    print(" - Automatically removing old logs to prevent disk space issues")
    print(" - Compressing less frequently accessed logs to save space")
    print(" - Maintaining a hierarchical structure for easy log navigation")

def main():
    """Main function to run the demo."""
    print("CENTRALIZED LOG MANAGEMENT DEMONSTRATION")
    print("========================================")
    
    # Initialize the centralized logging system
    setup_centralized_logging()
    
    # Run the demonstrations
    demonstrate_session_based_logging()
    simulate_application_logging()
    demonstrate_log_rotation()
    demonstrate_timestamped_log_files()
    demonstrate_component_specific_logging()
    demonstrate_multi_threaded_logging()
    simulate_log_cleanup_and_compression()
    
    # Show final log directory structure
    session_dir = get_session_log_dir()
    print("\n=== FINAL LOG DIRECTORY STRUCTURE ===")
    print(f"Session directory: {session_dir}")
    print("\nLog files created:")
    
    # Count files in each directory
    detailed_count = len(os.listdir(os.path.join(session_dir, 'detailed')))
    summary_count = len(os.listdir(os.path.join(session_dir, 'summary')))
    error_count = len(os.listdir(os.path.join(session_dir, 'errors')))
    root_count = len([f for f in os.listdir(session_dir) if os.path.isfile(os.path.join(session_dir, f))])
    
    print(f" - Root directory: {root_count} files")
    print(f" - Detailed logs: {detailed_count} files")
    print(f" - Summary logs: {summary_count} files")
    print(f" - Error logs: {error_count} files")
    
    print("\nDemonstration complete! Examine the log files in the session directory")
    print(f"to see the different logging configurations and outputs: {session_dir}")

if __name__ == "__main__":
    main() 