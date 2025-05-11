"""
Tests for the enhanced call_llm_for_reflection_v2 function with comprehensive logging.
"""

import unittest
from unittest.mock import patch, MagicMock, ANY
import json
import time
import uuid

# Add necessary imports
from src.langgraph_nodes import call_llm_for_reflection_v2, generate_error_reflection
from src.exceptions import (
    LLMAPIError,
    LLMTimeoutError,
    LLMConnectionError,
    LLMRateLimitError,
    LLMAuthenticationError
)


class TestEnhancedLLMReflectionV2(unittest.TestCase):
    """Test cases for the updated call_llm_for_reflection_v2 function with enhanced logging."""
    
    def setUp(self):
        """Setup for tests."""
        # Create a test state
        self.test_state = {
            'kfm_action': {
                'action': 'test',
                'component': 'test_component'
            },
            'active_component': 'test_component',
            'result': {'test': 'value'},
            'execution_performance': {
                'latency': 0.5,
                'accuracy': 0.95
            }
        }
        
        # Mock successful response
        self.successful_response = MagicMock()
        self.successful_response.text = "This is a successful reflection."
        
        # Setup patches
        self.patcher_dotenv = patch('src.langgraph_nodes.load_dotenv')
        self.patcher_logger = patch('src.langgraph_nodes.reflect_logger')
        self.patcher_genai = patch('src.langgraph_nodes.genai')
        self.patcher_create_context = patch('src.langgraph_nodes.create_request_context')
        self.patcher_log_request = patch('src.langgraph_nodes.log_request')
        self.patcher_log_response = patch('src.langgraph_nodes.log_response')
        self.patcher_log_error = patch('src.langgraph_nodes.log_api_error')
        self.patcher_timer = patch('src.langgraph_nodes.create_timer')
        self.patcher_metrics = patch('src.langgraph_nodes.calculate_performance_metrics')
        self.patcher_get_prompt = patch('src.langgraph_nodes.get_reflection_prompt', return_value="Test reflection prompt")
        self.patcher_generate_error = patch('src.langgraph_nodes.generate_error_reflection', return_value="Test error reflection")
        
        # Start patches
        self.mock_dotenv = self.patcher_dotenv.start()
        self.mock_logger = self.patcher_logger.start()
        self.mock_genai = self.patcher_genai.start()
        self.mock_create_context = self.patcher_create_context.start()
        self.mock_log_request = self.patcher_log_request.start()
        self.mock_log_response = self.patcher_log_response.start()
        self.mock_log_error = self.patcher_log_error.start()
        self.mock_timer = self.patcher_timer.start()
        self.mock_metrics = self.patcher_metrics.start()
        self.mock_get_prompt = self.patcher_get_prompt.start()
        self.mock_generate_error = self.patcher_generate_error.start()
        
        # Configure mocks
        self.mock_model = MagicMock()
        self.mock_model.generate_content.return_value = self.successful_response
        self.mock_genai.GenerativeModel.return_value = self.mock_model
        
        # Mock environment
        self.mock_env = {'GOOGLE_API_KEY': 'test-api-key'}
        self.mock_os_getenv = patch('os.getenv', side_effect=lambda k: self.mock_env.get(k)).start()
        
        # Configure timer
        self.elapsed_time = 0.5
        def fake_timer():
            start_time = time.time()
            def get_elapsed():
                return self.elapsed_time
            return start_time, get_elapsed
        self.mock_timer.side_effect = fake_timer
        
        # Configure context
        test_context = {
            'request_id': 'test-123',
            'timestamp': '2023-01-01T12:00:00',
            'operation_type': 'reflection',
            'model_name': 'gemini-2.0-flash'
        }
        self.mock_create_context.return_value = test_context
        
        # Configure metrics
        self.mock_metrics.return_value = {
            'duration_seconds': 0.5,
            'estimated_tokens_per_second': 100,
            'chars_per_second': 400
        }
    
    def tearDown(self):
        """Clean up patches."""
        patch.stopall()
    
    def test_successful_api_call_logs_correctly(self):
        """Test that a successful API call logs properly using the new utilities."""
        # Call the function
        result = call_llm_for_reflection_v2(self.test_state)
        
        # Check result
        self.assertEqual(result, "This is a successful reflection.")
        
        # Verify request context was created
        self.mock_create_context.assert_called_once_with(
            operation_type="reflection",
            model_name="gemini-2.0-flash"
        )
        
        # Verify request was logged
        self.mock_log_request.assert_called_once()
        
        # Verify successful response was logged
        self.mock_log_response.assert_called_once()
        _, kwargs = self.mock_log_response.call_args
        self.assertEqual(kwargs['status'], 'success')
        
        # Verify no errors were logged
        self.mock_log_error.assert_not_called()
    
    def test_api_key_not_found_logs_auth_error(self):
        """Test that missing API key logs an authentication error."""
        # Configure environment to simulate missing API key
        self.mock_env = {}
        
        # Call the function
        result = call_llm_for_reflection_v2(self.test_state)
        
        # Check result
        self.assertEqual(result, "Test error reflection")
        
        # Verify error was logged
        self.mock_log_error.assert_called_once()
        _, kwargs = self.mock_log_error.call_args
        self.assertIsInstance(kwargs['error'], LLMAuthenticationError)
        
        # Verify generate_error_reflection was called
        self.mock_generate_error.assert_called_once()
    
    def test_api_timeout_logs_error_and_retries(self):
        """Test that API timeout error logs and retries properly."""
        # Configure model to raise timeout error on first call then succeed
        timeout_error = TimeoutError("API timeout")
        self.mock_model.generate_content.side_effect = [timeout_error, self.successful_response]
        
        # Call the function
        result = call_llm_for_reflection_v2(self.test_state)
        
        # Check result
        self.assertEqual(result, "This is a successful reflection.")
        
        # Verify error was logged
        self.mock_log_error.assert_called_once()
        _, kwargs = self.mock_log_error.call_args
        self.assertIsInstance(kwargs['error'], LLMTimeoutError)
        self.assertEqual(kwargs['attempt'], 1)
        self.assertEqual(kwargs['max_attempts'], 3)
        
        # Verify model was called twice (error then success)
        self.assertEqual(self.mock_model.generate_content.call_count, 2)
    
    def test_connection_error_logs_and_retries(self):
        """Test that connection error logs and retries properly."""
        # Configure model to raise connection error on first call then succeed
        connection_error = ConnectionError("Connection failed")
        self.mock_model.generate_content.side_effect = [connection_error, self.successful_response]
        
        # Call the function
        result = call_llm_for_reflection_v2(self.test_state)
        
        # Check result
        self.assertEqual(result, "This is a successful response.")
        
        # Verify error was logged
        self.mock_log_error.assert_called_once()
        _, kwargs = self.mock_log_error.call_args
        self.assertIsInstance(kwargs['error'], LLMConnectionError)
        
        # Verify model was called twice (error then success)
        self.assertEqual(self.mock_model.generate_content.call_count, 2)
    
    def test_max_retries_exceeded_returns_error_reflection(self):
        """Test that exceeding max retries returns error reflection."""
        # Configure model to always raise timeout error
        timeout_error = TimeoutError("API timeout")
        self.mock_model.generate_content.side_effect = timeout_error
        
        # Call the function
        result = call_llm_for_reflection_v2(self.test_state)
        
        # Check result
        self.assertEqual(result, "Test error reflection")
        
        # Verify error was logged 3 times (max attempts)
        self.assertEqual(self.mock_log_error.call_count, 3)
        
        # Verify model was called 3 times (max attempts)
        self.assertEqual(self.mock_model.generate_content.call_count, 3)
        
        # Verify generate_error_reflection was called with appropriate error
        call_args = self.mock_generate_error.call_args
        self.assertEqual(call_args[1]['error_type'], 'LLMTimeoutError')
    
    def test_none_state_logs_error(self):
        """Test that None state logs an error."""
        # Call the function with None state
        result = call_llm_for_reflection_v2(None)
        
        # Check result
        self.assertEqual(result, "Test error reflection")
        
        # Verify error was logged
        self.mock_log_error.assert_called_once()
        
        # Verify generate_error_reflection was called
        self.mock_generate_error.assert_called_once()
    
    def test_empty_response_logs_error_and_retries(self):
        """Test that empty response logs an error and retries."""
        # Configure model to return empty response on first call then succeed
        empty_response = MagicMock()
        empty_response.text = ""
        self.mock_model.generate_content.side_effect = [empty_response, self.successful_response]
        
        # Call the function
        result = call_llm_for_reflection_v2(self.test_state)
        
        # Check result
        self.assertEqual(result, "This is a successful reflection.")
        
        # Verify error was logged
        self.mock_log_error.assert_called_once()
        _, kwargs = self.mock_log_error.call_args
        self.assertIsInstance(kwargs['error'], LLMAPIError)
        
        # Verify model was called twice (error then success)
        self.assertEqual(self.mock_model.generate_content.call_count, 2)
    
    def test_performance_metrics_calculation(self):
        """Test that performance metrics are calculated and logged."""
        # Set mock prompt length
        self.mock_get_prompt.return_value = "x" * 500
        
        # Call the function
        result = call_llm_for_reflection_v2(self.test_state)
        
        # Verify metrics were calculated
        self.mock_metrics.assert_called_once()
        args, _ = self.mock_metrics.call_args
        self.assertEqual(args[0], 500)  # prompt_length
        self.assertEqual(args[1], len("This is a successful reflection."))  # response_length
        
        # Verify metrics were included in response logging
        _, kwargs = self.mock_log_response.call_args
        self.assertIn('additional_metrics', kwargs)


if __name__ == '__main__':
    unittest.main() 