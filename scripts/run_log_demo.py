#!/usr/bin/env python
"""
Log Management Demo Script

This script demonstrates the centralized log management system with:
1. Multiple component loggers
2. Log rotation and archiving
3. Timestamped directories
4. Shared file logging across components

Run with: python scripts/run_log_demo.py
"""

import os
import sys
import time
import random
import logging
from datetime import datetime

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.logger import (
    # Basic logger functions
    setup_logger,
    set_log_level,
    
    # Centralized log management functions
    setup_centralized_logging,
    setup_component_logger,
    create_timestamped_log_file,
    get_session_log_dir,
    setup_shared_file_logger,
    LogManager
)

def simulate_component_activity(logger, component_name, iterations=100):
    """Simulate component activity by logging messages."""
    for i in range(iterations):
        # Simulate different log levels
        log_level = random.choice([
            (logging.DEBUG, f"DEBUG: {component_name} processing step {i}"),
            (logging.INFO, f"INFO: {component_name} completed step {i}"),
            (logging.WARNING, f"WARNING: {component_name} encountered non-critical issue in step {i}"),
            (logging.ERROR, f"ERROR: {component_name} failed in step {i}")
        ])
        
        # Log the message
        logger.log(log_level[0], log_level[1])
        
        # Add a small delay
        time.sleep(0.01)

def main():
    """Main demo function."""
    print("🔍 Starting Centralized Log Management Demo")
    
    # Initialize the centralized log management system
    print("\n1. Setting up centralized logging...")
    log_manager = setup_centralized_logging()
    session_dir = get_session_log_dir()
    
    print(f"   ✅ Log session directory: {session_dir}")
    
    # Create shared log file for this demo
    print("\n2. Creating shared log file...")
    shared_log = create_timestamped_log_file("log_demo")
    setup_shared_file_logger(shared_log)
    print(f"   ✅ Shared log file: {shared_log}")
    
    # Set up component loggers
    print("\n3. Setting up component loggers...")
    components = ["auth_service", "data_processor", "api_gateway", "storage_manager", "user_interface"]
    loggers = {}
    
    for component in components:
        loggers[component] = setup_component_logger(component)
        print(f"   ✅ Created logger for component: {component}")
    
    # Simulate component activity
    print("\n4. Simulating component activity (writing logs)...")
    for component, logger in loggers.items():
        iterations = random.randint(50, 200)  # Random number of log entries
        print(f"   🔄 Component {component} generating {iterations} log entries...")
        simulate_component_activity(logger, component, iterations)
    
    # Demonstrate log rotation
    print("\n5. Demonstrating log rotation...")
    rotation_log = os.path.join(session_dir, "rotation_demo.log")
    rotation_handler = log_manager.create_rotating_handler(
        rotation_log,
        max_bytes=1024,  # 1KB per log file to trigger rotation quickly
        backup_count=5
    )
    
    # Create dedicated logger for rotation demo
    rotation_logger = logging.getLogger("rotation_demo")
    rotation_logger.setLevel(logging.DEBUG)
    rotation_logger.addHandler(rotation_handler)
    
    print(f"   🔄 Writing to rotation demo log: {rotation_log}")
    
    # Write enough data to trigger rotation
    large_message = "X" * 200  # 200 character message
    for i in range(30):  # This should create multiple rotated files
        rotation_logger.info(f"Rotation test {i}: {large_message}")
    
    # List the rotated files
    rotation_files = [f for f in os.listdir(session_dir) if f.startswith(os.path.basename(rotation_log))]
    print(f"   ✅ Created {len(rotation_files)} rotation files:")
    for file in rotation_files:
        file_path = os.path.join(session_dir, file)
        file_size = os.path.getsize(file_path) / 1024  # Convert to KB
        print(f"      - {file} ({file_size:.2f} KB)")
    
    # Demonstrate log archiving
    print("\n6. Demonstrating log archiving...")
    archives_dir = os.path.join(log_manager.base_log_dir, "archives")
    os.makedirs(archives_dir, exist_ok=True)
    
    # Create a sample older log directory to be archived
    print("   🔄 Creating sample older logs...")
    old_date = "2023-01-01"  # This date should be old enough to trigger archiving
    old_log_dir = os.path.join(log_manager.base_log_dir, old_date)
    os.makedirs(old_log_dir, exist_ok=True)
    
    # Create a few sample old log files
    for i in range(3):
        old_log_file = os.path.join(old_log_dir, f"old_service_{i}.log")
        with open(old_log_file, "w") as f:
            f.write(f"This is an old log file {i} that should be archived.\n")
            f.write(f"Created for testing the log archiving feature.\n")
    
    print("   🔄 Running log archiving process...")
    log_manager.archive_old_logs(retention_days=30)  # Archive logs older than 30 days
    
    if os.path.exists(old_log_dir):
        print("   ❌ Old log directory still exists (should be archived)")
    else:
        print("   ✅ Old log directory was archived")
        
    archive_files = [f for f in os.listdir(archives_dir) if f.endswith(".zip")]
    print(f"   ✅ Created archive files: {', '.join(archive_files)}")
    
    # Print summary
    print("\n7. Log Management Summary")
    print("   ====================================")
    log_files = sum(len(files) for _, _, files in os.walk(session_dir))
    print(f"   ✅ Total log files in current session: {log_files}")
    print(f"   ✅ Session directory: {session_dir}")
    print(f"   ✅ Shared log file: {shared_log}")
    
    # Suggest viewing the logs
    print("\n🔍 Demo Complete! Next Steps:")
    print(f"   - View logs in: {session_dir}")
    print(f"   - Run tests: pytest tests/test_centralized_logger.py")
    print(f"   - Try the example: python examples/centralized_logger_demo.py")
    
if __name__ == "__main__":
    main() 