"""
Error Handling Examples

This file contains examples of using the error handling system implemented in Task 49.
These examples demonstrate different patterns for handling various error scenarios
when working with LLM API calls.
"""

import os
import time
from typing import Dict, Any

# Import error handling components
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
    LLMInternalError
)
from src.error_classifier import ErrorClassifier, ErrorCategory
from src.retry_strategy import (
    ExponentialBackoffStrategy,
    retry_on_network_errors,
    retry_on_rate_limit,
    retry_on_server_errors,
    retry_all_api_errors
)
from src.error_recovery import (
    CircuitBreaker,
    TokenBucketRateLimiter,
    RequestQueueManager,
    ErrorRecoveryStrategies
)
from src.llm_logging import ErrorLogger, LogLevel
from src.langgraph_nodes import call_llm_for_reflection_v3, generate_error_reflection


# Example 1: Basic Error Handling with Try/Except
def basic_error_handling(prompt: str) -> str:
    """
    Basic example of error handling using try/except blocks.
    """
    try:
        # Attempt to get a reflection from the LLM
        reflection = call_llm_for_reflection_v3(prompt)
        return reflection
    except LLMTimeoutError as e:
        # Handle timeout errors specifically
        print(f"Timeout error occurred: {e}")
        return f"Reflection timed out. Please try a shorter prompt or try again later."
    except LLMAuthenticationError as e:
        # Handle authentication errors
        print(f"Authentication error: {e}")
        return f"Authentication error. Please check API key configuration."
    except LLMRateLimitError as e:
        # Handle rate limit errors
        print(f"Rate limit exceeded: {e}")
        return f"Rate limit exceeded. Please try again in a few minutes."
    except LLMAPIError as e:
        # Handle all other API errors
        print(f"API error: {e}")
        return f"Error generating reflection: {e.get_user_message()}"
    except Exception as e:
        # Handle any unexpected errors
        print(f"Unexpected error: {e}")
        return f"An unexpected error occurred."


# Example 2: Using Error Classification
def with_error_classification(prompt: str) -> Dict[str, Any]:
    """
    Example using error classification to categorize and handle errors.
    """
    classifier = ErrorClassifier()
    
    try:
        reflection = call_llm_for_reflection_v3(prompt)
        return {"success": True, "reflection": reflection}
    except Exception as e:
        # Classify the error
        classified_error = classifier.classify_error(e)
        
        # Log detailed error information
        print(f"Error category: {classified_error.get_category()}")
        print(f"Error severity: {classified_error.get_severity()}")
        print(f"Error is retryable: {classified_error.is_retryable}")
        
        # Return structured error response
        return {
            "success": False,
            "error_type": classified_error.__class__.__name__,
            "error_message": str(classified_error),
            "error_category": classified_error.get_category(),
            "is_retryable": classified_error.is_retryable,
            "fallback_reflection": generate_error_reflection(
                prompt, classified_error, strategy="content_aware"
            )
        }


# Example 3: Using Retry Decorators
@retry_on_network_errors(max_retries=3, base_delay=1.0)
def with_network_retry(prompt: str) -> str:
    """
    Example using retry decorator for network errors.
    """
    # This function will automatically retry on network errors
    return call_llm_for_reflection_v3(prompt)


@retry_on_rate_limit(max_retries=5, respect_retry_after=True)
def with_rate_limit_retry(prompt: str) -> str:
    """
    Example using retry decorator specifically for rate limit errors.
    """
    # This function will automatically retry on rate limit errors,
    # respecting any retry-after headers in the response
    return call_llm_for_reflection_v3(prompt)


@retry_all_api_errors(
    max_retries=3, 
    base_delay=1.0,
    max_delay=10.0,
    jitter_factor=0.1
)
def with_comprehensive_retry(prompt: str) -> str:
    """
    Example using comprehensive retry for all retryable API errors.
    """
    # This function will retry on any retryable API error
    return call_llm_for_reflection_v3(prompt)


# Example 4: Custom Backoff Strategy
def with_custom_backoff(prompt: str) -> str:
    """
    Example using a custom backoff strategy.
    """
    # Create a custom backoff strategy
    backoff = ExponentialBackoffStrategy(
        base_delay=2.0,
        max_delay=30.0,
        max_retries=4,
        jitter_factor=0.2
    )
    
    # Define a function with the custom backoff
    @retry_all_api_errors(backoff_strategy=backoff)
    def call_with_custom_backoff(p):
        return call_llm_for_reflection_v3(p)
    
    # Call the function
    return call_with_custom_backoff(prompt)


# Example 5: Using Circuit Breaker
def with_circuit_breaker(prompt: str) -> str:
    """
    Example using circuit breaker pattern to prevent cascading failures.
    """
    # Create a circuit breaker
    breaker = CircuitBreaker(
        failure_threshold=3,       # Open after 3 failures
        recovery_timeout=60.0,     # Stay open for 60 seconds
        success_threshold=2        # Close after 2 successful tries
    )
    
    # Check if circuit allows request
    if breaker.allow_request():
        try:
            # Make API call
            result = call_llm_for_reflection_v3(prompt)
            # Report success
            breaker.record_success()
            return result
        except Exception as e:
            # Report failure
            breaker.record_failure()
            print(f"Request failed, circuit breaker updated: {e}")
            return generate_error_reflection(prompt, e, strategy="simple")
    else:
        # Circuit is open, use fallback
        print("Circuit breaker is open, using fallback")
        return "The system is currently unavailable due to repeated failures. Please try again later."


# Example 6: Using Rate Limiting
def with_rate_limiting(prompt: str) -> str:
    """
    Example using token bucket algorithm for rate limiting.
    """
    # Create a rate limiter (5 tokens per second, max 10 tokens)
    rate_limiter = TokenBucketRateLimiter(rate=5.0, max_tokens=10)
    
    # Try to consume a token
    if rate_limiter.consume():
        # We have capacity, make the API call
        return call_llm_for_reflection_v3(prompt)
    else:
        # We're rate limited, provide feedback
        print("Rate limited, cannot make request at this time")
        return "Request rate limit exceeded. Please try again in a moment."


# Example 7: Using Request Queue
def with_request_queue(prompts: list) -> Dict[str, str]:
    """
    Example using request queue to manage multiple concurrent requests.
    """
    # Create a queue manager
    queue_manager = RequestQueueManager(
        max_queue_size=100,
        processing_interval=0.2,
        retry_limit=2
    )
    
    # Add all requests to the queue with different priorities
    request_ids = {}
    for i, prompt in enumerate(prompts):
        # Alternate between high and low priority
        priority = 1 if i % 2 == 0 else 2
        request_ids[i] = queue_manager.enqueue(
            func=call_llm_for_reflection_v3,
            args=(prompt,),
            kwargs={},
            priority=priority
        )
    
    # Start processing in background
    queue_manager.start_processing()
    
    # Collect results as they become available
    results = {}
    for i, request_id in request_ids.items():
        try:
            results[i] = queue_manager.get_result(request_id, timeout=30.0)
        except TimeoutError:
            results[i] = f"Request {i} timed out"
        except Exception as e:
            results[i] = f"Request {i} failed: {str(e)}"
    
    # Stop processing
    queue_manager.stop_processing()
    
    return results


# Example 8: Using Structured Logging
def with_structured_logging(prompt: str) -> str:
    """
    Example using structured logging for API calls.
    """
    # Create a logger
    logger = ErrorLogger(
        log_dir='logs/llm_api',
        app_name='error_handling_examples'
    )
    
    # Log the request
    request_id = logger.log_request(
        operation='generate_reflection',
        parameters={'prompt': prompt[:50] + '...' if len(prompt) > 50 else prompt},
        context={'example': 'structured_logging'}
    )
    
    start_time = time.time()
    try:
        # Make API call
        reflection = call_llm_for_reflection_v3(prompt)
        
        # Log successful response
        duration_ms = int((time.time() - start_time) * 1000)
        logger.log_response(
            request_id=request_id,
            response=reflection,
            duration_ms=duration_ms
        )
        
        return reflection
    except Exception as e:
        # Log error
        duration_ms = int((time.time() - start_time) * 1000)
        logger.log_error(
            request_id=request_id,
            error=e,
            duration_ms=duration_ms,
            level=LogLevel.ERROR
        )
        
        # Return fallback
        return generate_error_reflection(prompt, e, strategy="content_aware")


# Example 9: Comprehensive Error Handling Solution
def comprehensive_example(prompt: str, retries: int = 3, timeout: float = 30.0) -> Dict[str, Any]:
    """
    Comprehensive example combining multiple error handling strategies.
    """
    # Create components
    logger = ErrorLogger(log_dir='logs/llm_api', app_name='comprehensive_example')
    classifier = ErrorClassifier()
    rate_limiter = TokenBucketRateLimiter(rate=10.0, max_tokens=30)
    circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)
    
    # Configure backoff strategy
    backoff = ExponentialBackoffStrategy(
        base_delay=1.0,
        max_delay=20.0,
        max_retries=retries,
        jitter_factor=0.1
    )
    
    # Log request
    request_id = logger.log_request(
        operation='generate_reflection',
        parameters={'prompt': prompt[:50] + '...' if len(prompt) > 50 else prompt},
        context={'timeout': timeout, 'retries': retries}
    )
    
    # Check rate limiting
    if not rate_limiter.consume():
        logger.log_error(
            request_id=request_id,
            error="Rate limit exceeded",
            level=LogLevel.WARNING
        )
        return {
            "success": False,
            "error_type": "RateLimitExceeded",
            "message": "Request rate limit exceeded. Please try again later."
        }
    
    # Check circuit breaker
    if not circuit_breaker.allow_request():
        logger.log_error(
            request_id=request_id,
            error="Circuit breaker open",
            level=LogLevel.WARNING
        )
        return {
            "success": False,
            "error_type": "CircuitBreakerOpen",
            "message": "Service is currently unavailable due to repeated failures. Please try again later."
        }
    
    # Define retry function
    @retry_all_api_errors(backoff_strategy=backoff)
    def call_with_retry(p):
        return call_llm_for_reflection_v3(p, timeout=timeout)
    
    # Attempt API call with retry
    start_time = time.time()
    try:
        reflection = call_with_retry(prompt)
        
        # Record success
        duration_ms = int((time.time() - start_time) * 1000)
        circuit_breaker.record_success()
        logger.log_response(
            request_id=request_id,
            response=reflection,
            duration_ms=duration_ms
        )
        
        return {
            "success": True,
            "reflection": reflection,
            "duration_ms": duration_ms
        }
    except Exception as e:
        # Record failure
        duration_ms = int((time.time() - start_time) * 1000)
        circuit_breaker.record_failure()
        
        # Classify error
        classified_error = classifier.classify_error(e)
        
        # Log error
        logger.log_error(
            request_id=request_id,
            error=classified_error,
            duration_ms=duration_ms,
            level=LogLevel.ERROR
        )
        
        # Generate fallback
        fallback = generate_error_reflection(prompt, classified_error, strategy="content_aware")
        
        return {
            "success": False,
            "error_type": classified_error.__class__.__name__,
            "error_message": str(classified_error),
            "is_retryable": classified_error.is_retryable,
            "duration_ms": duration_ms,
            "fallback_reflection": fallback
        }


# Example 10: Error Recovery Strategies
def with_recovery_strategies(prompt: str) -> str:
    """
    Example using specialized recovery strategies for different error types.
    """
    # Create recovery strategies
    recovery = ErrorRecoveryStrategies()
    
    try:
        # Attempt API call
        return call_llm_for_reflection_v3(prompt)
    except LLMRateLimitError as e:
        # Apply rate limit recovery
        recovery_action = recovery.handle_rate_limit_error(e)
        print(f"Rate limit recovery action: {recovery_action}")
        
        if recovery_action == "retry":
            # Wait and retry based on retry-after header
            retry_after = e.get_retry_after() or 5
            print(f"Retrying after {retry_after} seconds")
            time.sleep(retry_after)
            return call_llm_for_reflection_v3(prompt)
        else:
            # Use fallback
            return generate_error_reflection(prompt, e, strategy="content_aware")
    except LLMNetworkError as e:
        # Apply network error recovery
        recovery_action = recovery.handle_network_error(e)
        print(f"Network error recovery action: {recovery_action}")
        
        if recovery_action == "retry":
            # Retry with backoff
            time.sleep(2)
            return call_llm_for_reflection_v3(prompt)
        else:
            # Use fallback
            return generate_error_reflection(prompt, e, strategy="simple")
    except LLMServerError as e:
        # Apply server error recovery
        recovery_action = recovery.handle_server_error(e)
        print(f"Server error recovery action: {recovery_action}")
        
        if recovery_action == "check_health":
            # Check service health before retry
            if recovery.check_service_health():
                time.sleep(1)
                return call_llm_for_reflection_v3(prompt)
            else:
                return generate_error_reflection(prompt, e, strategy="simple")
        else:
            # Use fallback
            return generate_error_reflection(prompt, e, strategy="simple")
    except LLMAPIError as e:
        # Generic API error recovery
        return generate_error_reflection(prompt, e, strategy="content_aware")


# Usage examples
if __name__ == "__main__":
    test_prompt = "Reflect on the importance of error handling in AI systems."
    
    print("\n--- Example 1: Basic Error Handling ---")
    result1 = basic_error_handling(test_prompt)
    print(f"Result: {result1[:100]}...")
    
    print("\n--- Example 2: Using Error Classification ---")
    result2 = with_error_classification(test_prompt)
    print(f"Success: {result2['success']}")
    if result2['success']:
        print(f"Reflection: {result2['reflection'][:100]}...")
    else:
        print(f"Error type: {result2['error_type']}")
        print(f"Fallback: {result2['fallback_reflection'][:100]}...")
    
    print("\n--- Example 3: Using Retry Decorators ---")
    result3 = with_network_retry(test_prompt)
    print(f"Result: {result3[:100]}...")
    
    print("\n--- Example 4: Custom Backoff Strategy ---")
    result4 = with_custom_backoff(test_prompt)
    print(f"Result: {result4[:100]}...")
    
    print("\n--- Example 5: Using Circuit Breaker ---")
    result5 = with_circuit_breaker(test_prompt)
    print(f"Result: {result5[:100]}...")
    
    print("\n--- Example 6: Using Rate Limiting ---")
    result6 = with_rate_limiting(test_prompt)
    print(f"Result: {result6[:100]}...")
    
    print("\n--- Example 7: Using Request Queue ---")
    prompts = [f"{test_prompt} (Variation {i})" for i in range(3)]
    result7 = with_request_queue(prompts)
    for i, response in result7.items():
        print(f"Result {i}: {response[:100]}...")
    
    print("\n--- Example 8: Using Structured Logging ---")
    result8 = with_structured_logging(test_prompt)
    print(f"Result: {result8[:100]}...")
    
    print("\n--- Example 9: Comprehensive Error Handling ---")
    result9 = comprehensive_example(test_prompt)
    print(f"Success: {result9['success']}")
    if result9['success']:
        print(f"Reflection: {result9['reflection'][:100]}...")
    else:
        print(f"Error type: {result9['error_type']}")
        print(f"Fallback: {result9['fallback_reflection'][:100]}...")
    
    print("\n--- Example 10: Error Recovery Strategies ---")
    result10 = with_recovery_strategies(test_prompt)
    print(f"Result: {result10[:100]}...") 