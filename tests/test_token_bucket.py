"""
Unit tests for the TokenBucketRateLimiter class in src/error_recovery.py.

This module tests the token bucket algorithm for rate limiting,
including adaptive rate adjustment based on rate limit responses.
"""

import unittest
import time
from unittest.mock import patch, MagicMock, Mock

from src.error_recovery import TokenBucketRateLimiter


class TestTokenBucketRateLimiter(unittest.TestCase):
    """Test suite for the TokenBucketRateLimiter class."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Create a rate limiter with known parameters for testing
        self.rate_limiter = TokenBucketRateLimiter(
            rate=10.0,  # 10 tokens per second
            max_tokens=60,  # Max 60 tokens in bucket
            tokens_per_request=1,  # 1 token per request
            min_rate=0.2,  # Minimum rate during severe limiting
            recovery_factor=1.2,  # Rate increase factor on success
            backoff_factor=0.5  # Rate decrease factor on limit
        )
    
    def test_initialization(self):
        """Test that the rate limiter initializes with correct values."""
        self.assertEqual(self.rate_limiter.rate, 10.0)
        self.assertEqual(self.rate_limiter.max_tokens, 60)
        self.assertEqual(self.rate_limiter.tokens, 60)  # Should start full
        self.assertEqual(self.rate_limiter.tokens_per_request, 1)
        self.assertEqual(self.rate_limiter.min_rate, 0.2)
        self.assertEqual(self.rate_limiter.recovery_factor, 1.2)
        self.assertEqual(self.rate_limiter.backoff_factor, 0.5)
        self.assertEqual(self.rate_limiter.rate_limit_count, 0)
    
    def test_add_tokens(self):
        """Test that tokens are added correctly based on elapsed time."""
        # Set initial state
        self.rate_limiter.tokens = 50.0
        current_time = time.time()
        self.rate_limiter.last_updated = current_time - 1.0  # 1 second ago
        
        # Add tokens
        with patch('time.time', return_value=current_time):
            self.rate_limiter.add_tokens()
        
        # Should have added 10 tokens (rate=10, elapsed=1)
        self.assertEqual(self.rate_limiter.tokens, 60.0)  # Capped at max_tokens
    
    def test_get_wait_time(self):
        """Test wait time calculation."""
        # Set initial state with not enough tokens
        self.rate_limiter.tokens = 0.5
        self.rate_limiter.rate = 10.0
        
        # Get wait time
        wait_time = self.rate_limiter.get_wait_time()
        
        # Should need 0.5 tokens, at 10 tokens/sec = 0.05 seconds
        self.assertAlmostEqual(wait_time, 0.05, places=2)
        
        # Test with full bucket
        self.rate_limiter.tokens = 60.0
        wait_time = self.rate_limiter.get_wait_time()
        self.assertEqual(wait_time, 0.0)  # No wait needed
    
    def test_consume_success(self):
        """Test token consumption when enough tokens are available."""
        # Set initial state with enough tokens
        self.rate_limiter.tokens = 5.0
        
        # Consume tokens
        result = self.rate_limiter.consume(block=False)
        
        # Should succeed and decrease tokens
        self.assertTrue(result)
        self.assertEqual(self.rate_limiter.tokens, 4.0)
    
    def test_consume_not_enough_tokens_non_blocking(self):
        """Test non-blocking consumption when not enough tokens."""
        # Set initial state with not enough tokens
        self.rate_limiter.tokens = 0.5
        
        # Try to consume with non-blocking mode
        result = self.rate_limiter.consume(block=False)
        
        # Should fail
        self.assertFalse(result)
        self.assertEqual(self.rate_limiter.tokens, 0.5)  # Tokens unchanged
    
    @patch('time.sleep')
    def test_consume_blocking_wait(self, mock_sleep):
        """Test blocking consumption that waits for tokens."""
        # Set initial state with not enough tokens
        self.rate_limiter.tokens = 0.5
        
        # Mock time to advance during the sleep and add_tokens calls
        time_sequence = [100.0, 100.05, 100.1]  # Time advances by 0.05s
        
        with patch('time.time', side_effect=time_sequence):
            # Consume with blocking mode
            result = self.rate_limiter.consume(block=True)
            
            # Should succeed after waiting
            self.assertTrue(result)
            mock_sleep.assert_called()  # Sleep should have been called
    
    def test_consume_with_timeout(self):
        """Test consumption with timeout."""
        # Set initial state with not enough tokens
        self.rate_limiter.tokens = 0.0
        self.rate_limiter.rate = 0.1  # Very slow rate to ensure timeout
        
        # Consume with timeout
        start_time = time.time()
        result = self.rate_limiter.consume(block=True, timeout=0.01)
        elapsed = time.time() - start_time
        
        # Should fail after timing out
        self.assertFalse(result)
        self.assertLess(elapsed, 0.5)  # Should not wait too long
    
    def test_record_rate_limit(self):
        """Test rate adjustment when rate limit occurs."""
        # Set initial rate
        initial_rate = 10.0
        self.rate_limiter.rate = initial_rate
        self.rate_limiter.successful_request_count = 5
        
        # Record a rate limit
        self.rate_limiter.record_rate_limit()
        
        # Check rate was reduced
        self.assertEqual(self.rate_limiter.rate, initial_rate * 0.5)
        self.assertEqual(self.rate_limiter.rate_limit_count, 1)
        self.assertEqual(self.rate_limiter.successful_request_count, 0)
        
        # Test minimum rate enforcement
        self.rate_limiter.rate = 0.3
        self.rate_limiter.record_rate_limit()
        self.assertEqual(self.rate_limiter.rate, 0.2)  # Minimum rate
    
    def test_record_success(self):
        """Test rate adjustment after successful requests."""
        # Set initial state
        self.rate_limiter.rate = 5.0
        self.rate_limiter.successful_request_count = 0
        
        # Record successes, but not enough to trigger recovery
        for _ in range(9):
            self.rate_limiter.record_success()
        
        # Rate should not have changed yet
        self.assertEqual(self.rate_limiter.rate, 5.0)
        self.assertEqual(self.rate_limiter.successful_request_count, 9)
        
        # Record enough successes to trigger recovery
        with patch('time.time', return_value=time.time() + 31):  # Ensure enough time has passed
            self.rate_limiter.record_success()
            
            # Rate should increase
            self.assertEqual(self.rate_limiter.rate, 5.0 * 1.2)
            self.assertEqual(self.rate_limiter.successful_request_count, 0)  # Reset
    
    def test_get_status(self):
        """Test retrieving limiter status."""
        # Set some state
        self.rate_limiter.rate = 5.0
        self.rate_limiter.tokens = 30.0
        self.rate_limiter.rate_limit_count = 3
        self.rate_limiter.successful_request_count = 5
        
        # Get status
        status = self.rate_limiter.get_status()
        
        # Check status fields
        self.assertEqual(status["current_rate"], 5.0)
        self.assertEqual(status["available_tokens"], 30.0)
        self.assertEqual(status["max_tokens"], 60)
        self.assertEqual(status["rate_limit_count"], 3)
        self.assertEqual(status["successful_request_count"], 5)
    
    def test_adaptive_rate_adjustment(self):
        """Test the complete cycle of rate adjustments."""
        # Start with default rate
        initial_rate = 10.0
        self.rate_limiter.rate = initial_rate
        
        # 1. Hit rate limit, rate should decrease
        self.rate_limiter.record_rate_limit()
        reduced_rate = initial_rate * 0.5
        self.assertEqual(self.rate_limiter.rate, reduced_rate)
        
        # 2. Record successful requests
        for _ in range(10):
            self.rate_limiter.record_success()
        
        # 3. After time passes, rate should increase
        with patch('time.time', return_value=time.time() + 31):
            self.rate_limiter.record_success()  # Trigger rate increase
            increased_rate = reduced_rate * 1.2
            self.assertEqual(self.rate_limiter.rate, increased_rate)
    
    def test_multithreaded_safety(self):
        """Test that operations are thread-safe."""
        # This is a simple test to verify that lock acquisition doesn't deadlock
        # More comprehensive multi-threaded testing would require a more complex setup
        
        # Set initial state
        self.rate_limiter.tokens = 10.0
        
        # Acquire the lock explicitly first
        with self.rate_limiter._lock:
            # Inside the lock, perform an operation that also acquires the lock
            result = self.rate_limiter.consume(block=False)
            
            # Should succeed without deadlock
            self.assertTrue(result)
            self.assertEqual(self.rate_limiter.tokens, 9.0)


if __name__ == '__main__':
    unittest.main() 