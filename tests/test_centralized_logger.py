#!/usr/bin/env python
"""
Tests for the centralized logging management system.

This module contains tests for the log rotation, timestamped directories,
session-based logging, and other features of the centralized log management system.
"""

import os
import sys
import time
import unittest
import logging
import tempfile
import shutil
import zipfile
from unittest.mock import patch, MagicMock

# Add the project root to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.logger import (
    # Centralized log management functions
    setup_centralized_logging,
    setup_component_logger,
    create_timestamped_log_file,
    setup_shared_rotating_file_logger,
    get_session_log_dir,
    cleanup_old_logs,
    compress_old_logs,
    get_log_manager,
    LogManager,
    DEFAULT_MAX_BYTES,
    DEFAULT_BACKUP_COUNT
)

class TestCentralizedLogger(unittest.TestCase):
    """Test cases for the centralized logging management system."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory for log testing
        self.test_log_dir = tempfile.mkdtemp()
        
        # Set up the centralized logging with our test directory
        self.log_manager = setup_centralized_logging(self.test_log_dir)
        
        # Track created files for cleanup
        self.created_files = []
    
    def tearDown(self):
        """Clean up after tests."""
        # Remove the temporary directory and all its contents
        shutil.rmtree(self.test_log_dir)
    
    def test_session_directory_creation(self):
        """Test that a session directory is created with the correct structure."""
        # Check if session directory exists
        session_dir = get_session_log_dir()
        self.assertTrue(os.path.exists(session_dir))
        
        # Check if subdirectories exist
        detailed_dir = os.path.join(session_dir, 'detailed')
        summary_dir = os.path.join(session_dir, 'summary')
        error_dir = os.path.join(session_dir, 'errors')
        
        self.assertTrue(os.path.exists(detailed_dir))
        self.assertTrue(os.path.exists(summary_dir))
        self.assertTrue(os.path.exists(error_dir))
    
    def test_component_logger_creation(self):
        """Test creating a component logger with all log types."""
        # Create a component logger
        component_name = "test.component"
        logger = setup_component_logger(component_name)
        
        # Log some messages
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        
        # Check if log files were created
        session_dir = get_session_log_dir()
        
        detailed_log = os.path.join(session_dir, 'detailed', f"{component_name.replace('.', '_')}.log")
        summary_log = os.path.join(session_dir, 'summary', f"{component_name.replace('.', '_')}_summary.log")
        error_log = os.path.join(session_dir, 'errors', f"{component_name.replace('.', '_')}_errors.log")
        
        self.assertTrue(os.path.exists(detailed_log))
        self.assertTrue(os.path.exists(summary_log))
        self.assertTrue(os.path.exists(error_log))
        
        # Check log file contents
        with open(detailed_log, 'r') as f:
            detailed_content = f.read()
            self.assertIn("Debug message", detailed_content)
            self.assertIn("Info message", detailed_content)
            
        with open(summary_log, 'r') as f:
            summary_content = f.read()
            self.assertIn("Info message", summary_content)
            
        with open(error_log, 'r') as f:
            error_content = f.read()
            self.assertIn("Error message", error_content)
            self.assertNotIn("Debug message", error_content)
    
    def test_partial_component_logger(self):
        """Test creating a component logger with only some log types."""
        # Create a component logger with only error logs
        component_name = "test.partial"
        logger = setup_component_logger(
            component_name,
            detailed=False,
            summary=False,
            errors=True
        )
        
        # Log some messages
        logger.debug("Debug message")
        logger.info("Info message")
        logger.error("Error message")
        
        # Check if error log file was created
        session_dir = get_session_log_dir()
        
        detailed_log = os.path.join(session_dir, 'detailed', f"{component_name.replace('.', '_')}.log")
        summary_log = os.path.join(session_dir, 'summary', f"{component_name.replace('.', '_')}_summary.log")
        error_log = os.path.join(session_dir, 'errors', f"{component_name.replace('.', '_')}_errors.log")
        
        self.assertFalse(os.path.exists(detailed_log))
        self.assertFalse(os.path.exists(summary_log))
        self.assertTrue(os.path.exists(error_log))
        
        # Check error log file contents
        with open(error_log, 'r') as f:
            error_content = f.read()
            self.assertIn("Error message", error_content)
            self.assertNotIn("Debug message", error_content)
            self.assertNotIn("Info message", error_content)
    
    def test_timestamped_log_file(self):
        """Test creating a timestamped log file."""
        # Create a timestamped log file
        filename_prefix = "test_timestamp"
        log_file = create_timestamped_log_file(filename_prefix)
        
        # Check if file exists
        self.assertTrue(os.path.exists(log_file))
        
        # Check if filename follows the expected pattern
        filename = os.path.basename(log_file)
        self.assertTrue(filename.startswith(filename_prefix))
        self.assertTrue(filename.endswith(".log"))
        
        # Extract timestamp part (format should be YYYYMMDD_HHMMSS)
        timestamp_part = filename[len(filename_prefix)+1:-4]  # Remove prefix, underscore, and .log
        self.assertEqual(len(timestamp_part), 15)  # YYYYMMDD_HHMMSS is 15 characters
        
        # Basic format check for the timestamp
        self.assertTrue(timestamp_part[8] == '_')  # Underscore separating date and time
        date_part = timestamp_part[:8]
        time_part = timestamp_part[9:]
        
        self.assertTrue(date_part.isdigit())
        self.assertTrue(time_part.isdigit())
    
    def test_rotating_file_handler(self):
        """Test the rotating file handler functionality."""
        # Get the LogManager instance
        log_manager = get_log_manager()
        
        # Create a rotating file handler with small max_bytes for testing
        test_log_file = os.path.join(self.test_log_dir, "rotation_test.log")
        small_max_bytes = 100  # Small size to trigger rotation easily
        handler = log_manager.get_rotating_file_handler(
            test_log_file,
            max_bytes=small_max_bytes,
            backup_count=2
        )
        
        # Create a logger and add the handler
        logger = logging.getLogger("test.rotation")
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
        
        # Write enough data to trigger rotation
        for i in range(20):
            logger.info(f"Test message {i} with some padding to make it longer than our small max_bytes")
        
        # Check if backup files were created
        self.assertTrue(os.path.exists(test_log_file))
        self.assertTrue(os.path.exists(f"{test_log_file}.1"))
        self.assertTrue(os.path.exists(f"{test_log_file}.2"))
        
        # Check if we don't exceed backup_count
        self.assertFalse(os.path.exists(f"{test_log_file}.3"))
    
    def test_timed_rotating_logger(self):
        """Test the timed rotating logger functionality."""
        # Get the LogManager instance
        log_manager = get_log_manager()
        
        # Create a timed rotating logger with short interval for testing
        test_log_file = os.path.join(self.test_log_dir, "timed_rotation_test.log")
        
        # Use seconds-based rotation for testing
        logger = log_manager.create_timed_rotating_logger(
            "test.timed_rotation",
            test_log_file,
            when='S',  # Seconds
            interval=1,  # Every second
            backup_count=2
        )
        
        # Write some initial logs
        logger.info("Initial log message")
        
        # Wait for rotation interval
        time.sleep(1.1)
        
        # Write more logs to trigger rotation
        logger.info("Message after first rotation")
        
        # Wait again
        time.sleep(1.1)
        
        # Write more logs to trigger second rotation
        logger.info("Message after second rotation")
        
        # Check if the main log file exists
        self.assertTrue(os.path.exists(test_log_file))
        
        # Note: Testing for backup files is tricky because their names include timestamps
        # We can count the number of log files in the directory
        log_files = [f for f in os.listdir(os.path.dirname(test_log_file)) 
                    if os.path.basename(test_log_file) in f]
        self.assertGreaterEqual(len(log_files), 1)
    
    @patch('os.path.getmtime')
    @patch('os.listdir')
    @patch('shutil.rmtree')
    @patch('os.remove')
    def test_cleanup_old_logs(self, mock_remove, mock_rmtree, mock_listdir, mock_getmtime):
        """Test the cleanup of old logs functionality."""
        # Set up mocks
        mock_listdir.return_value = ['old_dir', 'old_file.log', 'recent_dir', 'recent_file.log']
        
        # Mock file/directory type checks
        orig_isdir = os.path.isdir
        orig_isfile = os.path.isfile
        
        def mock_isdir(path):
            return os.path.basename(path) in ['old_dir', 'recent_dir']
            
        def mock_isfile(path):
            return os.path.basename(path) in ['old_file.log', 'recent_file.log']
        
        # Mock time checks - old items are older than retention period, recent ones are not
        def mock_mtime_func(path):
            if 'old' in os.path.basename(path):
                return time.time() - (31 * 24 * 60 * 60)  # 31 days old
            else:
                return time.time() - (10 * 24 * 60 * 60)  # 10 days old
                
        mock_getmtime.side_effect = mock_mtime_func
        
        with patch('os.path.isdir', side_effect=mock_isdir):
            with patch('os.path.isfile', side_effect=mock_isfile):
                # Run cleanup with 30-day retention
                removed = cleanup_old_logs(30)
        
        # Check that the correct items were removed
        self.assertEqual(removed, 2)  # Both old_dir and old_file.log should be removed
        
        # Check appropriate functions were called
        mock_rmtree.assert_called_once()
        mock_remove.assert_called_once()
        
        # Verify the removed paths
        old_dir_path = os.path.join(get_session_log_dir(), '../old_dir')
        old_file_path = os.path.join(get_session_log_dir(), '../old_file.log')
        
        self.assertEqual(mock_rmtree.call_args[0][0].endswith('old_dir'), True)
        self.assertEqual(mock_remove.call_args[0][0].endswith('old_file.log'), True)
    
    @patch('os.path.getmtime')
    @patch('os.listdir')
    @patch('os.path.exists')
    @patch('zipfile.ZipFile')
    @patch('shutil.rmtree')
    @patch('os.walk')
    def test_compress_old_logs(self, mock_walk, mock_rmtree, mock_zipfile, mock_exists, mock_listdir, mock_getmtime):
        """Test the compression of old logs functionality."""
        # Set up mocks
        mock_listdir.return_value = ['old_dir', 'old_file.log', 'recent_dir', 'recent_file.log']
        
        # Mock directory checks
        orig_isdir = os.path.isdir
        
        def mock_isdir(path):
            return os.path.basename(path) in ['old_dir', 'recent_dir']
            
        # Mock time checks
        def mock_mtime_func(path):
            if 'old' in os.path.basename(path):
                return time.time() - (10 * 24 * 60 * 60)  # 10 days old
            else:
                return time.time() - (3 * 24 * 60 * 60)  # 3 days old
                
        mock_getmtime.side_effect = mock_mtime_func
        
        # Mock walk function to simulate directory structure
        mock_walk.return_value = [
            ('/fake/path/old_dir', [], ['file1.log', 'file2.log']),
        ]
        
        # Mock zipfile operations
        mock_zipfile_instance = MagicMock()
        mock_zipfile.return_value.__enter__.return_value = mock_zipfile_instance
        
        # Mock exists check for zip file
        mock_exists.side_effect = lambda path: not path.endswith('.zip')
        
        with patch('os.path.isdir', side_effect=mock_isdir):
            # Run compression with 7-day threshold
            compressed = compress_old_logs(7)
        
        # Check that the correct items were compressed
        self.assertEqual(compressed, 1)  # Only old_dir should be compressed
        
        # Check appropriate functions were called
        mock_zipfile.assert_called_once()
        mock_rmtree.assert_called_once()
        
        # Verify the removed path
        old_dir_path = os.path.join(get_session_log_dir(), '../old_dir')
        self.assertEqual(mock_rmtree.call_args[0][0].endswith('old_dir'), True)
        
        # Verify that files were added to the zip
        self.assertEqual(mock_zipfile_instance.write.call_count, 2)  # Two files added

if __name__ == '__main__':
    unittest.main() 