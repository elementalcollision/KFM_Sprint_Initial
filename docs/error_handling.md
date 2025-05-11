# Error Handling System Documentation

## Overview

The error handling system provides a comprehensive framework for handling errors in LLM API calls with Google's Generative AI API. It implements a robust error management approach that includes:

- Custom exception hierarchy
- Error detection and classification
- Advanced retry strategies with exponential backoff
- Fallback mechanisms for graceful degradation
- Structured logging for debugging and monitoring
- Specialized recovery strategies for different error types

This system ensures the application remains stable and provides meaningful feedback when issues occur during LLM API interactions.

## Architecture

The error handling system consists of the following components:

### 1. Custom Exception Hierarchy (`src/exceptions.py`)

A three-tier hierarchy of custom exceptions:
- Base class: `LLMAPIError`
- Second tier: `LLMNetworkError`, `LLMClientError`, `LLMServerError`
- Specialized exceptions: `LLMTimeoutError`, `LLMConnectionError`, `LLMAuthenticationError`, etc.

### 2. Error Classification (`src/error_classifier.py`)

- Analyzes API responses to identify error types
- Maps HTTP status codes to appropriate exceptions
- Uses pattern recognition to detect specific errors

### 3. Retry Strategy (`src/retry_strategy.py`)

- Implements exponential backoff with jitter
- Provides specialized retry decorators for different error types
- Integrates circuit breaker pattern for persistent errors

### 4. Error Recovery (`src/error_recovery.py`)

- Implements token bucket algorithm for rate limiting
- Provides request queuing and prioritization
- Implements circuit breaker for service protection
- Manages network connections and health checks

### 5. Logging System (`src/llm_logging.py`)

- Provides structured logging for API calls and errors
- Tracks request-response pairs with consistent IDs
- Includes performance metrics and timing information
- Sanitizes sensitive information automatically

### 6. Enhanced LLM Functions (`src/langgraph_nodes.py`)

- `call_llm_for_reflection_v3`: Main function with comprehensive error handling
- `generate_error_reflection`: Provides fallback responses when API calls fail

## Exception Hierarchy

```
LLMAPIError (base class)
├── LLMNetworkError
│   ├── LLMTimeoutError
│   └── LLMConnectionError
├── LLMClientError
│   ├── LLMAuthenticationError
│   ├── LLMRateLimitError
│   └── LLMInvalidRequestError
└── LLMServerError
    ├── LLMServiceUnavailableError
    └── LLMInternalError
```

Each exception provides:
- Access to the original exception/response
- HTTP status code and error message
- Request ID and additional context
- Methods for formatting errors for logging
- User-friendly error messages
- Debugging information

The hierarchy also distinguishes between retryable and non-retryable errors through the `is_retryable` property.

## Error Classification

The `ErrorClassifier` in `src/error_classifier.py` handles error detection and classification with:

- Status code mapping
- Error message pattern recognition
- Structured error extraction
- Google GenAI-specific error handling

Example usage:

```python
from src.error_classifier import ErrorClassifier

# Create an instance of the classifier
classifier = ErrorClassifier()

try:
    # Make an API call
    response = api.generate_content(prompt)
except Exception as e:
    # Classify the error
    classified_error = classifier.classify_error(e)
    # Handle based on error type
    if classified_error.is_retryable:
        # Retry the operation
        ...
    else:
        # Use fallback mechanism
        ...
```

## Retry Strategies

The retry system in `src/retry_strategy.py` provides several retry decorators:

- `retry_on_network_errors`: Retries on network-related errors
- `retry_on_rate_limit`: Specialized for rate limit errors, respects retry-after headers
- `retry_on_server_errors`: Handles server-side issues
- `retry_all_api_errors`: General retry strategy for all retryable API errors

Example usage:

```python
from src.retry_strategy import retry_on_network_errors, ExponentialBackoffStrategy

# Create a custom backoff strategy
backoff = ExponentialBackoffStrategy(
    base_delay=1.0,
    max_delay=60.0,
    max_retries=5
)

# Apply the retry decorator
@retry_on_network_errors(backoff_strategy=backoff)
def call_api(prompt):
    # Make API call
    return api.generate_content(prompt)
```

## Error Recovery Strategies

The `src/error_recovery.py` module provides specialized recovery strategies:

### 1. Token Bucket Rate Limiter

```python
from src.error_recovery import TokenBucketRateLimiter

# Create a rate limiter (10 tokens per second, max 60 tokens)
rate_limiter = TokenBucketRateLimiter(rate=10.0, max_tokens=60)

# Before making an API call, check if we can proceed
if rate_limiter.consume():
    # Make API call
    ...
else:
    # Handle rate limiting
    ...
```

### 2. Circuit Breaker

```python
from src.error_recovery import CircuitBreaker

# Create a circuit breaker
breaker = CircuitBreaker(
    failure_threshold=5,       # Open after 5 failures
    recovery_timeout=30.0,     # Stay open for 30 seconds
    success_threshold=2        # Close after 2 successful tries
)

# Before making an API call
if breaker.allow_request():
    try:
        # Make API call
        response = api.generate_content(prompt)
        # Report success
        breaker.record_success()
        return response
    except Exception as e:
        # Report failure
        breaker.record_failure()
        raise
else:
    # Circuit is open, use fallback
    ...
```

### 3. Request Queue Manager

```python
from src.error_recovery import RequestQueueManager

# Create a queue manager
queue_manager = RequestQueueManager(
    max_queue_size=100,
    processing_interval=0.5
)

# Add a request to the queue (with priority)
request_id = queue_manager.enqueue(
    func=api.generate_content,
    args=(prompt,),
    kwargs={},
    priority=1
)

# Get the result when available
result = queue_manager.get_result(request_id, timeout=10.0)
```

## Logging System

The logging system in `src/llm_logging.py` provides structured logging for API interactions:

```python
from src.llm_logging import ErrorLogger, LogLevel

# Create a logger
logger = ErrorLogger(
    log_dir='logs/llm_api',
    app_name='my_application'
)

# Log API request
request_id = logger.log_request(
    operation='generate_content',
    parameters={'prompt': 'shortened prompt...'},
    context={'user_id': '123'}
)

try:
    # Make API call
    response = api.generate_content(prompt)
    # Log success
    logger.log_response(
        request_id=request_id,
        response=response,
        duration_ms=1200
    )
except Exception as e:
    # Log error
    logger.log_error(
        request_id=request_id,
        error=e,
        level=LogLevel.ERROR
    )
```

## Enhanced LLM Function

The `call_llm_for_reflection_v3` function in `src/langgraph_nodes.py` integrates all error handling components:

```python
from src.langgraph_nodes import call_llm_for_reflection_v3

# Basic usage
result = call_llm_for_reflection_v3(prompt)

# Advanced usage with configuration
result = call_llm_for_reflection_v3(
    prompt,
    max_retries=3,
    timeout=30.0,
    priority=2,
    fallback_strategy='simple'
)
```

## Fallback Mechanisms

When API calls fail persistently, fallback mechanisms provide graceful degradation:

1. **Simple Fallback**: Returns a generic error reflection
2. **Content-Aware Fallback**: Analyzes prompt to generate a context-relevant response
3. **Cached Fallback**: Uses previous successful responses for similar prompts

The `generate_error_reflection` function in `src/langgraph_nodes.py` implements these fallback strategies.

## Best Practices

### 1. Error Handling in Client Code

```python
from src.exceptions import LLMAPIError, LLMTimeoutError, LLMRateLimitError
from src.langgraph_nodes import call_llm_for_reflection_v3

try:
    result = call_llm_for_reflection_v3(prompt)
    # Process result
    ...
except LLMTimeoutError as e:
    # Handle timeout specifically
    log.warning(f"Timeout occurred: {e}")
    # Show user-friendly message
    return "The system is taking longer than expected. Please try again."
except LLMRateLimitError as e:
    # Handle rate limiting
    log.warning(f"Rate limit exceeded: {e}")
    return "We're experiencing high demand. Please try again in a few minutes."
except LLMAPIError as e:
    # Handle all other API errors
    log.error(f"API error: {e}")
    return "An error occurred while processing your request."
```

### 2. Configuring Retry Strategies

For optimal retry behavior:

- Use shorter retry intervals for interactive applications
- Use longer intervals with more retries for batch processing
- Add jitter to prevent thundering herd problems
- Respect retry-after headers when available
- Set appropriate timeout values based on operation type

### 3. Monitoring and Debugging

To effectively monitor and debug API errors:

- Analyze logs in `logs/llm_api` directory
- Look for patterns in error frequencies and types
- Monitor rate limit errors to adjust request rates
- Track performance metrics for optimization
- Use request IDs to correlate logs across the system

## Troubleshooting Guide

| Issue | Possible Cause | Solution |
|-------|----------------|----------|
| Frequent timeout errors | Network latency or API service overload | Increase timeout settings, reduce request complexity |
| Rate limit errors | Too many requests in short time | Implement request throttling, increase rate limiter capacity |
| Authentication errors | Invalid or expired API key | Check API key configuration, rotate keys if needed |
| Circuit breaker stays open | Persistent API service issues | Monitor service status, implement alternative providers |
| High memory usage | Too many retries or queued requests | Limit queue size, reduce max retry count |
| Poor performance | Inefficient error handling | Use profiling to identify bottlenecks, optimize critical paths |

## Performance Considerations

- Token bucket algorithm has minimal CPU impact
- Circuit breaker reduces load during outages
- Logging system uses efficient JSON serialization
- Request queue manager prevents memory leaks
- Exponential backoff reduces unnecessary API calls

## Configuration Options

Key configuration options:

```python
# Rate Limiter Configuration
rate_limiter = TokenBucketRateLimiter(
    rate=10.0,              # Tokens per second
    max_tokens=60,          # Maximum token bucket size
    refill_interval=0.1,    # Refill interval in seconds
    adaptive=True           # Enable automatic rate adjustment
)

# Circuit Breaker Configuration
circuit_breaker = CircuitBreaker(
    failure_threshold=5,     # Number of failures before opening
    recovery_timeout=60.0,   # Time to stay open in seconds
    success_threshold=2,     # Successes needed to close
    half_open_capacity=0.2   # Percentage of requests to try in half-open state
)

# Retry Strategy Configuration
backoff_strategy = ExponentialBackoffStrategy(
    base_delay=1.0,          # Initial delay in seconds
    max_delay=60.0,          # Maximum delay in seconds
    max_retries=5,           # Maximum number of retries
    jitter_factor=0.1        # Randomness factor for delay
)
```

## Integration with Langgraph

The error handling system integrates seamlessly with langgraph nodes:

```python
from langgraph.graph import StateGraph
from src.langgraph_nodes import reflection_node, call_llm_for_reflection_v3

# Define the graph
graph = StateGraph()

# Add nodes that use the enhanced LLM function
graph.add_node("reflection", reflection_node)

# Error handling is automatically applied
# No changes needed to the graph structure
```

## Conclusion

The comprehensive error handling system provides robust protection against various failure modes when working with LLM APIs. By using this system, applications can:

- Gracefully handle API errors
- Automatically retry failed operations
- Implement rate limiting to prevent overload
- Provide meaningful feedback to users
- Maintain detailed logs for debugging
- Ensure system stability during service disruptions

For additional assistance or feature requests, please contact the development team. 