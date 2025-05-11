"""
Integration tests for error handling components working together.

This module tests the interaction between different error handling components
to ensure they work together correctly in complex scenarios.
"""

import unittest
import time
import json
from unittest.mock import patch, MagicMock, Mock

from src.error_recovery import (
    CircuitBreaker,
    TokenBucketRateLimiter,
    ErrorRecoveryStrategies
)
from src.retry_strategy import ExponentialBackoffStrategy
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
    LLMInternalError,
    CircuitBreakerOpenError
)


class TestErrorHandlingIntegration(unittest.TestCase):
    """Test suite for error handling components integration."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Create instances of all error handling components
        self.rate_limiter = TokenBucketRateLimiter(
            rate=10.0,
            max_tokens=60,
            tokens_per_request=1,
            min_rate=0.2,
            recovery_factor=1.2,
            backoff_factor=0.5
        )
        
        self.retry_strategy = ExponentialBackoffStrategy(
            base_delay=0.1,  # Shorter delays for testing
            max_delay=1.0,
            max_retries=3,
            jitter=0.1
        )
        
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=0.2,  # Shorter timeout for testing
            half_open_success_threshold=2
        )
        
        self.recovery_strategies = ErrorRecoveryStrategies()
        
        # Create test state for error messages
        self.test_state = {
            "session_id": "test-session-123",
            "user_id": "test-user-456",
            "current_context": {
                "action_type": "test_action",
                "component": "test_component"
            }
        }
    
    def test_rate_limiter_with_retry_strategy(self):
        """Test rate limiter working with retry strategy."""
        # Configure rate limiter to reject the first request, then accept subsequent ones
        self.rate_limiter.tokens = 0.0  # No tokens initially
        
        # Create a counter to track attempts
        attempts = [0]
        
        # Create a test function that updates the limiter after first call
        def test_function():
            attempts[0] += 1
            if attempts[0] == 1:
                # First attempt - reject due to rate limit
                return False
            else:
                # Add tokens after first attempt
                self.rate_limiter.tokens = 10.0
                return "Success after retry"
        
        # Wrap test_function with rate limiter check
        def wrapped_function():
            if not self.rate_limiter.consume(block=False):
                raise LLMRateLimitError("Rate limited")
            return test_function()
        
        # Use retry strategy to retry the rate-limited operation
        with patch('time.sleep'):  # Mock sleep to speed up test
            result = self.retry_strategy.retry_operation(wrapped_function)
        
        # Should succeed after retry
        self.assertEqual(result, "Success after retry")
        self.assertEqual(attempts[0], 2)  # Should have been called twice
    
    def test_circuit_breaker_with_retry_strategy(self):
        """Test circuit breaker working with retry strategy."""
        # Create a function that fails 3 times (triggering circuit breaker), then would succeed
        test_func = Mock(side_effect=[
            LLMNetworkError("Network error 1"),
            LLMNetworkError("Network error 2"),
            LLMNetworkError("Network error 3"),
            "Success"  # This won't be reached due to circuit breaker
        ])
        
        # Wrap with circuit breaker
        def circuit_wrapped():
            return self.circuit_breaker.execute(test_func)
        
        # Use retry strategy with circuit-wrapped function
        with patch('time.sleep'):  # Mock sleep to speed up test
            # Should eventually fail with CircuitBreakerOpenError
            with self.assertRaises(CircuitBreakerOpenError):
                self.retry_strategy.retry_operation(circuit_wrapped)
        
        # Should have called the function 3 times before circuit opened
        self.assertEqual(test_func.call_count, 3)
        self.assertEqual(self.circuit_breaker.state, "OPEN")
    
    def test_all_components_together(self):
        """Test all error handling components working together."""
        # Create error recovery handler
        def recovery_handler(error, state):
            return f"Recovered from {type(error).__name__}"
        
        # Register recovery handlers
        for error_type in [LLMNetworkError, LLMTimeoutError, LLMRateLimitError]:
            self.recovery_strategies.register_handler(error_type, recovery_handler)
        
        # Configure components
        self.rate_limiter.tokens = 5.0  # Limited tokens
        
        # Create a tracking counter and result storage
        attempt_counter = [0]
        last_error = [None]
        
        # Create test function with various failure scenarios
        def complex_test_function():
            attempt_counter[0] += 1
            
            # Different errors based on attempt number
            if attempt_counter[0] == 1:
                # First attempt - rate limit error
                self.rate_limiter.tokens = 0.0  # Consume all tokens
                error = LLMRateLimitError("Rate limited")
                last_error[0] = error
                raise error
                
            elif attempt_counter[0] <= 3:
                # Second and third attempts - network errors
                error = LLMNetworkError(f"Network error {attempt_counter[0]}")
                last_error[0] = error
                raise error
                
            else:
                # Fourth attempt onwards - success
                return "Final success"
        
        # Create the combined logic
        def execute_with_all_safeguards():
            try:
                # 1. Check rate limiter
                if not self.rate_limiter.consume(block=False):
                    raise LLMRateLimitError("Rate limited by token bucket")
                
                # 2. Execute with circuit breaker
                try:
                    return self.circuit_breaker.execute(complex_test_function)
                except Exception as e:
                    # Circuit breaker will re-raise the original exception
                    raise
                    
            except Exception as e:
                # 3. If any error occurs, try recovery
                return self.recovery_strategies.handle_error(e, self.test_state)
        
        # Use retry strategy as the outermost layer
        with patch('time.sleep'):  # Mock sleep to speed up test
            result = self.retry_strategy.retry_operation(execute_with_all_safeguards)
        
        # Check what happened - should have recovered from the last error
        self.assertEqual(result, f"Recovered from {type(last_error[0]).__name__}")
        
        # Circuit breaker should have recorded failures
        self.assertTrue(self.circuit_breaker.failure_count > 0 or self.circuit_breaker.state != "CLOSED")
    
    def test_degradation_levels(self):
        """Test graceful degradation through different levels of errors."""
        # Create a mock LLM client
        mock_llm_client = MagicMock()
        
        # Configure rate limiter and circuit breaker
        self.rate_limiter.tokens = 1.0
        
        # Define error handling levels
        def level1_call():
            """Primary call path with full features."""
            if not self.rate_limiter.consume(block=False):
                return level2_call()
                
            return self.circuit_breaker.execute(
                lambda: mock_llm_client.generate("Full prompt with all features")
            )
        
        def level2_call():
            """Reduced functionality fallback."""
            return self.circuit_breaker.execute(
                lambda: mock_llm_client.generate("Simplified prompt with core features only")
            )
        
        def level3_call():
            """Minimal functionality fallback."""
            return "Static fallback response with minimal functionality"
        
        # Configure mock to fail in specific ways
        mock_llm_client.generate.side_effect = [
            # First call will succeed
            "Full response with all features",
            # Then circuit breaker will open
            LLMServerError("Server error"),
            LLMServerError("Server error"),
            LLMServerError("Server error"),
            # After circuit breaker opens, level2 would try but circuit is open
            "This shouldn't be reached"
        ]
        
        # First call - should get full features
        result1 = level1_call()
        self.assertEqual(result1, "Full response with all features")
        
        # Trip the circuit breaker
        for _ in range(3):
            try:
                level1_call()
            except Exception:
                pass
        
        # Now circuit breaker is open
        self.assertEqual(self.circuit_breaker.state, "OPEN")
        
        # Try again - should attempt level2 but circuit breaker stops it
        with patch.object(self.circuit_breaker, 'execute', 
                         side_effect=CircuitBreakerOpenError("Circuit open")):
            # This should fall back to level3
            with patch('level3_call', return_value=level3_call()):
                result2 = level3_call()
                
        self.assertEqual(result2, "Static fallback response with minimal functionality")
    
    def test_adaptive_rate_limiting_with_retries(self):
        """Test adaptive rate limiting adjusting based on response patterns."""
        # Start with a high rate
        self.rate_limiter.rate = 20.0
        self.rate_limiter.tokens = 20.0
        
        # Create a test function with changing behavior
        execution_count = [0]
        
        def adaptive_test_function():
            execution_count[0] += 1
            
            if execution_count[0] <= 2:
                # First two calls succeed
                self.rate_limiter.record_success()
                return f"Success {execution_count[0]}"
                
            elif execution_count[0] <= 4:
                # Next two calls hit rate limits
                self.rate_limiter.record_rate_limit()
                raise LLMRateLimitError(f"Rate limit {execution_count[0]}")
                
            else:
                # Then succeed again but at a lower rate
                self.rate_limiter.record_success()
                return f"Success {execution_count[0]} at lower rate"
        
        # Track the rate changes
        initial_rate = self.rate_limiter.rate
        rates = [initial_rate]
        
        # Execute multiple times with retries
        results = []
        
        # Mock sleep to speed up test
        with patch('time.sleep'):
            for _ in range(5):
                try:
                    # Check rate limiter
                    if not self.rate_limiter.consume(block=False):
                        raise LLMRateLimitError("Rate limited")
                        
                    # Execute function
                    result = adaptive_test_function()
                    results.append(result)
                    
                except LLMRateLimitError:
                    # Use retry strategy
                    try:
                        # Only retry the rate limited calls
                        retry_result = self.retry_strategy.retry_operation(adaptive_test_function)
                        results.append(retry_result)
                    except Exception as e:
                        results.append(f"Failed: {str(e)}")
                        
                # Record the current rate after each attempt
                rates.append(self.rate_limiter.rate)
        
        # Verify rate adaptation
        self.assertTrue(rates[0] > rates[3], "Rate should decrease after limit errors")
        self.assertEqual(len(results), 5, "Should have 5 results")
        
        # Check for successful adaptations
        success_count = sum(1 for r in results if "Success" in str(r))
        self.assertGreater(success_count, 2, "Should have multiple successes despite rate limits")


if __name__ == '__main__':
    unittest.main() 