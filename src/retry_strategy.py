"""
Advanced retry strategies for LLM API calls using the tenacity library.

This module provides configurable retry decorators that implement exponential backoff,
jitter, and circuit breaking for different types of API errors. It integrates with
the custom exception hierarchy to provide intelligent retry behavior.
"""

import logging
import random
import time
import enum
import threading
from functools import wraps
from typing import Any, Callable, Dict, Optional, Type, TypeVar, Union, cast, List, Tuple

import tenacity
from tenacity import (
    retry,
    retry_if_exception,
    retry_if_exception_type,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential,
    wait_fixed,
    wait_random,
    wait_random_exponential,
    before_sleep_log,
    RetryCallState,
    AttemptManager,
)

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
)

# Configure logging
logger = logging.getLogger(__name__)

# Type variable for function return type
T = TypeVar('T')

# Retry metrics for monitoring
_retry_metrics = {
    "attempts": 0,              # Total retry attempts
    "successes_after_retry": 0, # Successful operations after at least one retry
    "failures": 0,              # Total failed operations (after max retries)
    "errors_by_type": {},       # Count of errors by exception type
    "total_retry_delay": 0,     # Total seconds spent in retry wait
    "circuit_breaks": 0,        # Number of times circuit breaker opened
    "last_metrics_reset": time.time(),  # When metrics were last reset
}

# Simple mutex for thread-safety
_retry_lock = threading.RLock()

class CircuitState(enum.Enum):
    """Possible states for the circuit breaker."""
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing fast
    HALF_OPEN = "half_open" # Testing recovery

class CircuitBreaker:
    """
    Advanced circuit breaker implementation with state tracking.
    
    This class implements the circuit breaker pattern for handling API failures:
    - CLOSED: Normal operation, all requests proceed
    - OPEN: Circuit is broken, requests fail fast without API calls
    - HALF-OPEN: Testing recovery, limited requests to check if API is healthy
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 3,
        monitored_exceptions: Optional[List[Type[Exception]]] = None,
    ):
        """
        Initialize the circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening the circuit
            recovery_timeout: Seconds before attempting to close the circuit
            half_open_max_calls: Maximum number of test calls allowed in HALF-OPEN state
            monitored_exceptions: List of exception types that trigger the circuit breaker
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.monitored_exceptions = monitored_exceptions or [
            LLMServerError,
            LLMServiceUnavailableError,
            LLMInternalError
        ]
        
        # State tracking
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._last_failure_time = 0
        self._last_success_time = 0
        self._half_open_calls = 0
        self._lock = threading.RLock()
    
    @property
    def state(self) -> CircuitState:
        """Get the current circuit state."""
        with self._lock:
            # Check if we should transition from OPEN to HALF-OPEN due to timeout
            if self._state == CircuitState.OPEN:
                if time.time() - self._last_failure_time > self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    logger.info("Circuit breaker transitioning from OPEN to HALF-OPEN")
            
            return self._state
    
    def record_failure(self, exception: Exception) -> bool:
        """
        Record a failure and potentially open the circuit.
        
        Args:
            exception: The exception that occurred
            
        Returns:
            True if the circuit is now open, False otherwise
        """
        # Check if this exception type should trigger the circuit breaker
        should_count = any(isinstance(exception, exc_type) for exc_type in self.monitored_exceptions)
        if not should_count:
            return False
        
        with self._lock:
            if self._state == CircuitState.CLOSED:
                self._failures += 1
                self._last_failure_time = time.time()
                
                if self._failures >= self.failure_threshold:
                    self._state = CircuitState.OPEN
                    logger.warning(
                        "Circuit breaker opened after %d consecutive failures. "
                        "Last error: %s: %s",
                        self._failures,
                        type(exception).__name__,
                        str(exception)
                    )
                    # Update circuit break metrics
                    with _retry_lock:
                        _retry_metrics["circuit_breaks"] += 1
                    
                    return True
                    
            elif self._state == CircuitState.HALF_OPEN:
                self._failures += 1
                self._last_failure_time = time.time()
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit breaker returning to OPEN state after failure in HALF-OPEN. "
                    "Error: %s: %s",
                    type(exception).__name__,
                    str(exception)
                )
                return True
        
        return False
    
    def record_success(self) -> None:
        """Record a successful operation and potentially close the circuit."""
        with self._lock:
            self._last_success_time = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1
                
                if self._half_open_calls >= self.half_open_max_calls:
                    self._state = CircuitState.CLOSED
                    self._failures = 0
                    logger.info(
                        "Circuit breaker closed after %d successful operations in HALF-OPEN state",
                        self._half_open_calls
                    )
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failures = 0
    
    def allow_request(self) -> bool:
        """
        Check if a request should be allowed to proceed.
        
        Returns:
            True if the request should proceed, False if it should fail fast
        """
        current_state = self.state  # This will handle OPEN to HALF-OPEN transitions
        
        if current_state == CircuitState.CLOSED:
            return True
            
        if current_state == CircuitState.HALF_OPEN:
            with self._lock:
                if self._half_open_calls < self.half_open_max_calls:
                    # Increment the count so we respect the limit of calls
                    # This will be reset back to zero if the call succeeds in record_success()
                    self._half_open_calls += 1
                    return True
            
        # Either OPEN or HALF-OPEN with max calls reached
        return False
    
    def reset(self) -> None:
        """Reset the circuit breaker to CLOSED state."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failures = 0
            self._half_open_calls = 0
            logger.info("Circuit breaker manually reset to CLOSED state")

# Global circuit breaker instance
_circuit_breaker = CircuitBreaker()

def configure_circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    half_open_max_calls: int = 3,
    monitored_exceptions: Optional[List[Type[Exception]]] = None,
) -> None:
    """
    Configure the global circuit breaker settings.
    
    Args:
        failure_threshold: Number of failures before opening the circuit
        recovery_timeout: Seconds before attempting to close the circuit
        half_open_max_calls: Maximum number of test calls allowed in HALF-OPEN state
        monitored_exceptions: List of exception types that trigger the circuit breaker
    """
    global _circuit_breaker
    _circuit_breaker = CircuitBreaker(
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        half_open_max_calls=half_open_max_calls,
        monitored_exceptions=monitored_exceptions
    )

def _is_retryable_exception(exception: Exception) -> bool:
    """
    Check if an exception should be retried based on its type and properties.
    
    Args:
        exception: The exception to check
        
    Returns:
        True if the exception should be retried, False otherwise
    """
    if isinstance(exception, LLMAPIError):
        return exception.is_retryable
    return False

def _extract_retry_after(exception: Exception) -> Optional[float]:
    """
    Extract retry-after value from an exception if available.
    
    Args:
        exception: The exception from which to extract retry-after
        
    Returns:
        The retry-after value in seconds, or None if not found
    """
    if not isinstance(exception, LLMAPIError):
        return None
    
    # Try to extract retry-after from response data
    if hasattr(exception, 'response_data') and exception.response_data:
        headers = exception.response_data.get('headers', {})
        
        # Check for retry-after header
        retry_after = headers.get('retry-after') or headers.get('Retry-After')
        
        if retry_after:
            try:
                # Check if it's a numeric value (seconds)
                return float(retry_after)
            except ValueError:
                # It might be an HTTP date format
                # For simplicity, we're returning a default value
                # A real implementation would parse the HTTP date
                return 30.0
    
    return None

def _reset_circuit_on_success() -> None:
    """Record a successful operation for the circuit breaker."""
    global _circuit_breaker
    _circuit_breaker.record_success()

def _check_circuit_breaker(exception: Exception) -> bool:
    """
    Check if the circuit breaker should allow a retry.
    
    Args:
        exception: The current exception
        
    Returns:
        True if retry should be allowed, False if circuit is open
    """
    global _circuit_breaker
    
    # Record failure and check if circuit is open
    circuit_open = _circuit_breaker.record_failure(exception)
    
    # Return whether requests should be allowed
    return _circuit_breaker.allow_request()

def _adaptive_wait_strategy(retry_state: RetryCallState) -> float:
    """
    Advanced adaptive wait strategy based on error type and frequency.
    
    Args:
        retry_state: The current retry state
        
    Returns:
        The number of seconds to wait before retrying
    """
    # Get the exception
    exception = retry_state.outcome.exception()
    if not exception:
        # Default exponential backoff if no exception
        base_wait = 2 ** retry_state.attempt_number
        return min(60, base_wait)
    
    # Adjust wait time based on exception type
    if isinstance(exception, LLMRateLimitError):
        # Use retry-after header or escalating backoff for rate limits
        return _rate_limit_wait_strategy(retry_state)
    
    if isinstance(exception, (LLMTimeoutError, LLMConnectionError)):
        # For timeout/connection errors, use shorter initial waits but steeper backoff
        multiplier = 1.5
        base_wait = multiplier * (2 ** (retry_state.attempt_number - 1))
        max_wait = 45.0  # Cap at 45 seconds
        jitter = random.uniform(0, 0.1 * base_wait)
        return min(max_wait, base_wait + jitter)
    
    if isinstance(exception, (LLMServerError, LLMServiceUnavailableError)):
        # For server errors, use longer waits to let the service recover
        multiplier = 3.0
        base_wait = multiplier * (2 ** (retry_state.attempt_number - 1))
        max_wait = 120.0  # Cap at 2 minutes
        jitter = random.uniform(0, 0.2 * base_wait)  # 20% jitter
        return min(max_wait, base_wait + jitter)
    
    # Default exponential backoff with jitter for other errors
    base_wait = 2 ** retry_state.attempt_number
    max_wait = 60.0
    jitter = random.uniform(0, 0.1 * base_wait)
    return min(max_wait, base_wait + jitter)

def _rate_limit_wait_strategy(retry_state: RetryCallState) -> float:
    """
    Custom wait strategy for rate limit errors that respects retry-after headers.
    
    Args:
        retry_state: The current retry state
        
    Returns:
        The number of seconds to wait before retrying
    """
    # Get the last exception
    exception = retry_state.outcome.exception()
    
    # Check for retry-after header
    retry_after = _extract_retry_after(exception) if exception else None
    
    if retry_after is not None and retry_after > 0:
        # Use the retry-after value with a small jitter
        jitter = random.uniform(0, 0.1 * retry_after)
        return retry_after + jitter
    
    # Fall back to exponential backoff with jitter
    exp_base = 2
    exp_max = 60  # Maximum wait time in seconds
    
    wait_time = min(
        exp_max,
        exp_base ** retry_state.attempt_number
    )
    
    # Add jitter (10% of wait time)
    jitter = random.uniform(0, 0.1 * wait_time)
    return wait_time + jitter

def _update_retry_metrics(retry_state: RetryCallState) -> None:
    """
    Update retry metrics for monitoring.
    
    Args:
        retry_state: The current retry state
    """
    with _retry_lock:
        # Increment attempt count
        _retry_metrics["attempts"] += 1
        
        # Track error by type
        exception = retry_state.outcome.exception()
        if exception:
            error_type = type(exception).__name__
            _retry_metrics["errors_by_type"][error_type] = (
                _retry_metrics["errors_by_type"].get(error_type, 0) + 1
            )

def _before_retry_log(retry_state: RetryCallState) -> None:
    """
    Log information before a retry attempt and update metrics.
    
    Args:
        retry_state: The current retry state
    """
    exception = retry_state.outcome.exception()
    if exception:
        # Get max attempts if available
        max_attempts = (
            retry_state.retry_object.stop.max_attempt_number 
            if hasattr(retry_state.retry_object.stop, "max_attempt_number") 
            else "∞"
        )
        
        # Get the next wait time
        wait_time = None
        if hasattr(retry_state.retry_object, "wait"):
            try:
                wait_time = retry_state.retry_object.wait(retry_state)
            except:
                wait_time = "unknown"
        
        # Log retry information
        logger.warning(
            "Retrying API call due to %s: %s (attempt %d/%s, next wait: %s sec)",
            type(exception).__name__,
            str(exception),
            retry_state.attempt_number,
            max_attempts,
            wait_time if wait_time is not None else "?"
        )
        
        # Update metrics
        _update_retry_metrics(retry_state)

def get_retry_metrics() -> Dict[str, Any]:
    """
    Get a copy of the current retry metrics.
    
    Returns:
        A dictionary with retry metrics
    """
    with _retry_lock:
        # Return a copy to avoid modification
        metrics = _retry_metrics.copy()
        metrics["uptime_seconds"] = time.time() - metrics["last_metrics_reset"]
        return metrics

def reset_retry_metrics() -> None:
    """Reset all retry metrics to zero."""
    with _retry_lock:
        global _retry_metrics
        _retry_metrics = {
            "attempts": 0,
            "successes_after_retry": 0,
            "failures": 0,
            "errors_by_type": {},
            "total_retry_delay": 0,
            "circuit_breaks": 0,
            "last_metrics_reset": time.time(),
        }

def retry_on_network_errors(
    max_attempts: int = 3,
    max_delay: Optional[float] = None,
    min_wait: float = 1.0,
    max_wait: float = 10.0,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for retrying operations that fail due to network errors.
    
    Args:
        max_attempts: Maximum number of retry attempts
        max_delay: Maximum total delay before giving up
        min_wait: Minimum wait time between retries
        max_wait: Maximum wait time between retries
        
    Returns:
        A decorator function
    """
    # Define stop strategy
    stop_strategy = stop_after_attempt(max_attempts)
    if max_delay is not None:
        stop_strategy = tenacity.stop_any(
            stop_strategy,
            stop_after_delay(max_delay)
        )
    
    # Define retry condition
    def _is_network_error(exception: Exception) -> bool:
        return isinstance(exception, (LLMNetworkError, LLMTimeoutError, LLMConnectionError))
    
    retry_condition = retry_if_exception(_is_network_error)
    
    # Define wait strategy
    wait_strategy = wait_random_exponential(multiplier=1, min=min_wait, max=max_wait)
    
    # Create decorator
    return retry(
        retry=retry_condition,
        stop=stop_strategy,
        wait=wait_strategy,
        before_sleep=_before_retry_log,
        reraise=True,
    )

def retry_on_rate_limit(
    max_attempts: int = 5,
    max_delay: Optional[float] = 300.0,  # 5 minutes max delay
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for retrying operations that fail due to rate limiting.
    
    Args:
        max_attempts: Maximum number of retry attempts
        max_delay: Maximum total delay before giving up
        
    Returns:
        A decorator function
    """
    # Define stop strategy
    stop_strategy = stop_after_attempt(max_attempts)
    if max_delay is not None:
        stop_strategy = tenacity.stop_any(
            stop_strategy,
            stop_after_delay(max_delay)
        )
    
    # Define retry condition
    retry_condition = retry_if_exception_type(LLMRateLimitError)
    
    # Create decorator
    return retry(
        retry=retry_condition,
        stop=stop_strategy,
        wait=_rate_limit_wait_strategy,
        before_sleep=_before_retry_log,
        reraise=True,
    )

def retry_on_server_errors(
    max_attempts: int = 3,
    max_delay: Optional[float] = 60.0,
    min_wait: float = 1.0,
    max_wait: float = 15.0,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for retrying operations that fail due to server errors.
    
    Args:
        max_attempts: Maximum number of retry attempts
        max_delay: Maximum total delay before giving up
        min_wait: Minimum wait time between retries
        max_wait: Maximum wait time between retries
        
    Returns:
        A decorator function
    """
    # Define stop strategy
    stop_strategy = stop_after_attempt(max_attempts)
    if max_delay is not None:
        stop_strategy = tenacity.stop_any(
            stop_strategy,
            stop_after_delay(max_delay)
        )
    
    # Define retry condition
    def _is_server_error(exception: Exception) -> bool:
        return isinstance(exception, (LLMServerError, LLMServiceUnavailableError, LLMInternalError))
    
    retry_condition = retry_if_exception(_is_server_error)
    
    # Define wait strategy
    wait_strategy = wait_random_exponential(multiplier=1, min=min_wait, max=max_wait)
    
    # Create decorator
    return retry(
        retry=retry_condition,
        stop=stop_strategy,
        wait=wait_strategy,
        before_sleep=_before_retry_log,
        reraise=True,
    )

def retry_all_api_errors(
    max_attempts: int = 5,
    max_delay: Optional[float] = 120.0,
    min_wait: float = 1.0,
    max_wait: float = 30.0,
    ignore_circuit_breaker: bool = False,
    use_adaptive_wait: bool = True,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for retrying all retryable API errors with circuit breaking.
    
    Args:
        max_attempts: Maximum number of retry attempts
        max_delay: Maximum total delay before giving up
        min_wait: Minimum wait time between retries
        max_wait: Maximum wait time between retries
        ignore_circuit_breaker: Whether to ignore the circuit breaker state
        use_adaptive_wait: Use advanced adaptive wait strategy
        
    Returns:
        A decorator function that applies the retry logic
    """
    # Define the retry decorator using tenacity
    tenacity_retry = retry(
        retry=retry_if_exception(_is_retryable_exception),
        stop=tenacity.stop_any(
            stop_after_attempt(max_attempts),
            stop_after_delay(max_delay) if max_delay is not None else tenacity.stop_never
        ),
        wait=_adaptive_wait_strategy if use_adaptive_wait else 
            wait_random_exponential(multiplier=1, min=min_wait, max=max_wait),
        before_sleep=_before_retry_log,
        reraise=True,
    )
    
    # Define our wrapper that adds circuit breaking and enhanced error handling
    def wrapper(func: Callable[..., T]) -> Callable[..., T]:
        # Apply the tenacity retry decorator to the function
        retrying_func = tenacity_retry(func)
        
        # Define a wrapper that applies circuit breaking
        @wraps(func)
        def circuit_wrapped(*args: Any, **kwargs: Any) -> T:
            # We can't reliably track attempt counts with the current tenacity version
            # so we'll just skip this part
            
            # Track exceptions for circuit breaker
            last_exception = None
            
            # Custom retry logic to handle circuit breaker and metrics
            def custom_retry(retry_state: RetryCallState) -> None:
                nonlocal last_exception
                if retry_state.outcome.failed:
                    # Get the exception
                    exc = retry_state.outcome.exception()
                    last_exception = exc
                    
                    # Update circuit breaker if needed
                    if not ignore_circuit_breaker:
                        _check_circuit_breaker(exc)
                    
                    # Update failure metrics
                    with _retry_lock:
                        _retry_metrics["failures"] += 1
            
            # Attach the callback to the retry
            try:
                # Add before_sleep callback to track exceptions
                old_before_sleep = tenacity_retry.kwargs.get('before_sleep')
                
                def combined_before_sleep(retry_state):
                    # Call original before_sleep if it exists
                    if old_before_sleep:
                        old_before_sleep(retry_state)
                    
                    # Call our custom callback
                    custom_retry(retry_state)
                
                # Create a new Retrying object with our combined callback
                custom_tenacity_retry = retry(
                    retry=tenacity_retry.kwargs.get('retry'),
                    stop=tenacity_retry.kwargs.get('stop'),
                    wait=tenacity_retry.kwargs.get('wait'),
                    before_sleep=combined_before_sleep,
                    reraise=tenacity_retry.kwargs.get('reraise', True),
                )
                
                # Replace the retrying function
                retrying_func = custom_tenacity_retry(func)
            except Exception:
                # If we can't modify the retry, just continue with the original
                pass
                
            # Check the circuit breaker if needed
            if not ignore_circuit_breaker:
                if not _circuit_breaker.allow_request():
                    raise LLMServiceUnavailableError(
                        message=f"Circuit breaker is open (state: {_circuit_breaker.state.value}) due to persistent errors",
                        status_code=503
                    )
            
            try:
                # Call the retrying function
                result = retrying_func(*args, **kwargs)
                
                # Record success for circuit breaker and metrics
                if not ignore_circuit_breaker:
                    _reset_circuit_on_success()
                
                # Update success metrics - we no longer know if retries occurred
                # Just increment the counter for successful calls
                with _retry_lock:
                    _retry_metrics["successes_after_retry"] += 1
                
                return result
            except Exception as e:
                # Update circuit breaker state and failure metrics
                if not ignore_circuit_breaker:
                    _check_circuit_breaker(e)
                
                with _retry_lock:
                    _retry_metrics["failures"] += 1
                
                raise
        
        return circuit_wrapped
    
    return wrapper 