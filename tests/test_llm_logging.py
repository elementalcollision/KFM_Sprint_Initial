"""
Tests for the llm_logging module that provides structured logging for LLM API calls.
"""

import unittest
import json
import time
from unittest.mock import patch, MagicMock
import logging

# Import the module under test
from src.llm_logging import (
    create_request_context,
    create_timer,
    calculate_performance_metrics,
    sanitize_log_data,
    sanitize_prompt_response,
    log_request,
    log_response,
    log_api_error,
    llm_api_logger,
    regular_logger
)
from src.exceptions import LLMAPIError, LLMTimeoutError


class TestLLMLogging(unittest.TestCase):
    """Test cases for the llm_logging module."""
    
    def setUp(self):
        """Setup for tests."""
        # Create a test context
        self.test_context = {
            'request_id': 'test-123',
            'timestamp': '2023-01-01T12:00:00',
            'operation_type': 'reflection',
            'model_name': 'test-model'
        }
        
        # Create test request data
        self.test_request = {
            'model_name': 'test-model',
            'temperature': 0.5,
            'max_output_tokens': 1024,
            'prompt_length': 500
        }
        
        # Create test sensitive data
        self.sensitive_data = {
            'api_key': 'sk-12345secret',
            'password': 'password123',
            'regular_data': 'this is fine'
        }
        
        # Create a test error
        self.test_error = LLMTimeoutError("Test timeout error")
    
    def test_create_request_context(self):
        """Test that create_request_context returns a valid context dictionary."""
        context = create_request_context(
            operation_type='test_operation',
            model_name='test-model',
            session_id='session-123',
            user_id='user-456'
        )
        
        # Check required fields
        self.assertIn('request_id', context)
        self.assertIn('timestamp', context)
        self.assertEqual(context['operation_type'], 'test_operation')
        self.assertEqual(context['model_name'], 'test-model')
        self.assertEqual(context['session_id'], 'session-123')
        self.assertEqual(context['user_id'], 'user-456')
    
    def test_create_timer(self):
        """Test that create_timer returns a usable timer."""
        start_time, get_elapsed = create_timer()
        
        # Check that start_time is a float
        self.assertIsInstance(start_time, float)
        
        # Wait a small amount of time
        time.sleep(0.01)
        
        # Check that get_elapsed returns a non-zero value
        elapsed = get_elapsed()
        self.assertGreater(elapsed, 0)
    
    def test_calculate_performance_metrics(self):
        """Test that calculate_performance_metrics returns the expected metrics."""
        metrics = calculate_performance_metrics(
            prompt_length=1000,
            response_length=500,
            duration=2.5
        )
        
        # Check required metrics
        self.assertEqual(metrics['prompt_length'], 1000)
        self.assertEqual(metrics['response_length'], 500)
        self.assertEqual(metrics['duration_seconds'], 2.5)
        
        # Check calculated metrics
        self.assertEqual(metrics['estimated_prompt_tokens'], 250)  # 1000/4
        self.assertEqual(metrics['estimated_response_tokens'], 125)  # 500/4
        self.assertEqual(metrics['estimated_total_tokens'], 375)  # 250+125
        self.assertEqual(metrics['chars_per_second'], 200)  # 500/2.5
        self.assertEqual(metrics['estimated_tokens_per_second'], 50)  # 125/2.5
    
    def test_sanitize_log_data(self):
        """Test that sanitize_log_data properly redacts sensitive information."""
        sanitized = sanitize_log_data(self.sensitive_data)
        
        # Check that sensitive keys are redacted
        self.assertEqual(sanitized['api_key'], "*** REDACTED ***")
        self.assertEqual(sanitized['password'], "*** REDACTED ***")
        
        # Check that regular data is unchanged
        self.assertEqual(sanitized['regular_data'], "this is fine")
        
        # Test with nested dictionaries
        nested_data = {
            'outer': {
                'api_key': 'secret',
                'safe': 'data'
            }
        }
        sanitized_nested = sanitize_log_data(nested_data)
        self.assertEqual(sanitized_nested['outer']['api_key'], "*** REDACTED ***")
        self.assertEqual(sanitized_nested['outer']['safe'], "data")
        
        # Test with long strings
        long_text = "a" * 2000
        sanitized_long = sanitize_log_data(long_text)
        self.assertIn("... [truncated", sanitized_long)
        self.assertLess(len(sanitized_long), 2000)
    
    def test_sanitize_prompt_response(self):
        """Test that sanitize_prompt_response properly truncates long text."""
        # Test with short text
        short_text = "This is a short text"
        self.assertEqual(sanitize_prompt_response(short_text), short_text)
        
        # Test with long text
        long_text = "a" * 2000
        sanitized = sanitize_prompt_response(long_text, max_length=1000)
        self.assertIn("... [truncated", sanitized)
        self.assertLess(len(sanitized), 2000)
        
        # Test with None
        self.assertEqual(sanitize_prompt_response(None), "")
    
    @patch('src.llm_logging.llm_api_logger')
    @patch('src.llm_logging.regular_logger')
    def test_log_request(self, mock_regular_logger, mock_llm_api_logger):
        """Test that log_request logs to both loggers with the correct format."""
        # Call the function
        log_request(
            context=self.test_context,
            request_data=self.test_request,
            additional_context={'extra': 'data'}
        )
        
        # Check that both loggers were called
        mock_llm_api_logger.info.assert_called_once()
        mock_regular_logger.info.assert_called_once()
        
        # Check the JSON log format
        json_log = mock_llm_api_logger.info.call_args[0][0]
        log_data = json.loads(json_log)
        
        # Verify structure
        self.assertEqual(log_data['event'], 'llm_request')
        self.assertEqual(log_data['context'], self.test_context)
        self.assertEqual(log_data['request']['model_name'], 'test-model')
        self.assertEqual(log_data['additional_context']['extra'], 'data')
        
        # Check regular log format
        regular_log = mock_regular_logger.info.call_args[0][0]
        self.assertIn('LLM REQUEST', regular_log)
        self.assertIn('test-123', regular_log)
        self.assertIn('reflection', regular_log)
    
    @patch('src.llm_logging.llm_api_logger')
    @patch('src.llm_logging.regular_logger')
    def test_log_response(self, mock_regular_logger, mock_llm_api_logger):
        """Test that log_response logs to both loggers with the correct format."""
        # Call the function with string response
        log_response(
            context=self.test_context,
            response_data="This is a test response",
            duration=1.5,
            status='success',
            additional_metrics={'tokens': 100}
        )
        
        # Check that both loggers were called
        mock_llm_api_logger.info.assert_called_once()
        mock_regular_logger.info.assert_called_once()
        
        # Check the JSON log format
        json_log = mock_llm_api_logger.info.call_args[0][0]
        log_data = json.loads(json_log)
        
        # Verify structure
        self.assertEqual(log_data['event'], 'llm_response')
        self.assertEqual(log_data['context'], self.test_context)
        self.assertEqual(log_data['response']['status'], 'success')
        self.assertEqual(log_data['response']['text_preview'], "This is a test response")
        self.assertEqual(log_data['metrics']['tokens'], 100)
        self.assertEqual(log_data['metrics']['duration_seconds'], 1.5)
        
        # Check regular log format
        regular_log = mock_regular_logger.info.call_args[0][0]
        self.assertIn('LLM RESPONSE', regular_log)
        self.assertIn('test-123', regular_log)
        self.assertIn('Success', regular_log)
    
    @patch('src.llm_logging.llm_api_logger')
    @patch('src.llm_logging.regular_logger')
    def test_log_api_error(self, mock_regular_logger, mock_llm_api_logger):
        """Test that log_api_error logs to both loggers with the correct format."""
        # Call the function
        log_api_error(
            context=self.test_context,
            error=self.test_error,
            duration=2.0,
            attempt=2,
            max_attempts=3,
            retry_after=5.0,
            request_data=self.test_request
        )
        
        # Check that both loggers were called
        mock_llm_api_logger.error.assert_called_once()
        mock_regular_logger.error.assert_called_once()
        
        # Check the JSON log format
        json_log = mock_llm_api_logger.error.call_args[0][0]
        log_data = json.loads(json_log)
        
        # Verify structure
        self.assertEqual(log_data['event'], 'llm_error')
        self.assertEqual(log_data['context'], self.test_context)
        self.assertEqual(log_data['error']['type'], 'LLMTimeoutError')
        self.assertEqual(log_data['error']['message'], 'Test timeout error')
        self.assertEqual(log_data['duration_seconds'], 2.0)
        self.assertEqual(log_data['retry']['attempt'], 2)
        self.assertEqual(log_data['retry']['max_attempts'], 3)
        self.assertEqual(log_data['retry']['retry_after'], 5.0)
        self.assertEqual(log_data['retry']['is_final_attempt'], False)
        self.assertEqual(log_data['request']['model_name'], 'test-model')
        
        # Check regular log format
        regular_log = mock_regular_logger.error.call_args[0][0]
        self.assertIn('LLM ERROR', regular_log)
        self.assertIn('test-123', regular_log)
        self.assertIn('LLMTimeoutError', regular_log)
        self.assertIn('attempt 2/3', regular_log)


if __name__ == '__main__':
    unittest.main() 