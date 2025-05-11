"""
Unit tests for the enhanced retry strategy functionality.
"""

import unittest
import time
from unittest.mock import Mock, patch, MagicMock, call
import threading
import random

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
    CircuitBreaker,
    CircuitState,
    _adaptive_wait_strategy,
    retry_all_api_errors,
    get_retry_metrics,
    reset_retry_metrics,
    _circuit_breaker,
    configure_circuit_breaker,
)


class TestCircuitBreaker(unittest.TestCase):
    """Test the enhanced CircuitBreaker implementation."""
    
    def setUp(self):
        # Create a fresh CircuitBreaker for each test
        self.circuit = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=0.1,  # Use small timeout for testing
            half_open_max_calls=2
        )
    
    def test_initial_state(self):
        """Test the initial state of the circuit breaker."""
        self.assertEqual(self.circuit.state, CircuitState.CLOSED)
        self.assertTrue(self.circuit.allow_request())
    
    def test_open_circuit_after_failures(self):
        """Test that the circuit opens after threshold failures."""
        # Create a server error
        error = LLMServerError("Server error")
        
        # Record failures
        self.circuit.record_failure(error)
        self.assertEqual(self.circuit.state, CircuitState.CLOSED)
        
        self.circuit.record_failure(error)
        self.assertEqual(self.circuit.state, CircuitState.CLOSED)
        
        # Third failure should open the circuit
        self.circuit.record_failure(error)
        self.assertEqual(self.circuit.state, CircuitState.OPEN)
        self.assertFalse(self.circuit.allow_request())
    
    def test_ignores_non_monitored_exceptions(self):
        """Test that non-monitored exceptions don't affect the circuit."""
        # Authentication errors are not monitored by default
        error = LLMAuthenticationError("Auth error")
        
        # Record multiple failures
        for _ in range(5):
            self.circuit.record_failure(error)
            
        # Circuit should remain closed
        self.assertEqual(self.circuit.state, CircuitState.CLOSED)
        self.assertTrue(self.circuit.allow_request())
    
    def test_transition_to_half_open(self):
        """Test transition from OPEN to HALF-OPEN after timeout."""
        # Open the circuit
        error = LLMServerError("Server error")
        for _ in range(3):
            self.circuit.record_failure(error)
            
        self.assertEqual(self.circuit.state, CircuitState.OPEN)
        
        # Wait for the timeout
        time.sleep(0.2)  # > recovery_timeout (0.1)
        
        # Circuit should transition to HALF-OPEN
        self.assertEqual(self.circuit.state, CircuitState.HALF_OPEN)
        self.assertTrue(self.circuit.allow_request())
    
    def test_half_open_allows_limited_calls(self):
        """Test that HALF-OPEN state allows a limited number of calls."""
        # Open the circuit and wait for transition to HALF-OPEN
        error = LLMServerError("Server error")
        for _ in range(3):
            self.circuit.record_failure(error)
            
        # Wait for the timeout
        time.sleep(0.2)  # > recovery_timeout (0.1)
        
        # Circuit should now be HALF-OPEN
        self.assertEqual(self.circuit.state, CircuitState.HALF_OPEN)
        
        # Should allow only 2 calls (half_open_max_calls)
        self.assertTrue(self.circuit.allow_request())
        self.assertTrue(self.circuit.allow_request())
        self.assertFalse(self.circuit.allow_request())  # Third request should be rejected
    
    def test_half_open_to_closed_transition(self):
        """Test transition from HALF-OPEN to CLOSED after successful calls."""
        # Open the circuit and wait for transition to HALF-OPEN
        error = LLMServerError("Server error")
        for _ in range(3):
            self.circuit.record_failure(error)
            
        # Wait for the timeout
        time.sleep(0.2)  # > recovery_timeout (0.1)
        
        # Circuit should now be HALF-OPEN
        self.assertEqual(self.circuit.state, CircuitState.HALF_OPEN)
        
        # Record 2 successful calls
        self.circuit.record_success()
        self.assertEqual(self.circuit.state, CircuitState.HALF_OPEN)
        
        self.circuit.record_success()
        self.assertEqual(self.circuit.state, CircuitState.CLOSED)
        self.assertTrue(self.circuit.allow_request())
    
    def test_half_open_to_open_on_failure(self):
        """Test transition from HALF-OPEN to OPEN after failure."""
        # Open the circuit and wait for transition to HALF-OPEN
        error = LLMServerError("Server error")
        for _ in range(3):
            self.circuit.record_failure(error)
            
        # Wait for the timeout
        time.sleep(0.2)  # > recovery_timeout (0.1)
        
        # Circuit should now be HALF-OPEN
        self.assertEqual(self.circuit.state, CircuitState.HALF_OPEN)
        
        # Record a success
        self.circuit.record_success()
        self.assertEqual(self.circuit.state, CircuitState.HALF_OPEN)
        
        # Record a failure
        self.circuit.record_failure(error)
        self.assertEqual(self.circuit.state, CircuitState.OPEN)
        self.assertFalse(self.circuit.allow_request())
    
    def test_manual_reset(self):
        """Test manual circuit breaker reset."""
        # Open the circuit
        error = LLMServerError("Server error")
        for _ in range(3):
            self.circuit.record_failure(error)
            
        self.assertEqual(self.circuit.state, CircuitState.OPEN)
        
        # Reset the circuit
        self.circuit.reset()
        self.assertEqual(self.circuit.state, CircuitState.CLOSED)
        self.assertTrue(self.circuit.allow_request())


class TestAdaptiveWaitStrategy(unittest.TestCase):
    """Test the adaptive wait strategy implementation."""
    
    def test_rate_limit_wait(self):
        """Test wait strategy for rate limit errors."""
        # Create a mock retry state with rate limit error
        retry_state = Mock()
        exception = LLMRateLimitError(
            message="Rate limit exceeded",
            response_data={"headers": {"retry-after": "10"}}
        )
        retry_state.outcome = Mock()
        retry_state.outcome.exception.return_value = exception
        retry_state.attempt_number = 1
        
        # Mock random jitter
        with patch('random.uniform', return_value=0.5):
            wait_time = _adaptive_wait_strategy(retry_state)
            
            # Should use retry-after (10) plus jitter (0.5)
            self.assertEqual(wait_time, 10.5)
    
    def test_timeout_error_wait(self):
        """Test wait strategy for timeout errors."""
        # Create a mock retry state with timeout error
        retry_state = Mock()
        exception = LLMTimeoutError(
            message="Request timed out"
        )
        retry_state.outcome = Mock()
        retry_state.outcome.exception.return_value = exception
        retry_state.attempt_number = 2  # Second attempt
        
        # Mock random jitter
        with patch('random.uniform', return_value=0.3):
            wait_time = _adaptive_wait_strategy(retry_state)
            
            # First attempt multiplier: 1.5, base: 2^(2-1) = 2, jitter: 0.3
            # Expected: min(45, 1.5*2 + 0.3) = 3.3
            self.assertAlmostEqual(wait_time, 3.3)
    
    def test_server_error_wait(self):
        """Test wait strategy for server errors."""
        # Create a mock retry state with server error
        retry_state = Mock()
        exception = LLMServiceUnavailableError(
            message="Service unavailable"
        )
        retry_state.outcome = Mock()
        retry_state.outcome.exception.return_value = exception
        retry_state.attempt_number = 3  # Third attempt
        
        # Mock random jitter
        with patch('random.uniform', return_value=1.2):
            wait_time = _adaptive_wait_strategy(retry_state)
            
            # First attempt multiplier: 3.0, base: 2^(3-1) = 4, jitter: 1.2
            # Expected: min(120, 3.0*4 + 1.2) = 13.2
            self.assertAlmostEqual(wait_time, 13.2)
    
    def test_default_wait(self):
        """Test default wait strategy for other errors."""
        # Create a mock retry state with general API error
        retry_state = Mock()
        exception = LLMAPIError(
            message="General API error"
        )
        retry_state.outcome = Mock()
        retry_state.outcome.exception.return_value = exception
        retry_state.attempt_number = 2  # Second attempt
        
        # Mock random jitter
        with patch('random.uniform', return_value=0.4):
            wait_time = _adaptive_wait_strategy(retry_state)
            
            # Base: 2^2 = 4, jitter: 0.4
            # Expected: min(60, 4 + 0.4) = 4.4
            self.assertAlmostEqual(wait_time, 4.4)
    
    def test_escalating_wait_times(self):
        """Test that wait times escalate with increasing attempt numbers."""
        retry_state = Mock()
        exception = LLMServerError("Server error")
        retry_state.outcome = Mock()
        retry_state.outcome.exception.return_value = exception
        
        # Mock random to always return 0 to eliminate jitter
        with patch('random.uniform', return_value=0):
            # Track wait times for several attempts
            wait_times = []
            for attempt in range(1, 6):
                retry_state.attempt_number = attempt
                wait_time = _adaptive_wait_strategy(retry_state)
                wait_times.append(wait_time)
            
            # Verify each wait time is longer than the previous
            for i in range(1, len(wait_times)):
                self.assertGreater(wait_times[i], wait_times[i-1])


class TestRetryMetrics(unittest.TestCase):
    """Test retry metrics tracking."""
    
    def setUp(self):
        reset_retry_metrics()
    
    def test_metrics_tracking(self):
        """Test that metrics are tracked correctly."""
        # Define a function that will fail and then succeed
        attempt_count = 0
        
        @retry_all_api_errors(max_attempts=3)
        def test_function():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise LLMServerError("Server error")
            return "success"
        
        # Call the function (should eventually succeed)
        result = test_function()
        self.assertEqual(result, "success")
        
        # Check the metrics
        metrics = get_retry_metrics()
        self.assertEqual(metrics["attempts"], 2)  # 2 retry attempts
        self.assertEqual(metrics["successes_after_retry"], 1)  # 1 success after retry
        self.assertEqual(metrics["failures"], 0)  # No overall failures
        self.assertEqual(metrics["errors_by_type"], {"LLMServerError": 2})
    
    def test_failures_tracked(self):
        """Test that failures are tracked correctly."""
        # Define a function that will always fail
        @retry_all_api_errors(max_attempts=2)
        def test_function():
            raise LLMServerError("Server error")
        
        # Call the function (should fail)
        with self.assertRaises(LLMServerError):
            test_function()
        
        # Check the metrics
        metrics = get_retry_metrics()
        self.assertEqual(metrics["attempts"], 1)  # 1 retry attempt
        self.assertEqual(metrics["successes_after_retry"], 0)  # No successes
        self.assertEqual(metrics["failures"], 1)  # 1 overall failure
        self.assertEqual(metrics["errors_by_type"], {"LLMServerError": 1})
    
    def test_reset_metrics(self):
        """Test that metrics can be reset."""
        # First record some metrics
        @retry_all_api_errors(max_attempts=2)
        def test_function():
            raise LLMServerError("Server error")
        
        # Call the function (should fail)
        with self.assertRaises(LLMServerError):
            test_function()
        
        # Verify metrics exist
        metrics = get_retry_metrics()
        self.assertGreater(metrics["attempts"], 0)
        
        # Reset metrics
        reset_retry_metrics()
        
        # Verify metrics are reset
        metrics = get_retry_metrics()
        self.assertEqual(metrics["attempts"], 0)
        self.assertEqual(metrics["successes_after_retry"], 0)
        self.assertEqual(metrics["failures"], 0)
        self.assertEqual(metrics["errors_by_type"], {})


@patch('src.retry_strategy._circuit_breaker')
class TestCircuitBreakerIntegration(unittest.TestCase):
    """Test the integration of the circuit breaker with retry decorators."""
    
    def test_circuit_breaker_open_fails_fast(self, mock_circuit_breaker):
        """Test that open circuit breaker fails fast without retry."""
        # Configure mock circuit breaker
        mock_circuit_breaker.allow_request.return_value = False
        mock_circuit_breaker.state = CircuitState.OPEN
        
        # Define a function with retry
        mock_func = Mock()
        
        @retry_all_api_errors()
        def test_function():
            mock_func()
            return "success"
        
        # Call the function (should fail immediately due to open circuit)
        with self.assertRaises(LLMServiceUnavailableError):
            test_function()
        
        # Verify the function was never called
        mock_func.assert_not_called()
    
    def test_circuit_breaker_half_open_allows_test_requests(self, mock_circuit_breaker):
        """Test that half-open circuit breaker allows test requests."""
        # Configure mock circuit breaker
        mock_circuit_breaker.allow_request.return_value = True
        mock_circuit_breaker.state = CircuitState.HALF_OPEN
        
        # Define a function with retry
        mock_func = Mock()
        mock_func.return_value = "success"
        
        @retry_all_api_errors()
        def test_function():
            return mock_func()
        
        # Call the function (should succeed)
        result = test_function()
        self.assertEqual(result, "success")
        
        # Verify the function was called
        mock_func.assert_called_once()
        
        # Verify circuit success was recorded
        mock_circuit_breaker.record_success.assert_called_once()
    
    @patch('src.retry_strategy._check_circuit_breaker')
    def test_circuit_breaker_records_failures(self, mock_check_circuit, mock_circuit_breaker):
        """Test that circuit breaker records failures with the _check_circuit_breaker function."""
        # Configure mock circuit breaker
        mock_circuit_breaker.allow_request.return_value = True
        
        # Define a function with retry that fails once then succeeds
        attempt_count = 0
        
        @retry_all_api_errors(max_attempts=2)
        def test_function():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count == 1:
                raise LLMServerError("Server error")
            return "success"
        
        # Call the function
        result = test_function()
        self.assertEqual(result, "success")
        
        # Verify that _check_circuit_breaker was called with the error
        mock_check_circuit.assert_called_once()
        args, kwargs = mock_check_circuit.call_args
        self.assertIsInstance(args[0], LLMServerError)


if __name__ == '__main__':
    unittest.main() 