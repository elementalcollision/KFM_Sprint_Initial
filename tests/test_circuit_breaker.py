"""
Unit tests for the CircuitBreaker class in src/error_recovery.py.

This module tests the circuit breaker pattern implementation,
including error threshold tracking, state transitions, and recovery.
"""

import unittest
import time
from unittest.mock import patch, MagicMock, Mock

from src.error_recovery import CircuitBreaker
from src.exceptions import (
    CircuitBreakerOpenError,
    LLMAPIError,
    LLMNetworkError
)


class TestCircuitBreaker(unittest.TestCase):
    """Test suite for the CircuitBreaker class."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Create a circuit breaker with known parameters for testing
        self.breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=5.0,
            half_open_success_threshold=2
        )
    
    def test_initialization(self):
        """Test that the circuit breaker initializes with correct values."""
        self.assertEqual(self.breaker.failure_threshold, 3)
        self.assertEqual(self.breaker.recovery_timeout, 5.0)
        self.assertEqual(self.breaker.half_open_success_threshold, 2)
        self.assertEqual(self.breaker.state, "CLOSED")
        self.assertEqual(self.breaker.failure_count, 0)
    
    def test_execute_success_closed_state(self):
        """Test successful execution in closed state."""
        # Create a function that succeeds
        func = Mock(return_value="Success")
        
        # Execute through circuit breaker
        result = self.breaker.execute(func, "arg1", kwarg1="test")
        
        # Check function was called and result returned
        func.assert_called_once_with("arg1", kwarg1="test")
        self.assertEqual(result, "Success")
        
        # State should still be closed, failure count should be reset
        self.assertEqual(self.breaker.state, "CLOSED")
        self.assertEqual(self.breaker.failure_count, 0)
    
    def test_execute_failure_below_threshold(self):
        """Test handling failures below the threshold."""
        # Create a function that fails
        error = LLMNetworkError("Network error")
        func = Mock(side_effect=error)
        
        # Execute through circuit breaker, should re-raise the error
        with self.assertRaises(LLMNetworkError):
            self.breaker.execute(func)
        
        # State should still be closed, but failure count should increment
        self.assertEqual(self.breaker.state, "CLOSED")
        self.assertEqual(self.breaker.failure_count, 1)
    
    def test_transition_to_open_state(self):
        """Test transition to open state when failures exceed threshold."""
        # Create a function that always fails
        error = LLMNetworkError("Network error")
        func = Mock(side_effect=error)
        
        # Cause enough failures to trip the breaker
        for _ in range(3):  # failure_threshold is 3
            with self.assertRaises(LLMNetworkError):
                self.breaker.execute(func)
        
        # State should now be open
        self.assertEqual(self.breaker.state, "OPEN")
        
        # Now calling again should raise CircuitBreakerOpenError without calling func
        func.reset_mock()
        with self.assertRaises(CircuitBreakerOpenError):
            self.breaker.execute(func)
        
        # Function should not have been called
        func.assert_not_called()
    
    def test_recovery_timeout_transition_to_half_open(self):
        """Test transition to half-open state after recovery timeout."""
        # Set breaker to open state
        self.breaker.state = "OPEN"
        self.breaker.open_time = time.time() - 6.0  # 6 seconds ago (> recovery_timeout)
        
        # Create a function that will succeed
        func = Mock(return_value="Success")
        
        # Execute - should switch to half-open and try the function
        result = self.breaker.execute(func)
        
        # Should have switched to half-open and executed successfully
        self.assertEqual(self.breaker.state, "HALF_OPEN")
        self.assertEqual(result, "Success")
        self.assertEqual(self.breaker.success_count, 1)
    
    def test_half_open_success_transition_to_closed(self):
        """Test transition from half-open to closed after enough successes."""
        # Set breaker to half-open state
        self.breaker.state = "HALF_OPEN"
        self.breaker.success_count = 1  # One success already recorded
        
        # Create a function that will succeed
        func = Mock(return_value="Success")
        
        # Execute - should count as second success and close the circuit
        result = self.breaker.execute(func)
        
        # Should have switched to closed and returned result
        self.assertEqual(self.breaker.state, "CLOSED")
        self.assertEqual(result, "Success")
        self.assertEqual(self.breaker.failure_count, 0)  # Reset
    
    def test_half_open_failure_transition_to_open(self):
        """Test transition from half-open back to open on failure."""
        # Set breaker to half-open state
        self.breaker.state = "HALF_OPEN"
        self.breaker.success_count = 1
        
        # Create a function that will fail
        error = LLMAPIError("API error")
        func = Mock(side_effect=error)
        
        # Execute - should fail and reopen circuit
        with self.assertRaises(LLMAPIError):
            self.breaker.execute(func)
        
        # Should have reopened the circuit
        self.assertEqual(self.breaker.state, "OPEN")
        self.assertEqual(self.breaker.success_count, 0)  # Reset
    
    def test_reset(self):
        """Test manually resetting the circuit breaker."""
        # Set breaker to open state with some counts
        self.breaker.state = "OPEN"
        self.breaker.failure_count = 5
        self.breaker.success_count = 1
        
        # Reset the breaker
        self.breaker.reset()
        
        # Should be back to initial state
        self.assertEqual(self.breaker.state, "CLOSED")
        self.assertEqual(self.breaker.failure_count, 0)
        self.assertEqual(self.breaker.success_count, 0)
    
    def test_is_allowed_to_execute(self):
        """Test the is_allowed_to_execute method."""
        # Closed state
        self.breaker.state = "CLOSED"
        self.assertTrue(self.breaker.is_allowed_to_execute())
        
        # Open state, not timed out
        self.breaker.state = "OPEN"
        self.breaker.open_time = time.time()  # Just now
        self.assertFalse(self.breaker.is_allowed_to_execute())
        
        # Open state, timed out
        self.breaker.open_time = time.time() - 6.0  # 6 seconds ago
        self.assertTrue(self.breaker.is_allowed_to_execute())
        
        # Half-open state
        self.breaker.state = "HALF_OPEN"
        self.assertTrue(self.breaker.is_allowed_to_execute())
    
    def test_get_failure_rate(self):
        """Test calculating failure rate."""
        # Set some state
        self.breaker.failure_count = 3
        self.breaker.request_count = 10
        
        # Calculate rate
        rate = self.breaker.get_failure_rate()
        
        # Should be failures/requests
        self.assertEqual(rate, 0.3)  # 3/10 = 0.3
        
        # Test with zero requests
        self.breaker.request_count = 0
        rate = self.breaker.get_failure_rate()
        self.assertEqual(rate, 0.0)  # Should handle zero division
    
    def test_get_state_description(self):
        """Test state description."""
        descriptions = {
            "CLOSED": self.breaker._get_state_description("CLOSED"),
            "OPEN": self.breaker._get_state_description("OPEN"),
            "HALF_OPEN": self.breaker._get_state_description("HALF_OPEN"),
            "UNKNOWN": self.breaker._get_state_description("UNKNOWN")
        }
        
        # Should return descriptive text for each state
        self.assertIn("allowing all requests", descriptions["CLOSED"].lower())
        self.assertIn("blocking all requests", descriptions["OPEN"].lower())
        self.assertIn("test", descriptions["HALF_OPEN"].lower())
        self.assertIn("unknown", descriptions["UNKNOWN"].lower())
    
    def test_get_status(self):
        """Test retrieving breaker status."""
        # Set some state
        self.breaker.state = "CLOSED"
        self.breaker.failure_count = 2
        self.breaker.request_count = 15
        
        # Get status
        status = self.breaker.get_status()
        
        # Check status fields
        self.assertEqual(status["state"], "CLOSED")
        self.assertEqual(status["failure_count"], 2)
        self.assertEqual(status["request_count"], 15)
        self.assertEqual(status["failure_rate"], 2/15)
        self.assertEqual(status["failure_threshold"], 3)
        self.assertIn("description", status)
    
    def test_allow_request(self):
        """Test the allow_request method used for external checking."""
        # Closed state
        self.breaker.state = "CLOSED"
        self.assertTrue(self.breaker.allow_request())
        
        # Open state
        self.breaker.state = "OPEN"
        self.breaker.open_time = time.time()  # Just now
        self.assertFalse(self.breaker.allow_request())
        
        # Half-open state
        self.breaker.state = "HALF_OPEN"
        self.assertTrue(self.breaker.allow_request())
    
    def test_integration_with_multiple_calls(self):
        """Integration test with a realistic sequence of calls."""
        # Create a function that succeeds at first, then fails repeatedly
        func = Mock(side_effect=[
            "Success 1",
            "Success 2",
            LLMNetworkError("Error 1"),
            LLMNetworkError("Error 2"),
            LLMNetworkError("Error 3"),  # This should trip the breaker
            "Success 3",  # This won't be called due to open circuit
        ])
        
        # Execute successful calls
        for i in range(2):
            result = self.breaker.execute(func)
            self.assertEqual(result, f"Success {i+1}")
            self.assertEqual(self.breaker.state, "CLOSED")
        
        # Execute failing calls
        for i in range(2):
            with self.assertRaises(LLMNetworkError):
                self.breaker.execute(func)
            self.assertEqual(self.breaker.state, "CLOSED")
            self.assertEqual(self.breaker.failure_count, i+1)
        
        # Execute final failing call that should trip the breaker
        with self.assertRaises(LLMNetworkError):
            self.breaker.execute(func)
        self.assertEqual(self.breaker.state, "OPEN")
        
        # Now calls should be blocked without calling the function
        with self.assertRaises(CircuitBreakerOpenError):
            self.breaker.execute(func)
        
        # Function should have been called exactly 5 times (not 6)
        self.assertEqual(func.call_count, 5)
        
        # Simulate timeout and transition to half-open
        self.breaker.open_time = time.time() - 6.0
        
        # Create a new function that will succeed twice to close the circuit
        success_func = Mock(return_value="Recovery Success")
        
        # First success in half-open
        result = self.breaker.execute(success_func)
        self.assertEqual(result, "Recovery Success")
        self.assertEqual(self.breaker.state, "HALF_OPEN")
        self.assertEqual(self.breaker.success_count, 1)
        
        # Second success should close the circuit
        result = self.breaker.execute(success_func)
        self.assertEqual(result, "Recovery Success")
        self.assertEqual(self.breaker.state, "CLOSED")


if __name__ == '__main__':
    unittest.main() 