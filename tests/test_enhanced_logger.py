"""
Tests for the enhanced logger functionality.
"""

import os
import json
import tempfile
import unittest
import logging
from unittest.mock import patch, MagicMock

from src.logger import (
    setup_logger,
    set_log_level,
    get_log_level,
    get_log_level_name,
    load_config_from_file,
    save_config_to_file,
    get_current_config,
    set_all_loggers_level,
    setup_shared_file_logger,
    list_configured_loggers,
    # New imports for structured logging
    set_log_format,
    set_colored_output,
    add_log_filter,
    remove_log_filter,
    clear_log_filters,
    exclude_module,
    include_module,
    clear_module_exclusions,
    JSONFormatter,
    ColorFormatter,
    LogFilter,
    ModuleFilter
)

class EnhancedLoggerTests(unittest.TestCase):
    """Test cases for the enhanced logger functionality."""
    
    def setUp(self):
        """Set up the test environment."""
        # Create a temp directory for log files
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "test_config.json")
        
        # Save original environment
        self.original_env = os.environ.copy()
        
        # Reset any module-level logger configurations
        set_all_loggers_level("INFO")
        set_log_format(False)
        set_colored_output(True)
        clear_log_filters()
        clear_module_exclusions()
    
    def tearDown(self):
        """Clean up after the tests."""
        # Remove temp directory
        for f in os.listdir(self.temp_dir):
            os.remove(os.path.join(self.temp_dir, f))
        os.rmdir(self.temp_dir)
        
        # Restore original environment
        os.environ.clear()
        os.environ.update(self.original_env)
    
    def test_setup_logger(self):
        """Test the basic logger setup."""
        logger = setup_logger("test_logger")
        self.assertEqual(logger.level, logging.INFO)
        
        debug_logger = setup_logger("debug_logger", level="DEBUG")
        self.assertEqual(debug_logger.level, logging.DEBUG)
    
    def test_set_log_level(self):
        """Test changing log levels at runtime."""
        logger_name = "test_level_logger"
        logger = setup_logger(logger_name)
        
        # Check default level
        self.assertEqual(logger.level, logging.INFO)
        
        # Change level to DEBUG
        set_log_level(logger_name, "DEBUG")
        self.assertEqual(logger.level, logging.DEBUG)
        
        # Change level to WARNING
        set_log_level(logger_name, logging.WARNING)
        self.assertEqual(logger.level, logging.WARNING)
    
    def test_level_name_conversion(self):
        """Test converting between level names and numeric values."""
        # Name to number
        self.assertEqual(get_log_level("DEBUG"), logging.DEBUG)
        self.assertEqual(get_log_level("INFO"), logging.INFO)
        self.assertEqual(get_log_level("WARNING"), logging.WARNING)
        self.assertEqual(get_log_level("ERROR"), logging.ERROR)
        self.assertEqual(get_log_level("CRITICAL"), logging.CRITICAL)
        
        # Number to name
        self.assertEqual(get_log_level_name(logging.DEBUG), "DEBUG")
        self.assertEqual(get_log_level_name(logging.INFO), "INFO")
        self.assertEqual(get_log_level_name(logging.WARNING), "WARNING")
        self.assertEqual(get_log_level_name(logging.ERROR), "ERROR")
        self.assertEqual(get_log_level_name(logging.CRITICAL), "CRITICAL")
    
    def test_config_file_operations(self):
        """Test saving and loading configuration from a file."""
        # Create a logger with non-default settings
        logger_name = "test_config_logger"
        logger = setup_logger(logger_name)
        set_log_level(logger_name, "DEBUG")
        
        # Save config to file
        self.assertTrue(save_config_to_file(self.config_file))
        
        # Modify the configuration
        set_log_level(logger_name, "WARNING")
        self.assertEqual(logger.level, logging.WARNING)
        
        # Load the saved configuration
        self.assertTrue(load_config_from_file(self.config_file))
        
        # Verify the level is updated based on the loaded config
        config = get_current_config()
        self.assertEqual(config['module_levels'][logger_name], "DEBUG")
    
    def test_set_all_loggers_level(self):
        """Test setting all loggers to a specific level."""
        # Create multiple loggers with different levels
        logger1 = setup_logger("test_all_1")
        logger2 = setup_logger("test_all_2", level="DEBUG")
        logger3 = setup_logger("test_all_3", level="WARNING")
        
        # Set all to ERROR level
        set_all_loggers_level("ERROR")
        
        # Verify all loggers are at ERROR level
        self.assertEqual(logger1.level, logging.ERROR)
        self.assertEqual(logger2.level, logging.ERROR)
        self.assertEqual(logger3.level, logging.ERROR)
    
    def test_environment_variable_config(self):
        """Test configuration from environment variables."""
        # Set environment variables
        os.environ['LOG_LEVEL'] = 'DEBUG'
        os.environ['LOG_LEVEL_TEST_ENV'] = 'WARNING'
        
        # Create loggers after environment variables are set
        # This would normally be handled by load_config_from_env()
        from src.logger import load_config_from_env
        load_config_from_env()
        
        # Create a logger that should inherit the default level
        logger = setup_logger("test_env_logger")
        
        # Create a logger with a specific module-level set in env
        module_logger = setup_logger("test_env")
        
        # Verify levels are set from environment variables
        config = get_current_config()
        self.assertEqual(config['default_level'], 'DEBUG')
        self.assertEqual(config['module_levels']['test_env'], 'WARNING')
    
    def test_list_configured_loggers(self):
        """Test listing all configured loggers."""
        # Create some loggers
        logger1 = setup_logger("test_list_1", level="DEBUG")
        logger2 = setup_logger("test_list_2", level="WARNING")
        
        # Get the list
        loggers = list_configured_loggers()
        
        # Verify loggers are in the list
        logger_names = [info['name'] for info in loggers]
        self.assertIn("test_list_1", logger_names)
        self.assertIn("test_list_2", logger_names)
        
        # Verify levels are correct
        for info in loggers:
            if info['name'] == "test_list_1":
                self.assertEqual(info['level'], "DEBUG")
            elif info['name'] == "test_list_2":
                self.assertEqual(info['level'], "WARNING")
    
    @patch('logging.FileHandler')
    def test_shared_file_logger(self, mock_file_handler):
        """Test setting up a shared file logger."""
        # Setup a mock file handler
        mock_instance = MagicMock()
        mock_file_handler.return_value = mock_instance
        
        # Call the function
        log_file = "shared.log"
        setup_shared_file_logger(log_file, level="WARNING")
        
        # Verify the handler was created and added to root logger
        mock_file_handler.assert_called_once()
        
        # Verify the handler was configured at the right level
        self.assertEqual(mock_instance.setLevel.call_args[0][0], logging.WARNING)

    def test_json_formatter(self):
        """Test the JSON formatter."""
        # Create a record
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        # Format the record
        formatter = JSONFormatter()
        formatted = formatter.format(record)
        
        # Parse and verify
        data = json.loads(formatted)
        self.assertEqual(data['level'], "INFO")
        self.assertEqual(data['message'], "Test message")
        self.assertEqual(data['function'], "")
        self.assertEqual(data['line'], 42)
        self.assertEqual(data['logger'], "test_logger")
        
        # Test with exception
        try:
            raise ValueError("Test exception")
        except ValueError:
            record.exc_info = sys.exc_info()
            formatter = JSONFormatter()
            formatted = formatter.format(record)
            data = json.loads(formatted)
            self.assertIn('exception', data)
            self.assertEqual(data['exception']['type'], "ValueError")
            self.assertEqual(data['exception']['message'], "Test exception")

    @patch('sys.stdout.isatty', return_value=True)
    def test_color_formatter(self, mock_isatty):
        """Test the color formatter."""
        # Create records for different levels
        info_record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="INFO message",
            args=(),
            exc_info=None
        )
        
        error_record = logging.LogRecord(
            name="test_logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=42,
            msg="ERROR message",
            args=(),
            exc_info=None
        )
        
        # Format the records
        formatter = ColorFormatter("%(levelname)s: %(message)s")
        info_formatted = formatter.format(info_record)
        error_formatted = formatter.format(error_record)
        
        # Verify color codes are in the output
        from src.logger import COLORS
        self.assertIn(COLORS['INFO'], info_formatted)
        self.assertIn(COLORS['ERROR'], error_formatted)
        self.assertIn(COLORS['RESET'], info_formatted)
        self.assertIn(COLORS['RESET'], error_formatted)
        
        # Test with colors disabled
        formatter = ColorFormatter("%(levelname)s: %(message)s", use_colors=False)
        info_formatted = formatter.format(info_record)
        self.assertNotIn(COLORS['INFO'], info_formatted)

    def test_log_filter(self):
        """Test the log message filter."""
        # Create a filter
        log_filter = LogFilter("test")
        
        # Create matching and non-matching records
        matching_record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="This is a test message",
            args=(),
            exc_info=None
        )
        
        non_matching_record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="This doesn't match",
            args=(),
            exc_info=None
        )
        
        # Test filter function
        self.assertTrue(log_filter.filter(matching_record))
        self.assertFalse(log_filter.filter(non_matching_record))

    def test_module_filter(self):
        """Test the module filter."""
        # Create a filter
        module_filter = ModuleFilter(["test\\.excluded", "another\\.excluded"])
        
        # Create matching and non-matching records
        excluded_record1 = logging.LogRecord(
            name="test.excluded.module",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="This should be excluded",
            args=(),
            exc_info=None
        )
        
        excluded_record2 = logging.LogRecord(
            name="another.excluded.module",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="This should also be excluded",
            args=(),
            exc_info=None
        )
        
        included_record = logging.LogRecord(
            name="test.included.module",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="This should be included",
            args=(),
            exc_info=None
        )
        
        # Test filter function
        self.assertFalse(module_filter.filter(excluded_record1))
        self.assertFalse(module_filter.filter(excluded_record2))
        self.assertTrue(module_filter.filter(included_record))

    def test_set_log_format(self):
        """Test setting log format globally."""
        # Get initial format setting
        config_before = get_current_config()
        initial_json_format = config_before['json_format']
        
        # Toggle json format
        set_log_format(not initial_json_format)
        
        # Verify the change
        config_after = get_current_config()
        self.assertEqual(config_after['json_format'], not initial_json_format)
        
        # Reset to original
        set_log_format(initial_json_format)

    def test_set_colored_output(self):
        """Test setting colored output globally."""
        # Get initial color setting
        config_before = get_current_config()
        initial_color = config_before['colored_output']
        
        # Toggle color setting
        set_colored_output(not initial_color)
        
        # Verify the change
        config_after = get_current_config()
        self.assertEqual(config_after['colored_output'], not initial_color)
        
        # Reset to original
        set_colored_output(initial_color)

    def test_add_remove_log_filter(self):
        """Test adding and removing log filters."""
        # Initial state
        config_before = get_current_config()
        self.assertEqual(len(config_before.get('filters', [])), 0)
        
        # Add a filter
        add_log_filter("test.*pattern")
        
        # Verify filter was added
        config_after_add = get_current_config()
        self.assertEqual(len(config_after_add['filters']), 1)
        self.assertEqual(config_after_add['filters'][0], "test.*pattern")
        
        # Remove the filter
        self.assertTrue(remove_log_filter("test.*pattern"))
        
        # Verify filter was removed
        config_after_remove = get_current_config()
        self.assertEqual(len(config_after_remove.get('filters', [])), 0)
        
        # Try to remove non-existent filter
        self.assertFalse(remove_log_filter("non_existent_pattern"))

    def test_clear_log_filters(self):
        """Test clearing all log filters."""
        # Add multiple filters
        add_log_filter("pattern1")
        add_log_filter("pattern2")
        
        # Verify filters were added
        config_after_add = get_current_config()
        self.assertEqual(len(config_after_add['filters']), 2)
        
        # Clear filters
        clear_log_filters()
        
        # Verify filters were cleared
        config_after_clear = get_current_config()
        self.assertEqual(len(config_after_clear.get('filters', [])), 0)

    def test_exclude_include_module(self):
        """Test excluding and including modules."""
        # Initial state
        config_before = get_current_config()
        self.assertEqual(len(config_before.get('excluded_modules', [])), 0)
        
        # Exclude a module
        exclude_module("test\\.excluded")
        
        # Verify module was excluded
        config_after_exclude = get_current_config()
        self.assertEqual(len(config_after_exclude['excluded_modules']), 1)
        self.assertEqual(config_after_exclude['excluded_modules'][0], "test\\.excluded")
        
        # Include the module
        self.assertTrue(include_module("test\\.excluded"))
        
        # Verify module was included
        config_after_include = get_current_config()
        self.assertEqual(len(config_after_include.get('excluded_modules', [])), 0)
        
        # Try to include non-existent module
        self.assertFalse(include_module("non_existent"))

    def test_clear_module_exclusions(self):
        """Test clearing all module exclusions."""
        # Exclude multiple modules
        exclude_module("module1")
        exclude_module("module2")
        
        # Verify modules were excluded
        config_after_exclude = get_current_config()
        self.assertEqual(len(config_after_exclude['excluded_modules']), 2)
        
        # Clear exclusions
        clear_module_exclusions()
        
        # Verify exclusions were cleared
        config_after_clear = get_current_config()
        self.assertEqual(len(config_after_clear.get('excluded_modules', [])), 0)

    @patch('src.logger.load_config_from_env')
    def test_log_format_env_vars(self, mock_load_env):
        """Test environment variables for log format settings."""
        # Set environment variables
        os.environ['LOG_JSON'] = 'true'
        os.environ['LOG_COLOR'] = 'false'
        os.environ['LOG_FILTERS'] = 'pattern1,pattern2'
        os.environ['LOG_EXCLUDE_MODULES'] = 'module1,module2'
        
        # Call load_config_from_env directly since we mocked it above
        from src.logger import load_config_from_env
        load_config_from_env()
        
        # Verify config was updated
        config = get_current_config()
        self.assertTrue(config['json_format'])
        self.assertFalse(config['colored_output'])
        self.assertEqual(len(config['filters']), 2)
        self.assertEqual(len(config['excluded_modules']), 2)


if __name__ == '__main__':
    unittest.main() 