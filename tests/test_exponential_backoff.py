"""
Unit tests for the ExponentialBackoffStrategy class in src/retry_strategy.py.

This module tests the exponential backoff strategy for retrying operations,
including jitter, max retries, and backoff calculations.
"""

import unittest
import time
from unittest.mock import patch, MagicMock, Mock

from src.retry_strategy import ExponentialBackoffStrategy
from src.exceptions import (
    LLMAPIError,
    LLMNetworkError,
    LLMTimeoutError,
    LLMRateLimitError
)


class TestExponentialBackoffStrategy(unittest.TestCase):
    """Test suite for the ExponentialBackoffStrategy class."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Create a strategy with known parameters for testing
        self.strategy = ExponentialBackoffStrategy(
            base_delay=1.0,
            max_delay=32.0,
            max_retries=5,
            jitter=0.2,
            rate_limit_delay_multiplier=2.0
        )
    
    def test_initialization(self):
        """Test that the strategy initializes with correct values."""
        self.assertEqual(self.strategy.base_delay, 1.0)
        self.assertEqual(self.strategy.max_delay, 32.0)
        self.assertEqual(self.strategy.max_retries, 5)
        self.assertEqual(self.strategy.jitter, 0.2)
        self.assertEqual(self.strategy.rate_limit_delay_multiplier, 2.0)
    
    def test_should_retry_network_error(self):
        """Test retry decision for network errors."""
        # Network errors should be retried
        error = LLMNetworkError("Network timeout")
        result = self.strategy.should_retry(error, 2)
        self.assertTrue(result)
    
    def test_should_retry_timeout_error(self):
        """Test retry decision for timeout errors."""
        # Timeout errors should be retried
        error = LLMTimeoutError("Operation timed out")
        result = self.strategy.should_retry(error, 3)
        self.assertTrue(result)
    
    def test_should_retry_rate_limit_error(self):
        """Test retry decision for rate limit errors."""
        # Rate limit errors should be retried
        error = LLMRateLimitError("Too many requests")
        result = self.strategy.should_retry(error, 1)
        self.assertTrue(result)
    
    def test_should_not_retry_invalid_request(self):
        """Test retry decision for errors that shouldn't be retried."""
        # Some errors should not be retried
        error = LLMAPIError("Invalid request format")
        result = self.strategy.should_retry(error, 1)
        self.assertFalse(result)
    
    def test_should_not_retry_beyond_max(self):
        """Test that retries stop after max_retries."""
        # After max_retries, should return False even for retryable errors
        error = LLMNetworkError("Network error")
        result = self.strategy.should_retry(error, 5)  # 5 is equal to max_retries
        self.assertFalse(result)
    
    def test_calculate_delay_standard(self):
        """Test delay calculation for standard errors."""
        # Test exponential increase (without jitter effect)
        with patch('random.uniform', return_value=0):  # Remove jitter for testing
            # First retry: base_delay * 2^0 = 1.0
            delay = self.strategy.calculate_delay(LLMNetworkError("Error"), 0)
            self.assertEqual(delay, 1.0)
            
            # Second retry: base_delay * 2^1 = 2.0
            delay = self.strategy.calculate_delay(LLMNetworkError("Error"), 1)
            self.assertEqual(delay, 2.0)
            
            # Third retry: base_delay * 2^2 = 4.0
            delay = self.strategy.calculate_delay(LLMNetworkError("Error"), 2)
            self.assertEqual(delay, 4.0)
    
    def test_calculate_delay_with_jitter(self):
        """Test that jitter is properly applied to delay."""
        # With jitter of 0.2, delay should be in range [0.8*base, 1.2*base]
        with patch('random.uniform', return_value=0.1):  # Jitter of 0.1 (from range -0.2 to 0.2)
            delay = self.strategy.calculate_delay(LLMNetworkError("Error"), 0)
            # Expected: 1.0 * (1 + 0.1) = 1.1
            self.assertAlmostEqual(delay, 1.1, places=1)
        
        with patch('random.uniform', return_value=-0.1):  # Negative jitter
            delay = self.strategy.calculate_delay(LLMNetworkError("Error"), 0)
            # Expected: 1.0 * (1 - 0.1) = 0.9
            self.assertAlmostEqual(delay, 0.9, places=1)
    
    def test_calculate_delay_rate_limit(self):
        """Test delay calculation for rate limit errors."""
        # Rate limit errors have a multiplier (2.0)
        with patch('random.uniform', return_value=0):  # Remove jitter for testing
            delay = self.strategy.calculate_delay(LLMRateLimitError("Rate limited"), 0)
            # Expected: 1.0 * 2.0 = 2.0 (base * rate_limit_multiplier)
            self.assertEqual(delay, 2.0)
            
            delay = self.strategy.calculate_delay(LLMRateLimitError("Rate limited"), 1)
            # Expected: 2.0 * 2.0 = 4.0 (base * 2^1 * rate_limit_multiplier)
            self.assertEqual(delay, 4.0)
    
    def test_calculate_delay_max_cap(self):
        """Test that delay is capped at max_delay."""
        # With high retry count, delay would exceed max without cap
        with patch('random.uniform', return_value=0):  # Remove jitter for testing
            delay = self.strategy.calculate_delay(LLMNetworkError("Error"), 10)  # Very high retry count
            self.assertEqual(delay, 32.0)  # Should be capped at max_delay
            
            # Even with rate limit multiplier, should still be capped
            delay = self.strategy.calculate_delay(LLMRateLimitError("Rate limited"), 10)
            self.assertEqual(delay, 32.0)  # Still capped at max_delay
    
    @patch('time.sleep')
    def test_wait_for_retry(self, mock_sleep):
        """Test that wait_for_retry sleeps for the correct amount of time."""
        # Set up to calculate a fixed delay
        with patch.object(self.strategy, 'calculate_delay', return_value=2.5):
            # Wait for retry
            self.strategy.wait_for_retry(LLMNetworkError("Error"), 1)
            
            # Should have slept for calculated delay
            mock_sleep.assert_called_once_with(2.5)
    
    @patch('time.sleep')
    def test_retry_operation_success_after_retries(self, mock_sleep):
        """Test retrying an operation until it succeeds."""
        # Create a function that fails twice, then succeeds
        func = Mock(side_effect=[
            LLMNetworkError("Connection error"),  # First call fails
            LLMNetworkError("Connection error"),  # Second call fails
            "Success"  # Third call succeeds
        ])
        
        # Mock delay calculation to speed up test
        with patch.object(self.strategy, 'calculate_delay', return_value=0.1):
            # Retry the operation
            result = self.strategy.retry_operation(func, "test_arg1", kwarg1="test")
            
            # Should have succeeded on third attempt
            self.assertEqual(result, "Success")
            self.assertEqual(func.call_count, 3)
            
            # Verify function was called with correct args
            func.assert_called_with("test_arg1", kwarg1="test")
    
    @patch('time.sleep')
    def test_retry_operation_never_succeeds(self, mock_sleep):
        """Test retrying an operation that never succeeds."""
        # Create a function that always fails with a retryable error
        error = LLMTimeoutError("Always times out")
        func = Mock(side_effect=error)
        
        # Mock delay calculation to speed up test
        with patch.object(self.strategy, 'calculate_delay', return_value=0.1):
            # Retry the operation - should eventually give up and re-raise the last error
            with self.assertRaises(LLMTimeoutError):
                self.strategy.retry_operation(func)
            
            # Should have tried max_retries + 1 times (initial + retries)
            self.assertEqual(func.call_count, self.strategy.max_retries + 1)
    
    @patch('time.sleep')
    def test_retry_operation_non_retryable_error(self, mock_sleep):
        """Test how the strategy handles non-retryable errors."""
        # Create a function that fails with a non-retryable error
        error = LLMAPIError("Invalid request")
        func = Mock(side_effect=error)
        
        # Retry the operation - should immediately re-raise without retrying
        with self.assertRaises(LLMAPIError):
            self.strategy.retry_operation(func)
        
        # Should only have tried once (no retries for non-retryable error)
        self.assertEqual(func.call_count, 1)
        self.assertEqual(mock_sleep.call_count, 0)  # Should not have slept
    
    def test_custom_retry_condition(self):
        """Test using a custom retry condition function."""
        # Create a custom retry condition that only retries LLMTimeoutError
        def custom_condition(error, retry_count):
            return isinstance(error, LLMTimeoutError) and retry_count < 3
        
        # Create strategy with custom condition
        strategy = ExponentialBackoffStrategy(
            base_delay=1.0,
            max_delay=10.0,
            max_retries=5,
            retry_condition=custom_condition
        )
        
        # Should retry timeout errors
        self.assertTrue(strategy.should_retry(LLMTimeoutError("Timeout"), 1))
        
        # Should NOT retry network errors, even though default would
        self.assertFalse(strategy.should_retry(LLMNetworkError("Network error"), 1))
        
        # Should NOT retry after 3 attempts, even for timeout errors
        self.assertFalse(strategy.should_retry(LLMTimeoutError("Timeout"), 3))
    
    def test_custom_delay_function(self):
        """Test using a custom delay function."""
        # Create a custom delay function that always returns 5.0
        def custom_delay(error, retry_count):
            return 5.0
        
        # Create strategy with custom delay
        strategy = ExponentialBackoffStrategy(
            base_delay=1.0,
            max_delay=10.0,
            max_retries=5,
            delay_function=custom_delay
        )
        
        # Check delay calculation
        delay = strategy.calculate_delay(LLMNetworkError("Error"), 0)
        self.assertEqual(delay, 5.0)  # Should use custom function
        
        delay = strategy.calculate_delay(LLMRateLimitError("Rate limited"), 10)
        self.assertEqual(delay, 5.0)  # Should still use custom function, ignoring type and count
    
    def test_get_stats(self):
        """Test retrieving retry statistics."""
        # Setup: perform some retries to record stats
        function = Mock(side_effect=[
            LLMNetworkError("Error 1"),
            LLMTimeoutError("Error 2"),
            "Success"
        ])
        
        # Mock delay calculation to speed up test
        with patch.object(self.strategy, 'calculate_delay', return_value=0.1):
            with patch('time.sleep'):
                self.strategy.retry_operation(function)
        
        # Get stats
        stats = self.strategy.get_stats()
        
        # Check stats fields
        self.assertEqual(stats["total_retries"], 2)
        self.assertEqual(stats["successful_operations"], 1)
        self.assertEqual(stats["failed_operations"], 0)  # Zero because eventually succeeded
        self.assertGreaterEqual(len(stats["retry_errors"]), 2)  # Should have record of errors
        self.assertGreater(stats["total_delay"], 0)  # Should have recorded delay time


if __name__ == '__main__':
    unittest.main() 