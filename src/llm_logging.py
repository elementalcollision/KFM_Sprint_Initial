"""
Specialized logging utilities for LLM API interactions.

This module provides structured logging capabilities specifically tailored 
for LLM API calls, including request-response correlation, performance metrics,
and sanitized logging of API interactions.
"""

import logging
import json
import time
import uuid
import datetime
import traceback
from typing import Dict, Any, Optional, Union, List, Tuple, NamedTuple
from dataclasses import dataclass, asdict

# Import the project's logging utilities
from src.logger import setup_logger, JSONFormatter
from src.exceptions import LLMAPIError, LLMAuthenticationError

# Create a dedicated logger for LLM API interactions
llm_api_logger = setup_logger('llm_api', 
                           level='INFO', 
                           console=True, 
                           file=True, 
                           json_format=True,
                           log_dir='logs/llm_api')

# Regular logger for simplified console output
regular_logger = setup_logger('llm_simple',
                           level='INFO',
                           console=True,
                           file=True,
                           json_format=False,
                           log_dir='logs/llm_api')

@dataclass
class RequestContext:
    """Contains metadata for tracking a request through the system."""
    request_id: str
    timestamp: str
    operation_type: str
    model_name: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return asdict(self)

def create_request_context(operation_type: str, 
                          model_name: str,
                          session_id: Optional[str] = None,
                          user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a request context object for tracking an LLM API call.
    
    Args:
        operation_type: The type of operation (e.g., 'reflection', 'generation')
        model_name: The name of the LLM model being used
        session_id: Optional session identifier for tracking user sessions
        user_id: Optional user identifier for user-specific tracking
        
    Returns:
        Dictionary with request context information
    """
    context = RequestContext(
        request_id=str(uuid.uuid4())[:8],
        timestamp=datetime.datetime.now().isoformat(),
        operation_type=operation_type,
        model_name=model_name,
        session_id=session_id,
        user_id=user_id
    )
    
    return context.to_dict()

def create_timer() -> Tuple[float, callable]:
    """
    Create a timer for measuring the duration of operations.
    
    Returns:
        Tuple of (start_time, get_elapsed_function)
    """
    start_time = time.time()
    
    def get_elapsed() -> float:
        return time.time() - start_time
    
    return start_time, get_elapsed

def calculate_performance_metrics(prompt_length: int, 
                                 response_length: int, 
                                 duration: float) -> Dict[str, Any]:
    """
    Calculate performance metrics for an LLM API call.
    
    Args:
        prompt_length: Length of the prompt in characters
        response_length: Length of the response in characters
        duration: Total duration of the API call in seconds
        
    Returns:
        Dictionary of performance metrics
    """
    # Rough estimation of tokens - can be refined with actual tokenizer
    est_prompt_tokens = prompt_length / 4  # Rough approximation of chars-to-tokens
    est_response_tokens = response_length / 4
    
    metrics = {
        'duration_seconds': duration,
        'prompt_length': prompt_length,
        'response_length': response_length,
        'estimated_prompt_tokens': int(est_prompt_tokens),
        'estimated_response_tokens': int(est_response_tokens),
        'estimated_total_tokens': int(est_prompt_tokens + est_response_tokens),
        'chars_per_second': int(response_length / duration) if duration > 0 else 0,
        'estimated_tokens_per_second': int(est_response_tokens / duration) if duration > 0 else 0
    }
    
    return metrics

def sanitize_log_data(data: Any) -> Any:
    """
    Sanitize data for logging, ensuring no sensitive information is included.
    
    Args:
        data: Input data to sanitize
        
    Returns:
        Sanitized data safe for logging
    """
    if data is None:
        return None
    
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            # Skip API keys and other sensitive data
            if any(sensitive in key.lower() for sensitive in ['key', 'token', 'secret', 'password', 'credential']):
                result[key] = "*** REDACTED ***"
            else:
                result[key] = sanitize_log_data(value)
        return result
    elif isinstance(data, list):
        return [sanitize_log_data(item) for item in data]
    elif isinstance(data, str) and len(data) > 1000:
        # Truncate long strings, keeping beginning and end
        return f"{data[:500]}... [truncated {len(data)-1000} chars] ...{data[-500:]}"
    else:
        return data

def sanitize_prompt_response(text: str, max_length: int = 1000) -> str:
    """
    Sanitize prompt or response text for logging.
    
    Args:
        text: Text to sanitize
        max_length: Maximum length to include
        
    Returns:
        Sanitized text safe for logging
    """
    if not text:
        return ""
    
    # Truncate text if it's too long
    if len(text) > max_length:
        half_length = max_length // 2
        return f"{text[:half_length]}... [truncated {len(text)-max_length} chars] ...{text[-half_length:]}"
    
    return text

def log_request(context: Dict[str, Any], 
                request_data: Dict[str, Any],
                additional_context: Optional[Dict[str, Any]] = None) -> None:
    """
    Log an LLM API request with structured data.
    
    Args:
        context: Request context dictionary
        request_data: Data about the request (sanitized)
        additional_context: Additional context information
    """
    request_id = context.get('request_id', 'unknown')
    log_data = {
        'event': 'llm_request',
        'context': context,
        'request': sanitize_log_data(request_data),
        'timestamp': datetime.datetime.now().isoformat()
    }
    
    if additional_context:
        log_data['additional_context'] = sanitize_log_data(additional_context)
    
    # Detailed JSON log
    llm_api_logger.info(json.dumps(log_data))
    
    # Simplified log for console/regular log file
    model_name = context.get('model_name', 'unknown')
    operation = context.get('operation_type', 'unknown')
    regular_logger.info(f"LLM REQUEST [{request_id}]: {operation} using {model_name}")

def log_response(context: Dict[str, Any],
                response_data: Union[str, Dict[str, Any]],
                duration: float,
                status: str = 'success',
                additional_metrics: Optional[Dict[str, Any]] = None) -> None:
    """
    Log an LLM API response with structured data.
    
    Args:
        context: Request context dictionary
        response_data: The response data or text
        duration: Duration of the request in seconds
        status: Status of the response ('success' or 'error')
        additional_metrics: Additional performance metrics
    """
    request_id = context.get('request_id', 'unknown')
    
    # If response is string, create a basic dict with the text
    response_dict = {'text': response_data} if isinstance(response_data, str) else response_data
    
    # Basic metrics if not provided
    metrics = additional_metrics or {}
    if 'duration_seconds' not in metrics:
        metrics['duration_seconds'] = duration
    
    log_data = {
        'event': 'llm_response',
        'context': context,
        'response': {'status': status},
        'metrics': metrics,
        'timestamp': datetime.datetime.now().isoformat()
    }
    
    # Add sanitized preview of the response
    if isinstance(response_data, str):
        log_data['response']['text_preview'] = sanitize_prompt_response(response_data)
        log_data['response']['length'] = len(response_data)
    
    # Detailed JSON log
    llm_api_logger.info(json.dumps(log_data))
    
    # Simplified log for console/regular log file
    if status == 'success':
        regular_logger.info(f"LLM RESPONSE [{request_id}]: Success in {duration:.2f}s, {metrics.get('estimated_tokens_per_second', 0)} tokens/sec")
    else:
        regular_logger.info(f"LLM RESPONSE [{request_id}]: Status={status}, duration={duration:.2f}s")

def log_api_error(context: Dict[str, Any],
                  error: Union[Exception, LLMAPIError],
                  duration: float,
                  attempt: Optional[int] = None,
                  max_attempts: Optional[int] = None,
                  retry_after: Optional[float] = None,
                  request_data: Optional[Dict[str, Any]] = None) -> None:
    """
    Log an LLM API error with structured data.
    
    Args:
        context: Request context dictionary
        error: The exception that occurred
        duration: Duration before error in seconds
        attempt: Current attempt number (for retries)
        max_attempts: Maximum attempts allowed
        retry_after: When the next retry will happen (seconds)
        request_data: Original request data for context
    """
    request_id = context.get('request_id', 'unknown')
    
    # Extract error details
    error_type = type(error).__name__
    error_message = str(error)
    error_traceback = traceback.format_exc()
    
    # Get original error if available
    original_error = getattr(error, 'original_error', None)
    original_error_type = type(original_error).__name__ if original_error else None
    
    # Check if error is retryable
    is_retryable = getattr(error, 'is_retryable', False)
    
    log_data = {
        'event': 'llm_error',
        'context': context,
        'error': {
            'type': error_type,
            'message': error_message,
            'traceback': error_traceback,
            'original_error_type': original_error_type,
            'is_retryable': is_retryable
        },
        'duration_seconds': duration,
        'timestamp': datetime.datetime.now().isoformat()
    }
    
    # Add retry information if available
    if attempt is not None:
        log_data['retry'] = {
            'attempt': attempt,
            'max_attempts': max_attempts,
            'retry_after': retry_after,
            'is_final_attempt': attempt >= max_attempts if max_attempts else True
        }
    
    # Add sanitized request data if available
    if request_data:
        log_data['request'] = sanitize_log_data(request_data)
    
    # Detailed JSON log
    llm_api_logger.error(json.dumps(log_data))
    
    # Simplified log for console/regular log file
    retry_info = f", attempt {attempt}/{max_attempts}" if attempt is not None else ""
    regular_logger.error(f"LLM ERROR [{request_id}]: {error_type}: {error_message}{retry_info}, duration={duration:.2f}s")
    
    # Log additional error details at debug level
    if original_error:
        regular_logger.debug(f"LLM ERROR [{request_id}] Original error: {original_error_type}: {str(original_error)}") 