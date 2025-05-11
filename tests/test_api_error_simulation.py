"""
Tests that simulate various API error conditions to verify error handling.

This module creates mock API responses for different error scenarios
to test that the error handling system properly handles each type of failure.
"""

import unittest
import time
import json
import random
from unittest.mock import patch, MagicMock, Mock

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


class MockAPIResponse:
    """Mock API response object that simulates various error conditions."""
    
    def __init__(self, status_code=200, error_message=None, error_type=None, content=None):
        self.status_code = status_code
        self.error_message = error_message
        self.error_type = error_type
        self.content = content or {}
        
    def json(self):
        """Return the JSON content of the response."""
        if self.error_message:
            return {
                "error": {
                    "message": self.error_message,
                    "type": self.error_type or "unknown_error",
                    "code": self.status_code
                }
            }
        return self.content
    
    def raise_for_status(self):
        """Raise an exception if the status code indicates an error."""
        import requests
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP Error: {self.status_code}")
        

class TestAPIErrorSimulation(unittest.TestCase):
    """Test error handling by simulating various API error conditions."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Create prompt for testing
        self.test_prompt = "Test prompt for error simulation"
        
        # Mock logging to prevent actual logging during tests
        self.log_patcher = patch('src.llm_logging.ErrorLogger')
        self.mock_logger = self.log_patcher.start()
        
    def tearDown(self):
        """Clean up after tests."""
        self.log_patcher.stop()
    
    @patch('google.generativeai.GenerativeModel')
    def test_network_timeout(self, mock_generative_model):
        """Test handling of network timeout errors."""
        # Configure the mock to raise a timeout error
        model_instance = MagicMock()
        model_instance.generate_content.side_effect = TimeoutError("Request timed out")
        mock_generative_model.return_value = model_instance
        
        # Call the function and check error handling
        result = call_llm_for_reflection_v3(self.test_prompt)
        
        # Verify it returned a fallback response
        self.assertIn("error", result.lower())
        self.assertIn("timeout", result.lower())
        
        # Verify the appropriate exception handling occurred
        model_instance.generate_content.assert_called_once()
    
    @patch('google.generativeai.GenerativeModel')
    def test_connection_error(self, mock_generative_model):
        """Test handling of connection errors."""
        # Configure the mock to raise a connection error
        model_instance = MagicMock()
        model_instance.generate_content.side_effect = ConnectionError("Failed to establish connection")
        mock_generative_model.return_value = model_instance
        
        # Call the function and check error handling
        result = call_llm_for_reflection_v3(self.test_prompt)
        
        # Verify it returned a fallback response
        self.assertIn("error", result.lower())
        self.assertIn("connection", result.lower())
        
        # Verify the appropriate exception handling occurred
        model_instance.generate_content.assert_called_once()
    
    @patch('google.generativeai.GenerativeModel')
    def test_authentication_error(self, mock_generative_model):
        """Test handling of authentication errors."""
        # Configure the mock to return an authentication error response
        model_instance = MagicMock()
        error_response = MockAPIResponse(
            status_code=401,
            error_message="Invalid API key",
            error_type="authentication_error"
        )
        model_instance.generate_content.side_effect = Exception(error_response)
        mock_generative_model.return_value = model_instance
        
        # Call the function and check error handling
        result = call_llm_for_reflection_v3(self.test_prompt)
        
        # Verify it returned a fallback response
        self.assertIn("error", result.lower())
        self.assertIn("authentication", result.lower())
        
        # Verify the appropriate exception handling occurred
        model_instance.generate_content.assert_called_once()
    
    @patch('google.generativeai.GenerativeModel')
    def test_rate_limit_error(self, mock_generative_model):
        """Test handling of rate limit errors."""
        # Configure the mock to return a rate limit error response
        model_instance = MagicMock()
        error_response = MockAPIResponse(
            status_code=429,
            error_message="Rate limit exceeded. Please try again later.",
            error_type="rate_limit_error",
            content={"retry_after": 30}
        )
        model_instance.generate_content.side_effect = Exception(error_response)
        mock_generative_model.return_value = model_instance
        
        # Call the function and check error handling
        result = call_llm_for_reflection_v3(self.test_prompt)
        
        # Verify it returned a fallback response
        self.assertIn("error", result.lower())
        self.assertIn("rate limit", result.lower())
        
        # Verify the appropriate exception handling occurred
        model_instance.generate_content.assert_called_once()
    
    @patch('google.generativeai.GenerativeModel')
    def test_invalid_request_error(self, mock_generative_model):
        """Test handling of invalid request errors."""
        # Configure the mock to return an invalid request error response
        model_instance = MagicMock()
        error_response = MockAPIResponse(
            status_code=400,
            error_message="Invalid request parameters",
            error_type="invalid_request_error"
        )
        model_instance.generate_content.side_effect = Exception(error_response)
        mock_generative_model.return_value = model_instance
        
        # Call the function and check error handling
        result = call_llm_for_reflection_v3(self.test_prompt)
        
        # Verify it returned a fallback response
        self.assertIn("error", result.lower())
        self.assertIn("invalid", result.lower())
        
        # Verify the appropriate exception handling occurred
        model_instance.generate_content.assert_called_once()
    
    @patch('google.generativeai.GenerativeModel')
    def test_server_error(self, mock_generative_model):
        """Test handling of server errors."""
        # Configure the mock to return a server error response
        model_instance = MagicMock()
        error_response = MockAPIResponse(
            status_code=500,
            error_message="Internal server error",
            error_type="server_error"
        )
        model_instance.generate_content.side_effect = Exception(error_response)
        mock_generative_model.return_value = model_instance
        
        # Call the function and check error handling
        result = call_llm_for_reflection_v3(self.test_prompt)
        
        # Verify it returned a fallback response
        self.assertIn("error", result.lower())
        self.assertIn("server", result.lower())
        
        # Verify the appropriate exception handling occurred
        model_instance.generate_content.assert_called_once()
    
    @patch('google.generativeai.GenerativeModel')
    def test_service_unavailable_error(self, mock_generative_model):
        """Test handling of service unavailable errors."""
        # Configure the mock to return a service unavailable error response
        model_instance = MagicMock()
        error_response = MockAPIResponse(
            status_code=503,
            error_message="Service temporarily unavailable",
            error_type="service_unavailable_error"
        )
        model_instance.generate_content.side_effect = Exception(error_response)
        mock_generative_model.return_value = model_instance
        
        # Call the function and check error handling
        result = call_llm_for_reflection_v3(self.test_prompt)
        
        # Verify it returned a fallback response
        self.assertIn("error", result.lower())
        self.assertIn("unavailable", result.lower())
        
        # Verify the appropriate exception handling occurred
        model_instance.generate_content.assert_called_once()
    
    @patch('google.generativeai.GenerativeModel')
    def test_intermittent_errors(self, mock_generative_model):
        """Test handling of intermittent errors with retry logic."""
        # Configure the mock to fail several times then succeed
        model_instance = MagicMock()
        
        # Create a side effect function that fails the first two calls then succeeds
        attempt_count = [0]
        
        def side_effect(*args, **kwargs):
            attempt_count[0] += 1
            if attempt_count[0] <= 2:
                # Return a different error each time
                error_codes = [
                    (500, "Internal server error", "server_error"),
                    (503, "Service temporarily unavailable", "service_unavailable_error")
                ]
                
                error_code, error_message, error_type = error_codes[attempt_count[0] - 1]
                error_response = MockAPIResponse(
                    status_code=error_code,
                    error_message=error_message,
                    error_type=error_type
                )
                raise Exception(error_response)
            else:
                # Succeed on third attempt
                mock_response = MagicMock()
                mock_response.text = "Successful reflection response after retry"
                return mock_response
        
        model_instance.generate_content.side_effect = side_effect
        mock_generative_model.return_value = model_instance
        
        # Call the function and check error handling
        result = call_llm_for_reflection_v3(self.test_prompt)
        
        # Verify it eventually succeeded after retries
        self.assertEqual(result, "Successful reflection response after retry")
        
        # Verify the function was called multiple times (retry logic working)
        self.assertEqual(model_instance.generate_content.call_count, 3)
    
    @patch('google.generativeai.GenerativeModel')
    def test_error_with_retry_after_header(self, mock_generative_model):
        """Test handling of errors with Retry-After headers."""
        # Configure the mock to return a rate limit error with Retry-After header
        model_instance = MagicMock()
        
        # Create a side effect function that checks timing
        start_time = [None]
        
        def side_effect(*args, **kwargs):
            if start_time[0] is None:
                # First call - return rate limit with retry-after
                start_time[0] = time.time()
                error_response = MockAPIResponse(
                    status_code=429,
                    error_message="Rate limit exceeded. Please retry in 2 seconds.",
                    error_type="rate_limit_error",
                    content={"retry_after": 2}  # 2-second retry after
                )
                raise Exception(error_response)
            else:
                # Second call - check if enough time passed and succeed
                elapsed = time.time() - start_time[0]
                # Verify some backoff occurred (at least 1 second)
                if elapsed < 1:
                    raise Exception("Retry happened too quickly, before backoff time")
                
                mock_response = MagicMock()
                mock_response.text = "Successful response after backoff"
                return mock_response
        
        model_instance.generate_content.side_effect = side_effect
        mock_generative_model.return_value = model_instance
        
        # Call the function and check error handling with retry timing
        result = call_llm_for_reflection_v3(self.test_prompt)
        
        # Verify the response after backoff
        self.assertEqual(result, "Successful response after backoff")
        
        # Verify the function was called twice
        self.assertEqual(model_instance.generate_content.call_count, 2)
    
    @patch('google.generativeai.GenerativeModel')
    def test_persistent_errors_circuit_breaker(self, mock_generative_model):
        """Test that persistent errors trigger the circuit breaker."""
        # Configure the mock to consistently fail with server errors
        model_instance = MagicMock()
        model_instance.generate_content.side_effect = Exception(MockAPIResponse(
            status_code=500,
            error_message="Internal server error",
            error_type="server_error"
        ))
        mock_generative_model.return_value = model_instance
        
        # Need to make multiple calls to potentially trigger the circuit breaker
        results = []
        for _ in range(10):
            results.append(call_llm_for_reflection_v3(self.test_prompt))
        
        # Verify all responses indicate error
        for result in results:
            self.assertIn("error", result.lower())
        
        # Verify the model wasn't called for all 10 attempts (circuit breaker)
        # The exact number depends on the configuration, but should be less than 10
        self.assertLess(model_instance.generate_content.call_count, 10, 
                       "Circuit breaker should prevent all API calls")
    
    @patch('google.generativeai.GenerativeModel')
    def test_random_error_simulation(self, mock_generative_model):
        """Test handling of random error types to ensure robustness."""
        # Configure the mock to return random errors
        model_instance = MagicMock()
        
        # Define a list of possible error conditions
        error_conditions = [
            (400, "Bad request", "invalid_request_error"),
            (401, "Unauthorized", "authentication_error"),
            (403, "Forbidden", "authorization_error"),
            (404, "Not found", "not_found_error"),
            (429, "Rate limit exceeded", "rate_limit_error"),
            (500, "Internal server error", "server_error"),
            (502, "Bad gateway", "server_error"),
            (503, "Service unavailable", "service_unavailable_error"),
            (504, "Gateway timeout", "timeout_error"),
            None  # Represent a network error
        ]
        
        # Create a side effect function that returns random errors
        def random_error_side_effect(*args, **kwargs):
            error_condition = random.choice(error_conditions)
            
            if error_condition is None:
                # Simulate a network error
                error_types = [TimeoutError("Request timed out"), 
                              ConnectionError("Connection error"),
                              ValueError("Invalid value")]
                raise random.choice(error_types)
            else:
                status_code, error_message, error_type = error_condition
                error_response = MockAPIResponse(
                    status_code=status_code,
                    error_message=error_message,
                    error_type=error_type
                )
                raise Exception(error_response)
        
        model_instance.generate_content.side_effect = random_error_side_effect
        mock_generative_model.return_value = model_instance
        
        # Make multiple calls to test random error handling
        for _ in range(10):
            result = call_llm_for_reflection_v3(self.test_prompt)
            
            # Verify it returned a fallback response that indicates an error
            self.assertIn("error", result.lower())
    
    @patch('src.error_recovery.TokenBucketRateLimiter.consume')
    @patch('google.generativeai.GenerativeModel')
    def test_rate_limiting_activation(self, mock_generative_model, mock_consume):
        """Test that the rate limiter is consulted before making API calls."""
        # Setup API mock to return normal responses
        model_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Successful API response"
        model_instance.generate_content.return_value = mock_response
        mock_generative_model.return_value = model_instance
        
        # Setup rate limiter to allow first call then block subsequent calls
        mock_consume.side_effect = [True, ValueError("Rate limit exceeded")]
        
        # Make two calls - first should succeed, second should be rate limited
        result1 = call_llm_for_reflection_v3(self.test_prompt)
        result2 = call_llm_for_reflection_v3(self.test_prompt)
        
        # Verify first call succeeded
        self.assertEqual(result1, "Successful API response")
        
        # Verify second call was rate limited and returned fallback
        self.assertIn("error", result2.lower())
        self.assertIn("rate limit", result2.lower())
        
        # Verify the first call went through to API but second didn't
        self.assertEqual(model_instance.generate_content.call_count, 1)


if __name__ == '__main__':
    unittest.main() 