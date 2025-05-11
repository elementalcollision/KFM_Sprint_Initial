"""
Unit tests for the call_llm_for_reflection_v3 function in src/langgraph_nodes.py.

This module tests the advanced error handling and recovery mechanisms
implemented in the call_llm_for_reflection_v3 function.
"""

import unittest
import os
import time
import json
from unittest.mock import patch, MagicMock, Mock, call
import pytest

from src.langgraph_nodes import call_llm_for_reflection_v3
from src.exceptions import (
    LLMAPIError,
    LLMNetworkError,
    LLMTimeoutError,
    LLMConnectionError,
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMInvalidRequestError,
    LLMServerError,
    LLMServiceUnavailableError,
    LLMInternalError
)


class TestCallLLMForReflectionV3(unittest.TestCase):
    """Test suite for the call_llm_for_reflection_v3 function."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Create a mock state for testing
        self.test_state = {
            "session_id": "test-session-123",
            "user_id": "test-user-456",
            "current_context": {
                "action_type": "test_action",
                "component": "test_component",
                "active_component": "test_active_component",
                "previous_actions": [],
                "error_history": []
            }
        }
        
        # Patch environment variables and mock objects for API calls
        patcher = patch.dict('os.environ', {'GOOGLE_API_KEY': 'test-api-key'})
        patcher.start()
        self.addCleanup(patcher.stop)
        
    @patch('src.langgraph_nodes.genai.GenerativeModel')
    @patch('src.langgraph_nodes.TokenBucketRateLimiter')
    @patch('src.langgraph_nodes.RequestQueueManager')
    @patch('src.langgraph_nodes.NetworkConnectionManager')
    @patch('src.langgraph_nodes.ServiceHealthMonitor')
    @patch('src.langgraph_nodes.ErrorRecoveryStrategies')
    @patch('src.langgraph_nodes.retry_all_api_errors')
    def test_successful_call(self, mock_retry, mock_recovery, mock_monitor, 
                            mock_network, mock_queue, mock_limiter, mock_model):
        """Test that a successful API call returns the expected result."""
        # Configure mocks
        mock_limiter_instance = MagicMock()
        mock_limiter_instance.consume.return_value = True
        mock_limiter.return_value = mock_limiter_instance
        
        mock_queue_instance = MagicMock()
        mock_queue.return_value = mock_queue_instance
        
        mock_network_instance = MagicMock()
        mock_network.return_value = mock_network_instance
        
        mock_monitor_instance = MagicMock()
        mock_monitor_instance.is_service_available.return_value = True
        mock_monitor.return_value = mock_monitor_instance
        
        mock_recovery_instance = MagicMock()
        mock_recovery.return_value = mock_recovery_instance
        
        # Mock the retry decorator to just call the function directly
        mock_retry.return_value = lambda f: f
        
        # Configure model to return successful response
        mock_response = MagicMock()
        mock_response.text = "This is a successful reflection response."
        
        mock_model_instance = MagicMock()
        mock_model_instance.generate_content.return_value = mock_response
        mock_model.return_value = mock_model_instance
        
        # Call the function
        result = call_llm_for_reflection_v3(self.test_state)
        
        # Check the result
        self.assertEqual(result, "This is a successful reflection response.")
        
        # Verify that the appropriate mocks were called
        mock_limiter_instance.consume.assert_called_once()
        mock_monitor_instance.is_service_available.assert_called_once()
        mock_model_instance.generate_content.assert_called_once()
        mock_limiter_instance.record_success.assert_called_once()
        mock_monitor_instance.record_request_result.assert_called_once()
    
    @patch('src.langgraph_nodes.genai.GenerativeModel')
    @patch('src.langgraph_nodes.TokenBucketRateLimiter')
    @patch('src.langgraph_nodes.RequestQueueManager')
    @patch('src.langgraph_nodes.NetworkConnectionManager')
    @patch('src.langgraph_nodes.ServiceHealthMonitor')
    @patch('src.langgraph_nodes.ErrorRecoveryStrategies')
    @patch('src.langgraph_nodes.retry_all_api_errors')
    def test_rate_limit_handling(self, mock_retry, mock_recovery, mock_monitor, 
                               mock_network, mock_queue, mock_limiter, mock_model):
        """Test that rate limit errors are properly handled."""
        # Configure rate limiter to reject the request
        mock_limiter_instance = MagicMock()
        mock_limiter_instance.consume.return_value = False  # Rate limited
        mock_limiter.return_value = mock_limiter_instance
        
        # Configure queue manager
        mock_queue_instance = MagicMock()
        mock_queue_instance.enqueue.return_value = "queue-123"
        mock_queue.return_value = mock_queue_instance
        
        # Call the function
        result = call_llm_for_reflection_v3(self.test_state)
        
        # Check for rate limit error handling
        self.assertIn("rate limit", result.lower())
        
        # Verify the queue was used
        mock_queue_instance.enqueue.assert_called_once()
        mock_model.return_value.generate_content.assert_not_called()
    
    @patch('src.langgraph_nodes.genai.GenerativeModel')
    @patch('src.langgraph_nodes.TokenBucketRateLimiter')
    @patch('src.langgraph_nodes.RequestQueueManager')
    @patch('src.langgraph_nodes.NetworkConnectionManager')
    @patch('src.langgraph_nodes.ServiceHealthMonitor')
    @patch('src.langgraph_nodes.ErrorRecoveryStrategies')
    @patch('src.langgraph_nodes.retry_all_api_errors')
    def test_service_unavailable_handling(self, mock_retry, mock_recovery, mock_monitor, 
                                        mock_network, mock_queue, mock_limiter, mock_model):
        """Test that service unavailable errors are properly handled."""
        # Configure rate limiter to accept the request
        mock_limiter_instance = MagicMock()
        mock_limiter_instance.consume.return_value = True
        mock_limiter.return_value = mock_limiter_instance
        
        # Configure service monitor to report service as unavailable
        mock_monitor_instance = MagicMock()
        mock_monitor_instance.is_service_available.return_value = False
        mock_monitor_instance.get_service_status.return_value = "unavailable"
        mock_monitor.return_value = mock_monitor_instance
        
        # Call the function
        result = call_llm_for_reflection_v3(self.test_state)
        
        # Check for service unavailable error handling
        self.assertIn("service unavailable", result.lower())
        
        # Verify that API was not called
        mock_model.return_value.generate_content.assert_not_called()
    
    @patch('src.langgraph_nodes.genai.GenerativeModel')
    @patch('src.langgraph_nodes.TokenBucketRateLimiter')
    @patch('src.langgraph_nodes.RequestQueueManager')
    @patch('src.langgraph_nodes.NetworkConnectionManager')
    @patch('src.langgraph_nodes.ServiceHealthMonitor')
    @patch('src.langgraph_nodes.ErrorRecoveryStrategies')
    @patch('src.langgraph_nodes.retry_all_api_errors')
    def test_api_call_error_handling(self, mock_retry, mock_recovery, mock_monitor, 
                                   mock_network, mock_queue, mock_limiter, mock_model):
        """Test that errors during API calls are properly handled."""
        # Configure rate limiter to accept the request
        mock_limiter_instance = MagicMock()
        mock_limiter_instance.consume.return_value = True
        mock_limiter.return_value = mock_limiter_instance
        
        # Configure service monitor to report service as available
        mock_monitor_instance = MagicMock()
        mock_monitor_instance.is_service_available.return_value = True
        mock_monitor.return_value = mock_monitor_instance
        
        # Configure model to raise an exception
        mock_model_instance = MagicMock()
        mock_model_instance.generate_content.side_effect = LLMNetworkError("Network error")
        mock_model.return_value = mock_model_instance
        
        # Mock retry decorator to call the function once and bypass retries
        mock_retry.return_value = lambda f: f
        
        # Configure recovery strategies
        mock_recovery_instance = MagicMock()
        mock_recovery_instance.handle_error.side_effect = lambda *args, **kwargs: "Error recovery response"
        mock_recovery.return_value = mock_recovery_instance
        
        # Call the function
        result = call_llm_for_reflection_v3(self.test_state)
        
        # Check the result
        self.assertEqual(result, "Error recovery response")
        
        # Verify the error handling flow
        mock_model_instance.generate_content.assert_called_once()
        mock_recovery_instance.handle_error.assert_called_once()
        mock_limiter_instance.record_success.assert_not_called()
    
    @patch('src.langgraph_nodes.genai.GenerativeModel')
    @patch('src.langgraph_nodes.TokenBucketRateLimiter')
    @patch('src.langgraph_nodes.RequestQueueManager')
    @patch('src.langgraph_nodes.NetworkConnectionManager')
    @patch('src.langgraph_nodes.ServiceHealthMonitor')
    @patch('src.langgraph_nodes.ErrorRecoveryStrategies')
    @patch('src.langgraph_nodes.retry_all_api_errors')
    def test_api_authentication_error(self, mock_retry, mock_recovery, mock_monitor, 
                                   mock_network, mock_queue, mock_limiter, mock_model):
        """Test that authentication errors are properly handled."""
        # Remove API key to trigger authentication error
        with patch.dict('os.environ', {'GOOGLE_API_KEY': ''}):
            # Call the function
            result = call_llm_for_reflection_v3(self.test_state)
            
            # Check the result
            self.assertIn("authentication", result.lower())
            
            # Verify that the API was not called
            mock_model.return_value.generate_content.assert_not_called()
    
    @patch('src.langgraph_nodes.genai.GenerativeModel')
    @patch('src.langgraph_nodes.TokenBucketRateLimiter')
    @patch('src.langgraph_nodes.RequestQueueManager')
    @patch('src.langgraph_nodes.NetworkConnectionManager')
    @patch('src.langgraph_nodes.ServiceHealthMonitor')
    @patch('src.langgraph_nodes.ErrorRecoveryStrategies')
    def test_retry_integration(self, mock_recovery, mock_monitor, mock_network, 
                             mock_queue, mock_limiter, mock_model):
        """Test integration with retry mechanism."""
        # Configure rate limiter to accept the request
        mock_limiter_instance = MagicMock()
        mock_limiter_instance.consume.return_value = True
        mock_limiter.return_value = mock_limiter_instance
        
        # Configure service monitor to report service as available
        mock_monitor_instance = MagicMock()
        mock_monitor_instance.is_service_available.return_value = True
        mock_monitor.return_value = mock_monitor_instance
        
        # Configure model to succeed after two failures
        mock_model_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Success after retries"
        
        # Create a side effect that fails twice then succeeds
        side_effects = [
            LLMServerError("Server error 1"),
            LLMServerError("Server error 2"),
            mock_response
        ]
        mock_model_instance.generate_content.side_effect = side_effects
        mock_model.return_value = mock_model_instance
        
        # Create a real retry decorator for testing
        def real_retry_decorator(f):
            def wrapper(*args, **kwargs):
                attempts = 0
                max_attempts = 3
                
                while attempts < max_attempts:
                    try:
                        return f(*args, **kwargs)
                    except LLMAPIError as e:
                        attempts += 1
                        if attempts >= max_attempts:
                            raise
                        time.sleep(0.01)  # Small delay for testing
                return None
            return wrapper
        
        # Patch the retry decorator to use our test implementation
        with patch('src.langgraph_nodes.retry_all_api_errors', return_value=real_retry_decorator):
            # Call the function
            result = call_llm_for_reflection_v3(self.test_state)
            
            # Check the result
            self.assertEqual(result, "Success after retries")
            
            # Verify number of API call attempts
            self.assertEqual(mock_model_instance.generate_content.call_count, 3)
            
            # Verify success was recorded
            mock_limiter_instance.record_success.assert_called_once()


if __name__ == '__main__':
    unittest.main() 