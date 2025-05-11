"""
Tests for the error recovery strategies.

This module shows how to use the specialized error recovery strategies
for handling different types of LLM API errors.
"""

import unittest
import os
import sys
import time
import json
import uuid
from unittest.mock import patch, MagicMock, call
from io import StringIO

# Add src directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import required modules
from src.langgraph_nodes import call_llm_for_reflection_v3, generate_error_reflection
from src.exceptions import (
    LLMAPIError, LLMAuthenticationError, LLMRateLimitError, 
    LLMConnectionError, LLMTimeoutError, LLMServerError,
    LLMServiceUnavailableError, LLMNetworkError
)
from src.error_recovery import (
    TokenBucketRateLimiter, RequestQueueManager, NetworkConnectionManager,
    ServiceHealthMonitor, ErrorRecoveryStrategies
)
from src.error_classifier import classify_error

class MockLLMClient:
    """Mock LLM client for testing error recovery strategies."""
    
    def __init__(self, fail_count=0, error_type=None):
        self.call_count = 0
        self.fail_count = fail_count
        self.error_type = error_type or LLMRateLimitError
        self.last_args = None
        self.last_kwargs = None
    
    def generate(self, *args, **kwargs):
        """Mock generate method that fails a specified number of times."""
        self.call_count += 1
        self.last_args = args
        self.last_kwargs = kwargs
        
        # Fail for the specified number of calls
        if self.call_count <= self.fail_count:
            if self.error_type == LLMRateLimitError:
                error = LLMRateLimitError("Rate limit exceeded")
                error.retry_after = 0.1  # Short delay for testing
                raise error
            elif self.error_type == LLMNetworkError:
                raise LLMNetworkError("Network error", original_error=Exception("General network failure"))
            elif self.error_type == LLMConnectionError:
                raise LLMConnectionError("Network error")
            elif self.error_type == LLMServiceUnavailableError:
                raise LLMServiceUnavailableError("Service unavailable")
            else:
                raise self.error_type("Error occurred")
        
        # Succeed after fail_count failures
        return {"result": "Success after recovery"}

class TestErrorRecovery(unittest.TestCase):
    """Test suite for error recovery components and strategies."""
    
    def setUp(self):
        """Set up test environment before each test."""
        self.mock_state = {
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
        
        # Create basic mocks for the API calls
        self.mock_response = MagicMock()
        self.mock_response.text = "This is a mock reflection response."
        
        # Ensure environment is clean
        if "GOOGLE_API_KEY" in os.environ:
            self.original_api_key = os.environ["GOOGLE_API_KEY"]
        else:
            self.original_api_key = None
            
        os.environ["GOOGLE_API_KEY"] = "mock-api-key-for-testing"
    
    def tearDown(self):
        """Clean up test environment after each test."""
        # Restore original API key
        if self.original_api_key:
            os.environ["GOOGLE_API_KEY"] = self.original_api_key
        else:
            if "GOOGLE_API_KEY" in os.environ:
                del os.environ["GOOGLE_API_KEY"]
    
    @patch('src.langgraph_nodes.genai.GenerativeModel')
    @patch('src.langgraph_nodes.TokenBucketRateLimiter')
    @patch('src.langgraph_nodes.NetworkConnectionManager')
    @patch('src.langgraph_nodes.ServiceHealthMonitor')
    def test_successful_call(self, mock_monitor, mock_network, mock_limiter, mock_model_class):
        """Test successful reflection call with normal operation."""
        # Configure mocks for normal setup
        mock_limiter_instance = MagicMock()
        mock_limiter_instance.acquire.return_value = True
        mock_limiter.return_value = mock_limiter_instance
        
        mock_monitor_instance = MagicMock()
        mock_monitor_instance.is_service_available.return_value = True
        mock_monitor.return_value = mock_monitor_instance
        
        # Set up connection manager
        mock_connection = MagicMock()
        mock_connection.id = "conn-123"
        mock_network_instance = MagicMock()
        mock_network_instance.get_connection.return_value.__enter__.return_value = mock_connection
        mock_network.return_value = mock_network_instance
        
        # Configure model to return a successful response
        response_mock = MagicMock()
        response_mock.text = "This is a mock reflection response."
        
        mock_model_instance = MagicMock()
        mock_model_instance.generate_content.return_value = response_mock
        mock_model_class.return_value = mock_model_instance
        
        # Mock the retry decorator to pass through the function call
        def mock_retry(*args, **kwargs):
            def inner(func):
                def wrapper(*args, **kwargs):
                    return func(*args, **kwargs)
                return wrapper
            return inner
        
        # Call the function with our mocked retry decorator
        with patch('src.langgraph_nodes.retry_all_api_errors', mock_retry):
            result = call_llm_for_reflection_v3(self.mock_state)
        
        # Verify successful response
        self.assertEqual(result, "This is a mock reflection response.")
        mock_monitor_instance.report_success.assert_called_once()
    
    @patch('src.langgraph_nodes.genai.GenerativeModel')
    @patch('src.langgraph_nodes.TokenBucketRateLimiter')
    @patch('src.langgraph_nodes.NetworkConnectionManager')
    @patch('src.langgraph_nodes.ServiceHealthMonitor')
    def test_rate_limit_handling(self, mock_monitor, mock_network, mock_limiter, mock_model_class):
        """Test handling of rate limit error."""
        # Configure bucket to reject the request (simulate rate limiting)
        mock_limiter_instance = MagicMock()
        mock_limiter_instance.acquire.return_value = False  # We're rate limited!
        mock_limiter.return_value = mock_limiter_instance
        
        # Create a mock request queue
        mock_queue = MagicMock()
        mock_queue.add_request.return_value = "queue-123"
        mock_queue.get_position.return_value = 3
        
        with patch('src.langgraph_nodes.RequestQueueManager', return_value=mock_queue):
            result = call_llm_for_reflection_v3(self.mock_state)
        
        # Verify rate limit error handling
        self.assertIn("rate limited", result.lower())
        self.assertIn("queue position", result.lower())
        self.assertIn("RateLimit Error", result)
        
    @patch('src.langgraph_nodes.genai.GenerativeModel')
    @patch('src.langgraph_nodes.TokenBucketRateLimiter')
    @patch('src.langgraph_nodes.NetworkConnectionManager')
    @patch('src.langgraph_nodes.ServiceHealthMonitor')
    def test_service_unavailable(self, mock_monitor, mock_network, mock_limiter, mock_model_class):
        """Test handling when service is marked as unavailable."""
        # Configure mocks for normal setup, but service is unavailable
        mock_limiter_instance = MagicMock()
        mock_limiter_instance.acquire.return_value = True
        mock_limiter.return_value = mock_limiter_instance
        
        # Set service as unavailable
        mock_monitor_instance = MagicMock()
        mock_monitor_instance.is_service_available.return_value = False  # Service is down!
        mock_monitor_instance.service_name = "GenAI-API"
        mock_monitor.return_value = mock_monitor_instance
        
        # Call the function (no need to reach the mock model)
        result = call_llm_for_reflection_v3(self.mock_state)
        
        # Verify service unavailable handling
        self.assertIn("unavailable", result.lower())
        self.assertIn("ServiceUnavailable Error", result)
    
    @patch('src.langgraph_nodes.genai.GenerativeModel')
    @patch('src.langgraph_nodes.TokenBucketRateLimiter')
    @patch('src.langgraph_nodes.NetworkConnectionManager')
    @patch('src.langgraph_nodes.ServiceHealthMonitor')
    def test_authentication_error(self, mock_monitor, mock_network, mock_limiter, mock_model_class):
        """Test handling of authentication errors."""
        # Remove API key to trigger authentication error
        if "GOOGLE_API_KEY" in os.environ:
            del os.environ["GOOGLE_API_KEY"]
        
        # Configure mocks for normal setup
        mock_limiter_instance = MagicMock()
        mock_limiter_instance.acquire.return_value = True
        mock_limiter.return_value = mock_limiter_instance
        
        mock_monitor_instance = MagicMock()
        mock_monitor_instance.is_service_available.return_value = True
        mock_monitor.return_value = mock_monitor_instance
        
        # Call the function
        result = call_llm_for_reflection_v3(self.mock_state)
        
        # Verify that we got an error reflection with the correct type
        self.assertIn("Missing API key", result)
        self.assertIn("Authentication Error", result)
    
    @patch('src.langgraph_nodes.genai.GenerativeModel')
    @patch('src.langgraph_nodes.TokenBucketRateLimiter')
    @patch('src.langgraph_nodes.NetworkConnectionManager')
    @patch('src.langgraph_nodes.ServiceHealthMonitor')
    @patch('src.langgraph_nodes.retry_all_api_errors')
    def test_integration_with_retry_decorator(self, mock_retry_decorator, mock_monitor, 
                                            mock_network, mock_limiter, mock_model_class):
        """Test integration with retry decorator."""
        # Configure mocks for normal setup
        mock_limiter_instance = MagicMock()
        mock_limiter_instance.acquire.return_value = True
        mock_limiter.return_value = mock_limiter_instance
        
        mock_monitor_instance = MagicMock()
        mock_monitor_instance.is_service_available.return_value = True
        mock_monitor.return_value = mock_monitor_instance
        
        mock_connection = MagicMock()
        mock_connection.id = "conn-123"
        mock_network_instance = MagicMock()
        mock_network_instance.get_connection.return_value.__enter__.return_value = mock_connection
        mock_network.return_value = mock_network_instance
        
        # Configure model to return a valid response
        mock_model_instance = MagicMock()
        mock_model_instance.generate_content.return_value = self.mock_response
        mock_model_class.return_value = mock_model_instance
        
        # Configure retry decorator to actually call the decorated function
        def mock_retry_implementation(func):
            def wrapped():
                return func()
            return wrapped
        mock_retry_decorator.return_value = mock_retry_implementation
        
        # Call the function
        result = call_llm_for_reflection_v3(self.mock_state)
        
        # Verify results
        self.assertEqual(result, "This is a mock reflection response.")
        mock_retry_decorator.assert_called_once()
        mock_model_instance.generate_content.assert_called_once()

if __name__ == '__main__':
    unittest.main() 