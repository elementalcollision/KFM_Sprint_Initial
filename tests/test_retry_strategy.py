"""
Unit tests for the retry strategy module in src/retry_strategy.py.
"""

import unittest
import time
from unittest.mock import Mock, patch, MagicMock, call
import random

import tenacity
from tenacity.wait import wait_base
from tenacity.stop import stop_base

from src.exceptions import (
    LLMAPIError,
    LLMNetworkError,
    LLMTimeoutError,
    LLMConnectionError,
    LLMRateLimitError,
    LLMServerError,
    LLMServiceUnavailableError,
    LLMInternalError,
    LLMAuthenticationError,
    LLMInvalidRequestError,
)
from src.retry_strategy import (
    _is_retryable_exception,
    _extract_retry_after,
    _check_circuit_breaker,
    _reset_circuit_on_success,
    _rate_limit_wait_strategy,
    _before_retry_log,
    retry_on_network_errors,
    retry_on_rate_limit,
    retry_on_server_errors,
    retry_all_api_errors,
    configure_circuit_breaker,
    _circuit_state,
)


class TestRetryableDetection(unittest.TestCase):
    """Test detection of retryable exceptions."""
    
    def test_retryable_exceptions(self):
        """Test that retryable exceptions are correctly detected."""
        # Network errors are retryable
        self.assertTrue(_is_retryable_exception(LLMNetworkError("Network error")))
        self.assertTrue(_is_retryable_exception(LLMTimeoutError("Timeout")))
        self.assertTrue(_is_retryable_exception(LLMConnectionError("Connection error")))
        
        # Rate limit errors are retryable
        self.assertTrue(_is_retryable_exception(LLMRateLimitError("Rate limit")))
        
        # Server errors are retryable
        self.assertTrue(_is_retryable_exception(LLMServerError("Server error")))
        self.assertTrue(_is_retryable_exception(LLMServiceUnavailableError("Service unavailable")))
        self.assertTrue(_is_retryable_exception(LLMInternalError("Internal error")))
    
    def test_non_retryable_exceptions(self):
        """Test that non-retryable exceptions are correctly detected."""
        # Base API error is not retryable
        self.assertFalse(_is_retryable_exception(LLMAPIError("API error")))
        
        # Authentication errors are not retryable
        self.assertFalse(_is_retryable_exception(LLMAuthenticationError("Auth error")))
        
        # Invalid request errors are not retryable
        self.assertFalse(_is_retryable_exception(LLMInvalidRequestError("Invalid request")))
        
        # Other exceptions are not retryable
        self.assertFalse(_is_retryable_exception(ValueError("Value error")))


class TestRetryAfterExtraction(unittest.TestCase):
    """Test extraction of retry-after header from response data."""
    
    def test_extract_numeric_retry_after(self):
        """Test extracting numeric retry-after values."""
        error = LLMRateLimitError(
            message="Rate limit exceeded",
            response_data={"headers": {"retry-after": "30"}}
        )
        self.assertEqual(_extract_retry_after(error), 30.0)
        
        # Test with uppercase header
        error = LLMRateLimitError(
            message="Rate limit exceeded",
            response_data={"headers": {"Retry-After": "60"}}
        )
        self.assertEqual(_extract_retry_after(error), 60.0)
    
    def test_extract_http_date_retry_after(self):
        """Test extracting HTTP date retry-after values."""
        # This test is more complex as it involves time parsing
        # We'll mock the relevant parts
        with patch('email.utils.parsedate') as mock_parsedate:
            with patch('calendar.timegm') as mock_timegm:
                with patch('time.time') as mock_time:
                    # Setup mocks
                    mock_parsedate.return_value = (2023, 5, 1, 12, 0, 0, 0, 0, 0)
                    mock_timegm.return_value = 1682942400  # May 1, 2023 12:00:00 UTC
                    mock_time.return_value = 1682942100  # 5 minutes earlier
                    
                    error = LLMRateLimitError(
                        message="Rate limit exceeded",
                        response_data={"headers": {"retry-after": "Mon, 01 May 2023 12:00:00 GMT"}}
                    )
                    
                    self.assertEqual(_extract_retry_after(error), 300.0)  # 5 minutes difference
    
    def test_no_retry_after(self):
        """Test when no retry-after header is present."""
        error = LLMRateLimitError(
            message="Rate limit exceeded",
            response_data={"headers": {}}
        )
        self.assertIsNone(_extract_retry_after(error))
        
        # Test non-rate limit error
        error = LLMAPIError("General error")
        self.assertIsNone(_extract_retry_after(error))
        
        # Test non-LLM API error
        error = ValueError("Value error")
        self.assertIsNone(_extract_retry_after(error))


class TestCircuitBreaker(unittest.TestCase):
    """Test circuit breaker functionality."""
    
    def setUp(self):
        """Reset circuit breaker state before each test."""
        global _circuit_state
        _circuit_state = {
            "failures": 0,
            "last_failure_time": 0,
            "open": False,
            "threshold": 5,
            "reset_timeout": 60,
        }
    
    def test_circuit_breaker_threshold(self):
        """Test that circuit opens after threshold failures."""
        for i in range(4):
            # First 4 errors - circuit stays closed
            self.assertTrue(_check_circuit_breaker(LLMServerError()))
            self.assertFalse(_circuit_state["open"])
        
        # 5th error - circuit opens
        self.assertTrue(_check_circuit_breaker(LLMServerError()))
        self.assertTrue(_circuit_state["open"])
    
    def test_circuit_breaker_reset(self):
        """Test that circuit resets after timeout."""
        # Open the circuit
        for i in range(5):
            _check_circuit_breaker(LLMServerError())
        
        self.assertTrue(_circuit_state["open"])
        
        # Set the last failure time to more than the reset timeout ago
        _circuit_state["last_failure_time"] = time.time() - 61
        
        # Check again - should reset and close the circuit
        self.assertTrue(_check_circuit_breaker(LLMServerError()))
        self.assertFalse(_circuit_state["open"])  # Circuit should be closed now
        self.assertEqual(_circuit_state["failures"], 1)  # Failures reset to 0 and new failure added
    
    def test_circuit_breaker_open_rejects_requests(self):
        """Test that open circuit prevents retries."""
        # Open the circuit
        for i in range(5):
            _check_circuit_breaker(LLMServerError())
        
        self.assertTrue(_circuit_state["open"])
        
        # Set last failure time to recent
        _circuit_state["last_failure_time"] = time.time()
        
        # Circuit should reject new requests
        self.assertFalse(_check_circuit_breaker(LLMServerError()))
    
    def test_reset_on_success(self):
        """Test circuit breaker reset on successful calls."""
        # Add some failures but not enough to open circuit
        _circuit_state["failures"] = 3
        
        # Reset on success
        _reset_circuit_on_success()
        
        self.assertEqual(_circuit_state["failures"], 0)
        self.assertFalse(_circuit_state["open"])
        
        # Open the circuit and then reset
        _circuit_state["failures"] = 5
        _circuit_state["open"] = True
        
        _reset_circuit_on_success()
        
        self.assertEqual(_circuit_state["failures"], 0)
        self.assertFalse(_circuit_state["open"])
    
    def test_configure_circuit_breaker(self):
        """Test circuit breaker configuration."""
        # Default values
        self.assertEqual(_circuit_state["threshold"], 5)
        self.assertEqual(_circuit_state["reset_timeout"], 60)
        
        # Configure new values
        configure_circuit_breaker(threshold=10, reset_timeout=120)
        
        self.assertEqual(_circuit_state["threshold"], 10)
        self.assertEqual(_circuit_state["reset_timeout"], 120)


class TestWaitStrategies(unittest.TestCase):
    """Test retry wait strategies."""
    
    @patch('random.uniform')
    def test_rate_limit_wait_with_retry_after(self, mock_uniform):
        """Test rate limit wait strategy with retry-after header."""
        mock_uniform.return_value = 1.0  # Fixed jitter
        
        # Create mock retry state
        retry_state = Mock()
        exception = LLMRateLimitError(
            message="Rate limit exceeded",
            response_data={"headers": {"retry-after": "30"}}
        )
        retry_state.outcome = Mock()
        retry_state.outcome.exception.return_value = exception
        
        wait_time = _rate_limit_wait_strategy(retry_state)
        
        # Should use retry-after value (30) plus jitter (1.0)
        self.assertEqual(wait_time, 31.0)
        mock_uniform.assert_called_once_with(0, 3.0)  # 10% of 30 is 3.0
    
    @patch('random.uniform')
    def test_rate_limit_wait_without_retry_after(self, mock_uniform):
        """Test rate limit wait strategy without retry-after header."""
        mock_uniform.return_value = 2.0  # Fixed jitter
        
        # Create mock retry state with no retry-after
        retry_state = Mock()
        exception = LLMRateLimitError(
            message="Rate limit exceeded",
            response_data={"headers": {}}
        )
        retry_state.outcome = Mock()
        retry_state.outcome.exception.return_value = exception
        retry_state.attempt_number = 2  # Second attempt
        
        wait_time = _rate_limit_wait_strategy(retry_state)
        
        # Should use exponential backoff: 2^2 = 4, plus jitter (2.0)
        self.assertEqual(wait_time, 6.0)
        mock_uniform.assert_called_once_with(0, 0.4)  # 10% of 4 is 0.4
    
    @patch('random.uniform')
    def test_rate_limit_wait_with_large_attempt_number(self, mock_uniform):
        """Test rate limit wait strategy with large attempt number."""
        mock_uniform.return_value = 3.0  # Fixed jitter
        
        # Create mock retry state with large attempt number
        retry_state = Mock()
        exception = LLMRateLimitError(
            message="Rate limit exceeded",
            response_data={"headers": {}}
        )
        retry_state.outcome = Mock()
        retry_state.outcome.exception.return_value = exception
        retry_state.attempt_number = 10  # Large attempt number
        
        wait_time = _rate_limit_wait_strategy(retry_state)
        
        # Should cap at max wait time (60) plus jitter (3.0)
        self.assertEqual(wait_time, 63.0)


@patch('logging.Logger.warning')
class TestRetryLogging(unittest.TestCase):
    """Test retry logging functionality."""
    
    def test_before_retry_log(self, mock_warning):
        """Test logging before retry attempts."""
        # Create mock retry state
        retry_state = Mock()
        exception = LLMRateLimitError("Rate limit exceeded")
        retry_state.outcome = Mock()
        retry_state.outcome.exception.return_value = exception
        retry_state.attempt_number = 2  # Second attempt
        
        # Mock the stop strategy's max_attempt_number attribute
        retry_state.retry_object.stop = Mock()
        retry_state.retry_object.stop.max_attempt_number = 5
        
        _before_retry_log(retry_state)
        
        # Verify log message
        mock_warning.assert_called_once_with(
            "Retrying API call due to %s: %s (attempt %d/%d)",
            "LLMRateLimitError",
            "Rate limit exceeded",
            2,
            5
        )
    
    def test_before_retry_log_without_max_attempts(self, mock_warning):
        """Test logging before retry when max attempts is not defined."""
        # Create mock retry state
        retry_state = Mock()
        exception = LLMRateLimitError("Rate limit exceeded")
        retry_state.outcome = Mock()
        retry_state.outcome.exception.return_value = exception
        retry_state.attempt_number = 2  # Second attempt
        
        # Mock the stop strategy without max_attempt_number
        retry_state.retry_object.stop = Mock(spec=stop_base)
        
        _before_retry_log(retry_state)
        
        # Verify log message with infinity symbol
        mock_warning.assert_called_once_with(
            "Retrying API call due to %s: %s (attempt %d/%d)",
            "LLMRateLimitError",
            "Rate limit exceeded",
            2,
            "∞"
        )


class TestRetryDecorators(unittest.TestCase):
    """Test the retry decorator functions."""
    
    def test_retry_on_network_errors_decorator(self):
        """Test the retry_on_network_errors decorator."""
        # We'll inspect the decorator's retry configuration
        decorator = retry_on_network_errors(max_attempts=3, min_wait=1.0, max_wait=5.0)
        
        # Check that it's a tenacity.retry decorator
        self.assertTrue(hasattr(decorator, "__retry_state_key__"))
        
        # Use the decorator on a test function
        @decorator
        def test_func():
            pass
        
        # Verify retry configuration
        retry_state = test_func.__retry_state_key__
        
        # Check the stop strategy
        self.assertIsInstance(retry_state.kwargs["stop"], tenacity.stop_after_attempt)
        self.assertEqual(retry_state.kwargs["stop"].max_attempt_number, 3)
        
        # Check the wait strategy
        self.assertIsInstance(retry_state.kwargs["wait"], tenacity.wait_random_exponential)
        
        # Check the retry condition
        self.assertIsInstance(retry_state.kwargs["retry"], tenacity.retry_if_exception)
    
    def test_retry_on_rate_limit_decorator(self):
        """Test the retry_on_rate_limit decorator."""
        decorator = retry_on_rate_limit(max_attempts=5, max_delay=300.0)
        
        # Use the decorator on a test function
        @decorator
        def test_func():
            pass
        
        # Verify retry configuration
        retry_state = test_func.__retry_state_key__
        
        # Check the stop strategy
        self.assertIsInstance(retry_state.kwargs["stop"], tenacity.stop_after_attempt)
        self.assertEqual(retry_state.kwargs["stop"].max_attempt_number, 5)
        
        # Check the wait strategy is our custom function
        self.assertEqual(retry_state.kwargs["wait"], _rate_limit_wait_strategy)
        
        # Check the retry condition matches LLMRateLimitError
        self.assertIsInstance(retry_state.kwargs["retry"], tenacity.retry_if_exception_type)
        self.assertEqual(retry_state.kwargs["retry"].exception, LLMRateLimitError)
    
    def test_retry_on_server_errors_decorator(self):
        """Test the retry_on_server_errors decorator."""
        decorator = retry_on_server_errors(max_attempts=3, min_wait=2.0, max_wait=10.0)
        
        # Use the decorator on a test function
        @decorator
        def test_func():
            pass
        
        # Verify retry configuration
        retry_state = test_func.__retry_state_key__
        
        # Check the stop strategy
        self.assertIsInstance(retry_state.kwargs["stop"], tenacity.stop_after_attempt)
        self.assertEqual(retry_state.kwargs["stop"].max_attempt_number, 3)
        
        # Check the wait strategy
        self.assertIsInstance(retry_state.kwargs["wait"], tenacity.wait_random_exponential)
        
        # Check the retry condition
        self.assertIsInstance(retry_state.kwargs["retry"], tenacity.retry_if_exception)


class TestRetryAllApiErrors(unittest.TestCase):
    """Test the retry_all_api_errors decorator with circuit breaker."""
    
    def setUp(self):
        """Reset circuit breaker state before each test."""
        global _circuit_state
        _circuit_state = {
            "failures": 0,
            "last_failure_time": 0,
            "open": False,
            "threshold": 5,
            "reset_timeout": 60,
        }
    
    def test_circuit_breaker_open_prevents_calls(self):
        """Test that an open circuit breaker prevents calls."""
        # Create test function with retry decorator
        @retry_all_api_errors(max_attempts=3)
        def test_func():
            return "Success"
        
        # Open the circuit breaker
        _circuit_state["open"] = True
        _circuit_state["last_failure_time"] = time.time()
        
        # Call should raise LLMServiceUnavailableError
        with self.assertRaises(LLMServiceUnavailableError) as context:
            test_func()
        
        self.assertIn("Circuit breaker is open", str(context.exception))
    
    def test_circuit_reset_on_success(self):
        """Test that successful calls reset the circuit breaker."""
        # Create a counter to track calls
        call_count = 0
        
        # Create test function with retry decorator
        @retry_all_api_errors(max_attempts=3)
        def test_func():
            nonlocal call_count
            call_count += 1
            return "Success"
        
        # Set some failures but not enough to open circuit
        _circuit_state["failures"] = 3
        
        # Call should succeed and reset the circuit breaker
        result = test_func()
        self.assertEqual(result, "Success")
        self.assertEqual(call_count, 1)
        
        # Circuit breaker should be reset
        self.assertEqual(_circuit_state["failures"], 0)
        self.assertFalse(_circuit_state["open"])
    
    @patch('src.retry_strategy._check_circuit_breaker')
    def test_circuit_updated_on_failure(self, mock_check_circuit):
        """Test that circuit breaker state is updated on failures."""
        mock_check_circuit.return_value = True  # Allow retry
        
        # Create a counter to track calls
        call_count = 0
        
        # Create test function with retry decorator
        @retry_all_api_errors(max_attempts=2)
        def test_func():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise LLMServerError("Server error")
            return "Success"
        
        # Call should fail after max attempts and update circuit breaker
        with self.assertRaises(LLMServerError):
            test_func()
        
        self.assertEqual(call_count, 2)  # 2 attempts (original + 1 retry)
        mock_check_circuit.assert_called_with(LLMServerError("Server error"))
    
    def test_ignore_circuit_breaker(self):
        """Test that circuit breaker can be ignored."""
        # Create test function with circuit breaker ignored
        @retry_all_api_errors(max_attempts=3, ignore_circuit_breaker=True)
        def test_func():
            return "Success"
        
        # Open the circuit breaker
        _circuit_state["open"] = True
        _circuit_state["last_failure_time"] = time.time()
        
        # Call should succeed despite open circuit breaker
        result = test_func()
        self.assertEqual(result, "Success")
        
        # Circuit breaker should remain open
        self.assertTrue(_circuit_state["open"])


if __name__ == '__main__':
    unittest.main() 