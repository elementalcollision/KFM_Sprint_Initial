"""
Unit tests for the custom exception classes defined in src/exceptions.py.
"""

import unittest
import json
import time
from unittest.mock import Mock, patch

from src.exceptions import (
    LLMAPIError,
    LLMNetworkError,
    LLMTimeoutError,
    LLMConnectionError,
    LLMClientError,
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMInvalidRequestError,
    LLMServerError,
    LLMServiceUnavailableError,
    LLMInternalError,
    map_exception_to_llm_error
)


class TestExceptionBasics(unittest.TestCase):
    """Test basic properties and methods of the exception classes."""
    
    def test_base_exception_init(self):
        """Test that the base exception initializes correctly."""
        error = LLMAPIError(
            message="Test error",
            status_code=400,
            request_id="req-123",
            response_data={"error": "details"},
            request_data={"prompt": "test"}
        )
        
        self.assertEqual(error.message, "Test error")
        self.assertEqual(error.status_code, 400)
        self.assertEqual(error.request_id, "req-123")
        self.assertEqual(error.response_data, {"error": "details"})
        self.assertEqual(error.request_data, {"prompt": "test"})
        self.assertIsNotNone(error.timestamp)
        
    def test_exception_str_representation(self):
        """Test the string representation of exceptions."""
        error = LLMAPIError("Test error", 400, "req-123")
        self.assertIn("Test error", str(error))
        self.assertIn("400", str(error))
        self.assertIn("req-123", str(error))
        
    def test_exception_inheritance(self):
        """Test that the exception hierarchy is correct."""
        self.assertTrue(issubclass(LLMNetworkError, LLMAPIError))
        self.assertTrue(issubclass(LLMTimeoutError, LLMNetworkError))
        self.assertTrue(issubclass(LLMConnectionError, LLMNetworkError))
        
        self.assertTrue(issubclass(LLMClientError, LLMAPIError))
        self.assertTrue(issubclass(LLMAuthenticationError, LLMClientError))
        self.assertTrue(issubclass(LLMRateLimitError, LLMClientError))
        self.assertTrue(issubclass(LLMInvalidRequestError, LLMClientError))
        
        self.assertTrue(issubclass(LLMServerError, LLMAPIError))
        self.assertTrue(issubclass(LLMServiceUnavailableError, LLMServerError))
        self.assertTrue(issubclass(LLMInternalError, LLMServerError))


class TestRetryableProperty(unittest.TestCase):
    """Test the is_retryable property of exceptions."""
    
    def test_base_error_not_retryable(self):
        """Base errors should not be retryable by default."""
        error = LLMAPIError("Test")
        self.assertFalse(error.is_retryable)
        
    def test_network_errors_retryable(self):
        """Network errors should be retryable."""
        error = LLMNetworkError("Test")
        self.assertTrue(error.is_retryable)
        
        timeout_error = LLMTimeoutError()
        self.assertTrue(timeout_error.is_retryable)
        
        connection_error = LLMConnectionError()
        self.assertTrue(connection_error.is_retryable)
        
    def test_client_errors_not_retryable(self):
        """Client errors should not be retryable (except rate limit)."""
        error = LLMClientError("Test")
        self.assertFalse(error.is_retryable)
        
        auth_error = LLMAuthenticationError()
        self.assertFalse(auth_error.is_retryable)
        
        invalid_request = LLMInvalidRequestError()
        self.assertFalse(invalid_request.is_retryable)
        
    def test_rate_limit_error_retryable(self):
        """Rate limit errors should be retryable despite being client errors."""
        error = LLMRateLimitError()
        self.assertTrue(error.is_retryable)
        
    def test_server_errors_retryable(self):
        """Server errors should be retryable."""
        error = LLMServerError("Test")
        self.assertTrue(error.is_retryable)
        
        unavailable = LLMServiceUnavailableError()
        self.assertTrue(unavailable.is_retryable)
        
        internal = LLMInternalError()
        self.assertTrue(internal.is_retryable)


class TestToDictMethod(unittest.TestCase):
    """Test the to_dict method for serialization."""
    
    def test_to_dict_basic(self):
        """Test the basic to_dict functionality."""
        timestamp = time.time()
        error = LLMAPIError(
            message="Test error",
            status_code=400,
            request_id="req-123",
            response_data={"error": "details"},
            request_data={"prompt": "test"},
            timestamp=timestamp
        )
        
        error_dict = error.to_dict()
        self.assertEqual(error_dict["error_type"], "LLMAPIError")
        self.assertEqual(error_dict["message"], "Test error")
        self.assertEqual(error_dict["status_code"], 400)
        self.assertEqual(error_dict["request_id"], "req-123")
        self.assertEqual(error_dict["timestamp"], timestamp)
        self.assertEqual(error_dict["response_data"], {"error": "details"})
        self.assertEqual(error_dict["request_data"], {"prompt": "test"})
        self.assertFalse(error_dict["is_retryable"])
        
    def test_to_dict_sensitive_data_filtering(self):
        """Test that sensitive data is filtered in to_dict."""
        error = LLMAPIError(
            message="Test error",
            request_data={
                "prompt": "test",
                "api_key": "SECRET",
                "credentials": "SENSITIVE",
                "token": "PRIVATE"
            }
        )
        
        error_dict = error.to_dict()
        self.assertEqual(error_dict["request_data"], {"prompt": "test"})
        self.assertNotIn("api_key", error_dict["request_data"])
        self.assertNotIn("credentials", error_dict["request_data"])
        self.assertNotIn("token", error_dict["request_data"])


class TestResponseMapping(unittest.TestCase):
    """Test mapping API responses to appropriate exception types."""
    
    def create_mock_response(self, status_code, json_data=None, headers=None):
        """Helper to create a mock response object."""
        mock_response = Mock()
        mock_response.status_code = status_code
        mock_response.headers = headers or {}
        
        def mock_json():
            return json_data or {}
            
        mock_response.json = mock_json
        return mock_response
    
    def test_authentication_error_mapping(self):
        """Test mapping a 401 response to an authentication error."""
        response = self.create_mock_response(
            status_code=401,
            json_data={"error": {"message": "Invalid API key"}}
        )
        
        error = LLMAPIError.from_response(response)
        self.assertIsInstance(error, LLMAuthenticationError)
        self.assertEqual(error.status_code, 401)
        self.assertEqual(error.message, "Invalid API key")
        
    def test_rate_limit_error_mapping(self):
        """Test mapping a 429 response to a rate limit error."""
        response = self.create_mock_response(
            status_code=429,
            json_data={"error": {"message": "Rate limit exceeded"}}
        )
        
        error = LLMAPIError.from_response(response)
        self.assertIsInstance(error, LLMRateLimitError)
        self.assertEqual(error.status_code, 429)
        self.assertTrue(error.is_retryable)
        
    def test_invalid_request_error_mapping(self):
        """Test mapping a 400 response to an invalid request error."""
        response = self.create_mock_response(
            status_code=400,
            json_data={"error": {"message": "Invalid prompt format"}}
        )
        
        error = LLMAPIError.from_response(response)
        self.assertIsInstance(error, LLMInvalidRequestError)
        self.assertEqual(error.status_code, 400)
        self.assertFalse(error.is_retryable)
        
    def test_service_unavailable_error_mapping(self):
        """Test mapping a 503 response to a service unavailable error."""
        response = self.create_mock_response(
            status_code=503,
            json_data={"error": {"message": "Service temporarily unavailable"}}
        )
        
        error = LLMAPIError.from_response(response)
        self.assertIsInstance(error, LLMServiceUnavailableError)
        self.assertEqual(error.status_code, 503)
        self.assertTrue(error.is_retryable)
        
    def test_internal_error_mapping(self):
        """Test mapping a 500 response to an internal error."""
        response = self.create_mock_response(
            status_code=500,
            json_data={"error": {"message": "Internal server error"}}
        )
        
        error = LLMAPIError.from_response(response)
        self.assertIsInstance(error, LLMInternalError)
        self.assertEqual(error.status_code, 500)
        self.assertTrue(error.is_retryable)
        
    def test_default_error_mapping(self):
        """Test mapping a response with no status code to a generic error."""
        response = Mock()
        # No status_code attribute
        
        error = LLMAPIError.from_response(response)
        self.assertIsInstance(error, LLMAPIError)
        self.assertIsNone(error.status_code)
        
    def test_request_id_extraction(self):
        """Test that request ID is extracted from response headers or body."""
        # From headers
        response = self.create_mock_response(
            status_code=400,
            headers={"x-request-id": "header-req-123"}
        )
        error = LLMAPIError.from_response(response)
        self.assertEqual(error.request_id, "header-req-123")
        
        # From body (common path)
        response = self.create_mock_response(
            status_code=400,
            json_data={"error": {"request_id": "body-req-456"}}
        )
        error = LLMAPIError.from_response(response)
        self.assertEqual(error.request_id, "body-req-456")
        
        # From body (Anthropic specific path)
        response = self.create_mock_response(
            status_code=400,
            json_data={"request_id": "anthropic-req-789"} # No nested error object
        )
        error = LLMAPIError.from_response(response)
        self.assertEqual(error.request_id, "anthropic-req-789")


class TestExceptionMapping(unittest.TestCase):
    """Test the map_exception_to_llm_error utility function."""
    
    def test_timeout_mapping(self):
        """Test that timeout exceptions are mapped to LLMTimeoutError."""
        from requests.exceptions import Timeout
        original_exc = Timeout("Connection timed out")
        llm_exc = map_exception_to_llm_error(original_exc)
        self.assertIsInstance(llm_exc, LLMTimeoutError)
        self.assertIn("Connection timed out", llm_exc.message)
        
    def test_connection_error_mapping(self):
        """Test that connection errors are mapped to LLMConnectionError."""
        from requests.exceptions import ConnectionError as RequestsConnectionError
        original_exc = RequestsConnectionError("Failed to establish connection")
        llm_exc = map_exception_to_llm_error(original_exc)
        self.assertIsInstance(llm_exc, LLMConnectionError)
        self.assertIn("Failed to establish connection", llm_exc.message)
        
    @patch('src.exceptions.requests')
    def test_requests_exception_mapping(self, mock_requests):
        """Test that generic requests exceptions are mapped to LLMNetworkError."""
        # Define specific request exception types if they exist in the mocked requests
        mock_requests.exceptions.RequestException = type('RequestException', (Exception,), {})
        mock_requests.exceptions.Timeout = type('Timeout', (mock_requests.exceptions.RequestException,), {})
        mock_requests.exceptions.ConnectionError = type('ConnectionError', (mock_requests.exceptions.RequestException,), {})
        mock_requests.exceptions.TooManyRedirects = type('TooManyRedirects', (mock_requests.exceptions.RequestException,), {})

        original_exc = mock_requests.exceptions.RequestException("Generic request error")
        llm_exc = map_exception_to_llm_error(original_exc)
        self.assertIsInstance(llm_exc, LLMNetworkError)
        self.assertIn("Generic request error", llm_exc.message)

        # Test specific requests exceptions not already handled (e.g. TooManyRedirects)
        specific_req_exc = mock_requests.exceptions.TooManyRedirects("Too many redirects")
        llm_specific_exc = map_exception_to_llm_error(specific_req_exc)
        self.assertIsInstance(llm_specific_exc, LLMNetworkError) # Should still be a network error
        self.assertIn("Too many redirects", llm_specific_exc.message)
        
    def test_generic_exception_mapping(self):
        """Test that other exceptions are mapped to a generic LLMAPIError."""
        original_exc = ValueError("Some other error")
        llm_exc = map_exception_to_llm_error(original_exc)
        self.assertIsInstance(llm_exc, LLMAPIError)
        self.assertNotIn(LLMNetworkError, type(llm_exc).__mro__) # Ensure it's not a more specific type
        self.assertIn("Some other error", llm_exc.message)


if __name__ == '__main__':
    unittest.main() 