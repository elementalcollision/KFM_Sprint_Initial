"""
Unit tests for the error classifier module in src/error_classifier.py.
"""

import unittest
from unittest.mock import Mock, patch
import json

import google.api_core.exceptions

from src.error_classifier import (
    extract_request_id,
    extract_error_details,
    detect_rate_limit_error,
    detect_authentication_error,
    detect_invalid_request_error,
    detect_service_unavailable_error,
    classify_google_api_exception,
    classify_error
)
from src.exceptions import (
    LLMAPIError,
    LLMTimeoutError,
    LLMConnectionError,
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMInvalidRequestError,
    LLMServiceUnavailableError,
    LLMInternalError
)


class TestRequestIdExtraction(unittest.TestCase):
    """Test the request ID extraction from different response formats."""
    
    def test_extract_from_headers(self):
        """Test extracting request ID from response headers."""
        mock_response = Mock()
        mock_response.headers = {'x-request-id': 'req-123'}
        
        request_id = extract_request_id(mock_response)
        self.assertEqual(request_id, 'req-123')
        
        # Test alternate header names
        mock_response.headers = {'x-goog-request-id': 'req-456'}
        request_id = extract_request_id(mock_response)
        self.assertEqual(request_id, 'req-456')
        
        mock_response.headers = {'request-id': 'req-789'}
        request_id = extract_request_id(mock_response)
        self.assertEqual(request_id, 'req-789')
    
    def test_extract_from_json_response(self):
        """Test extracting request ID from JSON response data."""
        mock_response = Mock()
        mock_response.headers = {}
        
        # Test direct attribute
        mock_response.json = lambda: {'requestId': 'req-123'}
        request_id = extract_request_id(mock_response)
        self.assertEqual(request_id, 'req-123')
        
        # Test alternate field name
        mock_response.json = lambda: {'request_id': 'req-456'}
        request_id = extract_request_id(mock_response)
        self.assertEqual(request_id, 'req-456')
        
        # Test nested field
        mock_response.json = lambda: {'metadata': {'requestId': 'req-789'}}
        request_id = extract_request_id(mock_response)
        self.assertEqual(request_id, None)  # Current implementation doesn't handle nested fields this way
    
    def test_extract_from_request_object(self):
        """Test extracting request ID from request object."""
        mock_request = Mock()
        mock_request.request_id = 'req-123'
        
        mock_response = Mock()
        mock_response.headers = {}
        mock_response.request = mock_request
        
        request_id = extract_request_id(mock_response)
        self.assertEqual(request_id, 'req-123')
    
    def test_no_request_id(self):
        """Test behavior when no request ID is present."""
        mock_response = Mock()
        mock_response.headers = {}
        mock_response.json = lambda: {'data': 'no_request_id_here'}
        
        request_id = extract_request_id(mock_response)
        self.assertIsNone(request_id)


class TestErrorDetailsExtraction(unittest.TestCase):
    """Test extracting error details from different response formats."""
    
    def test_extract_from_response_with_status_code(self):
        """Test extracting error details from a response with status code."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json = lambda: {'error': {'message': 'Invalid request'}}
        
        status_code, error_message, additional_data = extract_error_details(mock_response)
        self.assertEqual(status_code, 400)
        self.assertEqual(error_message, 'Invalid request')
        self.assertEqual(additional_data, {'error': {'message': 'Invalid request'}})
    
    def test_extract_from_response_with_code_attribute(self):
        """Test extracting error details from a response with code attribute."""
        mock_response = Mock()
        mock_response.code = 429
        mock_response.json = lambda: {'error': {'message': 'Rate limit exceeded'}}
        
        status_code, error_message, additional_data = extract_error_details(mock_response)
        self.assertEqual(status_code, 429)
        self.assertEqual(error_message, 'Rate limit exceeded')
    
    def test_extract_from_different_error_formats(self):
        """Test extracting from different error formats."""
        # Standard Google API format
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json = lambda: {'error': {'message': 'Invalid request'}}
        
        _, error_message, _ = extract_error_details(mock_response)
        self.assertEqual(error_message, 'Invalid request')
        
        # Error as string
        mock_response.json = lambda: {'error': 'Something went wrong'}
        _, error_message, _ = extract_error_details(mock_response)
        self.assertEqual(error_message, 'Something went wrong')
        
        # Message at top level
        mock_response.json = lambda: {'message': 'Top level message'}
        _, error_message, _ = extract_error_details(mock_response)
        self.assertEqual(error_message, 'Top level message')
        
        # Description field
        mock_response.json = lambda: {'description': 'Error description'}
        _, error_message, _ = extract_error_details(mock_response)
        self.assertEqual(error_message, 'Error description')
    
    def test_extract_from_text_response(self):
        """Test extracting from text response when JSON parsing fails."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.text = "Internal Server Error"
        
        status_code, error_message, additional_data = extract_error_details(mock_response)
        self.assertEqual(status_code, 500)
        self.assertEqual(error_message, "Internal Server Error")
        self.assertEqual(additional_data, {})
    
    def test_extract_from_exception(self):
        """Test extracting from an exception object."""
        exception = ValueError("Custom error message")
        status_code, error_message, additional_data = extract_error_details(exception)
        
        self.assertIsNone(status_code)
        self.assertEqual(error_message, "Custom error message")
        self.assertEqual(additional_data, {})


class TestErrorDetection(unittest.TestCase):
    """Test the error detection functions."""
    
    def test_detect_rate_limit_error(self):
        """Test detection of rate limit errors."""
        # By status code
        self.assertTrue(detect_rate_limit_error(429, None))
        self.assertFalse(detect_rate_limit_error(400, None))
        
        # By message content
        self.assertTrue(detect_rate_limit_error(None, "Rate limit exceeded"))
        self.assertTrue(detect_rate_limit_error(None, "Quota exceeded, try again later"))
        self.assertTrue(detect_rate_limit_error(None, "Too many requests, please slow down"))
        self.assertTrue(detect_rate_limit_error(None, "Resource exhausted, retry after delay"))
        self.assertTrue(detect_rate_limit_error(None, "Request throttled"))
        self.assertFalse(detect_rate_limit_error(None, "Invalid request format"))
    
    def test_detect_authentication_error(self):
        """Test detection of authentication errors."""
        # By status code
        self.assertTrue(detect_authentication_error(401, None))
        self.assertTrue(detect_authentication_error(403, None))
        self.assertFalse(detect_authentication_error(400, None))
        
        # By message content
        self.assertTrue(detect_authentication_error(None, "Authentication failed"))
        self.assertTrue(detect_authentication_error(None, "Unauthorized access"))
        self.assertTrue(detect_authentication_error(None, "Invalid API key provided"))
        self.assertTrue(detect_authentication_error(None, "Access denied"))
        self.assertTrue(detect_authentication_error(None, "Permission denied"))
        self.assertFalse(detect_authentication_error(None, "Invalid request format"))
    
    def test_detect_invalid_request_error(self):
        """Test detection of invalid request errors."""
        # By status code
        self.assertTrue(detect_invalid_request_error(400, None))
        self.assertTrue(detect_invalid_request_error(404, None))
        self.assertTrue(detect_invalid_request_error(422, None))
        self.assertFalse(detect_invalid_request_error(500, None))
        
        # By message content
        self.assertTrue(detect_invalid_request_error(None, "Invalid request format"))
        self.assertTrue(detect_invalid_request_error(None, "Bad request: missing parameter"))
        self.assertTrue(detect_invalid_request_error(None, "Resource not found"))
        self.assertTrue(detect_invalid_request_error(None, "Validation failed"))
        self.assertTrue(detect_invalid_request_error(None, "Malformed JSON"))
        self.assertFalse(detect_invalid_request_error(None, "Internal server error"))
    
    def test_detect_service_unavailable_error(self):
        """Test detection of service unavailability errors."""
        # By status code
        self.assertTrue(detect_service_unavailable_error(503, None))
        self.assertTrue(detect_service_unavailable_error(502, None))
        self.assertTrue(detect_service_unavailable_error(504, None))
        self.assertFalse(detect_service_unavailable_error(400, None))
        
        # By message content
        self.assertTrue(detect_service_unavailable_error(None, "Service unavailable"))
        self.assertTrue(detect_service_unavailable_error(None, "Server is down for maintenance"))
        self.assertTrue(detect_service_unavailable_error(None, "Service temporarily offline"))
        self.assertTrue(detect_service_unavailable_error(None, "Server overloaded"))
        self.assertTrue(detect_service_unavailable_error(None, "Bad gateway"))
        self.assertFalse(detect_service_unavailable_error(None, "Invalid request format"))


@patch('src.error_classifier.google.api_core.exceptions')
class TestGoogleApiExceptionClassification(unittest.TestCase):
    """Test classification of Google API exceptions."""
    
    def test_classify_too_many_requests(self, mock_exceptions):
        """Test classifying TooManyRequests exception."""
        exception = Mock(spec=mock_exceptions.TooManyRequests)
        exception.__str__.return_value = "Rate limit exceeded"
        mock_exceptions.TooManyRequests = type(exception)
        
        result = classify_google_api_exception(exception)
        self.assertIsInstance(result, LLMRateLimitError)
        self.assertEqual(result.message, "Rate limit exceeded")
        self.assertEqual(result.original_error, exception)
    
    def test_classify_unauthenticated(self, mock_exceptions):
        """Test classifying Unauthenticated exception."""
        exception = Mock(spec=mock_exceptions.Unauthenticated)
        exception.__str__.return_value = "Authentication failed"
        mock_exceptions.Unauthenticated = type(exception)
        
        result = classify_google_api_exception(exception)
        self.assertIsInstance(result, LLMAuthenticationError)
    
    def test_classify_permission_denied(self, mock_exceptions):
        """Test classifying PermissionDenied exception."""
        exception = Mock(spec=mock_exceptions.PermissionDenied)
        exception.__str__.return_value = "Permission denied"
        mock_exceptions.PermissionDenied = type(exception)
        
        result = classify_google_api_exception(exception)
        self.assertIsInstance(result, LLMAuthenticationError)
    
    def test_classify_invalid_argument(self, mock_exceptions):
        """Test classifying InvalidArgument exception."""
        exception = Mock(spec=mock_exceptions.InvalidArgument)
        exception.__str__.return_value = "Invalid argument"
        mock_exceptions.InvalidArgument = type(exception)
        
        result = classify_google_api_exception(exception)
        self.assertIsInstance(result, LLMInvalidRequestError)
    
    def test_classify_deadline_exceeded(self, mock_exceptions):
        """Test classifying DeadlineExceeded exception."""
        exception = Mock(spec=mock_exceptions.DeadlineExceeded)
        exception.__str__.return_value = "Deadline exceeded"
        mock_exceptions.DeadlineExceeded = type(exception)
        
        result = classify_google_api_exception(exception)
        self.assertIsInstance(result, LLMTimeoutError)
    
    def test_classify_service_unavailable(self, mock_exceptions):
        """Test classifying ServiceUnavailable exception."""
        exception = Mock(spec=mock_exceptions.ServiceUnavailable)
        exception.__str__.return_value = "Service unavailable"
        mock_exceptions.ServiceUnavailable = type(exception)
        
        result = classify_google_api_exception(exception)
        self.assertIsInstance(result, LLMServiceUnavailableError)
    
    def test_classify_internal_server_error(self, mock_exceptions):
        """Test classifying InternalServerError exception."""
        exception = Mock(spec=mock_exceptions.InternalServerError)
        exception.__str__.return_value = "Internal server error"
        mock_exceptions.InternalServerError = type(exception)
        
        result = classify_google_api_exception(exception)
        self.assertIsInstance(result, LLMInternalError)
    
    def test_classify_resource_exhausted(self, mock_exceptions):
        """Test classifying ResourceExhausted exception."""
        exception = Mock(spec=mock_exceptions.ResourceExhausted)
        exception.__str__.return_value = "Resource exhausted"
        mock_exceptions.ResourceExhausted = type(exception)
        
        result = classify_google_api_exception(exception)
        self.assertIsInstance(result, LLMRateLimitError)
    
    def test_classify_unknown_google_api_error(self, mock_exceptions):
        """Test classifying an unknown Google API error."""
        exception = Mock(spec=mock_exceptions.GoogleAPIError)
        exception.__str__.return_value = "Unknown Google API error"
        mock_exceptions.GoogleAPIError = type(exception)
        
        result = classify_google_api_exception(exception)
        self.assertIsInstance(result, LLMAPIError)
        self.assertNotIsInstance(result, LLMRateLimitError)
        self.assertNotIsInstance(result, LLMAuthenticationError)


class TestErrorClassification(unittest.TestCase):
    """Test the main error classification function."""
    
    @patch('src.error_classifier.classify_google_api_exception')
    def test_classify_google_api_error(self, mock_classify_google):
        """Test classifying a Google API exception."""
        mock_google_error = Mock(spec=google.api_core.exceptions.GoogleAPIError)
        mock_expected_result = Mock(spec=LLMAPIError)
        mock_classify_google.return_value = mock_expected_result
        
        result = classify_error(mock_google_error)
        mock_classify_google.assert_called_once_with(mock_google_error)
        self.assertEqual(result, mock_expected_result)
    
    @patch('src.error_classifier.map_exception_to_llm_error')
    def test_classify_standard_exception(self, mock_map_exception):
        """Test classifying a standard Python exception."""
        standard_exception = ValueError("Value error")
        mock_expected_result = Mock(spec=LLMAPIError)
        mock_map_exception.return_value = mock_expected_result
        
        result = classify_error(standard_exception)
        mock_map_exception.assert_called_once_with(standard_exception)
        self.assertEqual(result, mock_expected_result)
    
    def test_classify_response_with_status_code(self):
        """Test classifying a response with status code."""
        # Authentication error (401)
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json = lambda: {'error': {'message': 'Authentication failed'}}
        mock_response.headers = {}
        
        result = classify_error(mock_response)
        self.assertIsInstance(result, LLMAuthenticationError)
        self.assertEqual(result.status_code, 401)
        
        # Rate limit error (429)
        mock_response.status_code = 429
        mock_response.json = lambda: {'error': {'message': 'Rate limit exceeded'}}
        
        result = classify_error(mock_response)
        self.assertIsInstance(result, LLMRateLimitError)
        self.assertEqual(result.status_code, 429)
        
        # Invalid request error (400)
        mock_response.status_code = 400
        mock_response.json = lambda: {'error': {'message': 'Invalid request format'}}
        
        result = classify_error(mock_response)
        self.assertIsInstance(result, LLMInvalidRequestError)
        self.assertEqual(result.status_code, 400)
        
        # Service unavailable error (503)
        mock_response.status_code = 503
        mock_response.json = lambda: {'error': {'message': 'Service temporarily unavailable'}}
        
        result = classify_error(mock_response)
        self.assertIsInstance(result, LLMServiceUnavailableError)
        self.assertEqual(result.status_code, 503)
        
        # Internal server error (500)
        mock_response.status_code = 500
        mock_response.json = lambda: {'error': {'message': 'Internal server error'}}
        
        result = classify_error(mock_response)
        self.assertIsInstance(result, LLMInternalError)
        self.assertEqual(result.status_code, 500)
    
    def test_classify_response_without_status_code(self):
        """Test classifying a response without status code, using message patterns."""
        mock_response = Mock()
        # No status_code attribute
        mock_response.json = lambda: {'error': {'message': 'Authentication failed'}}
        mock_response.headers = {}
        
        result = classify_error(mock_response)
        self.assertIsInstance(result, LLMAuthenticationError)
        
        # Rate limit message
        mock_response.json = lambda: {'error': {'message': 'Rate limit exceeded'}}
        result = classify_error(mock_response)
        self.assertIsInstance(result, LLMRateLimitError)
        
        # Invalid request message
        mock_response.json = lambda: {'error': {'message': 'Invalid request format'}}
        result = classify_error(mock_response)
        self.assertIsInstance(result, LLMInvalidRequestError)
        
        # Service unavailable message
        mock_response.json = lambda: {'error': {'message': 'Service temporarily unavailable'}}
        result = classify_error(mock_response)
        self.assertIsInstance(result, LLMServiceUnavailableError)
    
    def test_classify_unrecognized_error(self):
        """Test classifying an unrecognized error type."""
        mock_response = Mock()
        mock_response.status_code = 418  # I'm a teapot
        mock_response.json = lambda: {'error': {'message': 'I am a teapot'}}
        mock_response.headers = {}
        
        result = classify_error(mock_response)
        self.assertIsInstance(result, LLMAPIError)
        self.assertNotIsInstance(result, LLMRateLimitError)
        self.assertNotIsInstance(result, LLMAuthenticationError)
        self.assertNotIsInstance(result, LLMInvalidRequestError)
        self.assertNotIsInstance(result, LLMServiceUnavailableError)
        self.assertNotIsInstance(result, LLMInternalError)


if __name__ == '__main__':
    unittest.main() 