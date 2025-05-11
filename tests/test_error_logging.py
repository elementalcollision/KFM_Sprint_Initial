"""
Unit tests for error logging functionality.

This module tests the error logging components that capture,
format and store error information for analysis and debugging.
"""

import unittest
import os
import json
import logging
import tempfile
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime

from src.llm_logging import ErrorLogger, LogLevel
from src.exceptions import (
    LLMAPIError,
    LLMNetworkError,
    LLMTimeoutError
)


class TestErrorLogging(unittest.TestCase):
    """Test suite for error logging functionality."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Create a temporary directory for log files
        self.temp_dir = tempfile.mkdtemp()
        
        # Configure the error logger to use the temporary directory
        self.log_file = os.path.join(self.temp_dir, "error_log.jsonl")
        self.error_logger = ErrorLogger(
            log_file_path=self.log_file,
            console_log_level=LogLevel.DEBUG,
            file_log_level=LogLevel.INFO
        )
        
        # Create a test error and context
        self.test_error = LLMNetworkError("Test network error")
        self.test_context = {
            "user_id": "test-user-123",
            "session_id": "test-session-456",
            "request_id": "test-request-789",
            "timestamp": datetime.now().isoformat(),
            "component": "test_component",
            "operation": "test_operation"
        }
    
    def tearDown(self):
        """Clean up after tests."""
        # Remove temporary files
        if os.path.exists(self.log_file):
            os.remove(self.log_file)
        
        # Remove temporary directory
        if os.path.exists(self.temp_dir):
            os.rmdir(self.temp_dir)
    
    def test_log_error_creates_file(self):
        """Test that log_error creates a log file if it doesn't exist."""
        # Ensure the file doesn't exist initially
        if os.path.exists(self.log_file):
            os.remove(self.log_file)
        
        # Log an error
        self.error_logger.log_error(
            error=self.test_error,
            error_context=self.test_context,
            level=LogLevel.ERROR
        )
        
        # Check that the file was created
        self.assertTrue(os.path.exists(self.log_file))
    
    def test_log_error_file_content(self):
        """Test that log_error writes the correct content to the file."""
        # Log an error
        self.error_logger.log_error(
            error=self.test_error,
            error_context=self.test_context,
            level=LogLevel.ERROR
        )
        
        # Read the log file
        with open(self.log_file, 'r') as f:
            log_line = f.readline().strip()
            log_data = json.loads(log_line)
        
        # Check that the log entry contains the expected fields
        self.assertEqual(log_data["error_type"], "LLMNetworkError")
        self.assertEqual(log_data["error_message"], "Test network error")
        self.assertEqual(log_data["level"], "ERROR")
        self.assertEqual(log_data["context"]["user_id"], "test-user-123")
        self.assertEqual(log_data["context"]["component"], "test_component")
    
    def test_log_error_with_different_levels(self):
        """Test logging errors with different severity levels."""
        # Log errors at different levels
        levels = [LogLevel.DEBUG, LogLevel.INFO, LogLevel.WARNING, LogLevel.ERROR, LogLevel.CRITICAL]
        
        for level in levels:
            self.error_logger.log_error(
                error=self.test_error,
                error_context=self.test_context,
                level=level
            )
        
        # Read the log file
        with open(self.log_file, 'r') as f:
            log_lines = f.readlines()
        
        # Check that we have multiple entries (only those at INFO level or higher should be in the file)
        self.assertEqual(len(log_lines), 4)  # INFO, WARNING, ERROR, CRITICAL
        
        # Check that each entry has the correct level
        expected_levels = [LogLevel.INFO.name, LogLevel.WARNING.name, LogLevel.ERROR.name, LogLevel.CRITICAL.name]
        for i, level in enumerate(expected_levels):
            log_data = json.loads(log_lines[i])
            self.assertEqual(log_data["level"], level)
    
    @patch('logging.Logger.debug')
    @patch('logging.Logger.info')
    @patch('logging.Logger.warning')
    @patch('logging.Logger.error')
    @patch('logging.Logger.critical')
    def test_console_logging(self, mock_critical, mock_error, mock_warning, mock_info, mock_debug):
        """Test that errors are logged to the console with the correct level."""
        # Log errors at different levels
        self.error_logger.log_error(
            error=self.test_error,
            error_context=self.test_context,
            level=LogLevel.DEBUG
        )
        self.error_logger.log_error(
            error=self.test_error,
            error_context=self.test_context,
            level=LogLevel.INFO
        )
        self.error_logger.log_error(
            error=self.test_error,
            error_context=self.test_context,
            level=LogLevel.WARNING
        )
        self.error_logger.log_error(
            error=self.test_error,
            error_context=self.test_context,
            level=LogLevel.ERROR
        )
        self.error_logger.log_error(
            error=self.test_error,
            error_context=self.test_context,
            level=LogLevel.CRITICAL
        )
        
        # Check that each log method was called once
        mock_debug.assert_called_once()
        mock_info.assert_called_once()
        mock_warning.assert_called_once()
        mock_error.assert_called_once()
        mock_critical.assert_called_once()
    
    def test_log_error_with_traceback(self):
        """Test logging errors with traceback information."""
        # Create an error with traceback
        try:
            raise LLMTimeoutError("Test timeout error")
        except LLMTimeoutError as e:
            error_with_traceback = e
        
        # Log the error
        self.error_logger.log_error(
            error=error_with_traceback,
            error_context=self.test_context,
            level=LogLevel.ERROR,
            include_traceback=True
        )
        
        # Read the log file
        with open(self.log_file, 'r') as f:
            log_line = f.readline().strip()
            log_data = json.loads(log_line)
        
        # Check that the traceback is included
        self.assertIn("traceback", log_data)
        self.assertIn("test_error_logging.py", log_data["traceback"])
    
    def test_log_error_without_traceback(self):
        """Test logging errors without traceback information."""
        # Log an error without traceback
        self.error_logger.log_error(
            error=self.test_error,
            error_context=self.test_context,
            level=LogLevel.ERROR,
            include_traceback=False
        )
        
        # Read the log file
        with open(self.log_file, 'r') as f:
            log_line = f.readline().strip()
            log_data = json.loads(log_line)
        
        # Check that the traceback is not included
        self.assertNotIn("traceback", log_data)
    
    def test_log_error_with_custom_formatter(self):
        """Test logging errors with a custom formatter."""
        # Define a custom formatter
        def custom_formatter(error, context, level, traceback=None):
            return {
                "custom_error_type": type(error).__name__,
                "custom_message": str(error),
                "custom_level": level.name,
                "custom_context": context,
                "timestamp": datetime.now().isoformat()
            }
        
        # Create a logger with the custom formatter
        custom_logger = ErrorLogger(
            log_file_path=os.path.join(self.temp_dir, "custom_log.jsonl"),
            console_log_level=LogLevel.WARNING,
            file_log_level=LogLevel.WARNING,
            formatter=custom_formatter
        )
        
        # Log an error
        custom_logger.log_error(
            error=self.test_error,
            error_context=self.test_context,
            level=LogLevel.WARNING
        )
        
        # Read the log file
        with open(os.path.join(self.temp_dir, "custom_log.jsonl"), 'r') as f:
            log_line = f.readline().strip()
            log_data = json.loads(log_line)
        
        # Check that the custom formatter was used
        self.assertIn("custom_error_type", log_data)
        self.assertEqual(log_data["custom_error_type"], "LLMNetworkError")
        self.assertIn("custom_message", log_data)
        self.assertIn("custom_level", log_data)
        self.assertIn("custom_context", log_data)
    
    def test_log_error_batch(self):
        """Test batch logging of multiple errors."""
        # Create multiple errors
        errors = [
            LLMNetworkError("Network error 1"),
            LLMTimeoutError("Timeout error"),
            LLMAPIError("API error"),
            LLMNetworkError("Network error 2")
        ]
        
        # Log errors in batch
        self.error_logger.log_error_batch(
            errors=errors,
            error_context=self.test_context,
            level=LogLevel.ERROR
        )
        
        # Read the log file
        with open(self.log_file, 'r') as f:
            log_lines = f.readlines()
        
        # Check that we have one entry per error
        self.assertEqual(len(log_lines), len(errors))
        
        # Check that each error was logged correctly
        error_types = [json.loads(line)["error_type"] for line in log_lines]
        self.assertEqual(error_types, ["LLMNetworkError", "LLMTimeoutError", "LLMAPIError", "LLMNetworkError"])
    
    def test_get_logs(self):
        """Test retrieving logs from the log file."""
        # Log multiple errors
        for i in range(5):
            self.error_logger.log_error(
                error=LLMNetworkError(f"Network error {i}"),
                error_context=self.test_context,
                level=LogLevel.ERROR
            )
        
        # Retrieve all logs
        logs = self.error_logger.get_logs()
        
        # Check that we have all entries
        self.assertEqual(len(logs), 5)
        
        # Check that the entries have the correct content
        for i, log in enumerate(logs):
            self.assertEqual(log["error_type"], "LLMNetworkError")
            self.assertEqual(log["error_message"], f"Network error {i}")
    
    def test_get_logs_with_filter(self):
        """Test retrieving logs with filtering."""
        # Log errors of different types
        self.error_logger.log_error(
            error=LLMNetworkError("Network error"),
            error_context=self.test_context,
            level=LogLevel.ERROR
        )
        self.error_logger.log_error(
            error=LLMTimeoutError("Timeout error"),
            error_context=self.test_context,
            level=LogLevel.WARNING
        )
        self.error_logger.log_error(
            error=LLMAPIError("API error"),
            error_context=self.test_context,
            level=LogLevel.ERROR
        )
        
        # Define a filter function
        def network_error_filter(log_entry):
            return log_entry["error_type"] == "LLMNetworkError"
        
        # Retrieve filtered logs
        logs = self.error_logger.get_logs(filter_func=network_error_filter)
        
        # Check that we have only the network error
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["error_type"], "LLMNetworkError")
        self.assertEqual(logs[0]["error_message"], "Network error")
    
    def test_get_logs_with_limit(self):
        """Test retrieving logs with a limit."""
        # Log multiple errors
        for i in range(10):
            self.error_logger.log_error(
                error=LLMNetworkError(f"Network error {i}"),
                error_context=self.test_context,
                level=LogLevel.ERROR
            )
        
        # Retrieve limited logs
        logs = self.error_logger.get_logs(limit=5)
        
        # Check that we have the correct number of logs
        self.assertEqual(len(logs), 5)
    
    def test_get_error_stats(self):
        """Test retrieving error statistics."""
        # Log errors of different types
        for _ in range(3):
            self.error_logger.log_error(
                error=LLMNetworkError("Network error"),
                error_context=self.test_context,
                level=LogLevel.ERROR
            )
        
        for _ in range(2):
            self.error_logger.log_error(
                error=LLMTimeoutError("Timeout error"),
                error_context=self.test_context,
                level=LogLevel.WARNING
            )
        
        self.error_logger.log_error(
            error=LLMAPIError("API error"),
            error_context=self.test_context,
            level=LogLevel.CRITICAL
        )
        
        # Get error statistics
        stats = self.error_logger.get_error_stats()
        
        # Check the statistics
        self.assertEqual(stats["total_errors"], 6)
        self.assertEqual(stats["error_types"]["LLMNetworkError"], 3)
        self.assertEqual(stats["error_types"]["LLMTimeoutError"], 2)
        self.assertEqual(stats["error_types"]["LLMAPIError"], 1)
        self.assertEqual(stats["error_levels"]["ERROR"], 3)
        self.assertEqual(stats["error_levels"]["WARNING"], 2)
        self.assertEqual(stats["error_levels"]["CRITICAL"], 1)
    
    def test_rotating_log_files(self):
        """Test automatic rotation of log files."""
        # Create a logger with a small max file size
        rotating_logger = ErrorLogger(
            log_file_path=os.path.join(self.temp_dir, "rotating_log.jsonl"),
            console_log_level=LogLevel.WARNING,
            file_log_level=LogLevel.WARNING,
            max_file_size_kb=1,  # Very small to trigger rotation
            backup_count=3
        )
        
        # Log enough errors to trigger rotation
        large_context = {"large_field": "x" * 500}  # Make the log entry larger
        for i in range(10):
            rotating_logger.log_error(
                error=LLMNetworkError(f"Network error {i}"),
                error_context=large_context,
                level=LogLevel.WARNING
            )
        
        # Check that backup files were created
        base_path = os.path.join(self.temp_dir, "rotating_log.jsonl")
        self.assertTrue(os.path.exists(base_path))
        
        # At least one backup should exist
        backup_files = [f for f in os.listdir(self.temp_dir) if f.startswith("rotating_log.jsonl.") and f.endswith(".backup")]
        self.assertGreater(len(backup_files), 0)


if __name__ == '__main__':
    unittest.main() 