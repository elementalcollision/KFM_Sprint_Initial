"""
Custom exception classes for LLM API error handling.

This module defines a hierarchy of exception classes for handling errors
that may occur when making calls to Large Language Model APIs (specifically
Google's Generative AI API). These exceptions provide structured error information
and help with implementing appropriate retry and recovery strategies.
"""

import time
from typing import Any, Dict, Optional, Union
from http import HTTPStatus


class LLMAPIError(Exception):
    """Base exception class for all LLM API related errors."""
    
    def __init__(
        self, 
        message: str, 
        status_code: Optional[int] = None,
        request_id: Optional[str] = None,
        original_error: Optional[Exception] = None,
        response_data: Optional[Dict[str, Any]] = None,
        request_data: Optional[Dict[str, Any]] = None,
        timestamp: Optional[float] = None
    ):
        """Initialize the LLM API error.
        
        Args:
            message: Human-readable error message
            status_code: HTTP status code if applicable
            request_id: Unique identifier for the request if available
            original_error: The original exception that caused this error
            response_data: Raw response data from the API
            request_data: Data sent in the request (sensitive data removed)
            timestamp: When the error occurred (defaults to current time)
        """
        self.message = message
        self.status_code = status_code
        self.request_id = request_id
        self.original_error = original_error
        self.response_data = response_data or {}
        self.request_data = request_data or {}
        self.timestamp = timestamp or time.time()
        
        # Construct the full error message
        full_message = f"{message}"
        if status_code:
            full_message += f" (Status: {status_code})"
        if request_id:
            full_message += f" [Request ID: {request_id}]"
            
        super().__init__(full_message)
    
    @property
    def is_retryable(self) -> bool:
        """Whether this error type should typically be retried."""
        return False  # Base implementation, override in subclasses
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the exception to a dictionary for logging/serialization."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "status_code": self.status_code,
            "request_id": self.request_id,
            "timestamp": self.timestamp,
            "is_retryable": self.is_retryable,
            "response_data": self.response_data,
            # Filter request data to remove sensitive information
            "request_data": {
                k: v for k, v in self.request_data.items() 
                if k not in ["api_key", "credentials", "token"]
            },
        }
        
    @classmethod
    def from_response(cls, response, message=None):
        """Create an appropriate exception instance from a response object.
        
        Args:
            response: The API response object
            message: Optional message override
            
        Returns:
            The appropriate LLMAPIError subclass instance
        """
        status_code = getattr(response, "status_code", None)
        
        # Extract data from the response if possible
        try:
            data = response.json() if hasattr(response, "json") else {}
        except Exception:
            data = {}
            
        # Extract request ID if available
        request_id = data.get("requestId") or response.headers.get("x-request-id") if hasattr(response, "headers") else None
        
        # Default message if none provided
        if not message:
            message = data.get("error", {}).get("message", "Unknown API error occurred")
            
        # Map status codes to appropriate exception types
        if status_code:
            if 400 <= status_code < 500:
                if status_code == 401:
                    return LLMAuthenticationError(
                        message=message or "Authentication failed",
                        status_code=status_code,
                        request_id=request_id,
                        response_data=data
                    )
                elif status_code == 429:
                    return LLMRateLimitError(
                        message=message or "Rate limit exceeded",
                        status_code=status_code,
                        request_id=request_id,
                        response_data=data
                    )
                else:
                    return LLMInvalidRequestError(
                        message=message or f"Invalid request: {status_code}",
                        status_code=status_code,
                        request_id=request_id,
                        response_data=data
                    )
            elif 500 <= status_code < 600:
                if status_code == 503:
                    return LLMServiceUnavailableError(
                        message=message or "Service unavailable",
                        status_code=status_code,
                        request_id=request_id,
                        response_data=data
                    )
                else:
                    return LLMInternalError(
                        message=message or f"Server error: {status_code}",
                        status_code=status_code,
                        request_id=request_id,
                        response_data=data
                    )
                
        # If we can't determine a specific error type, return the base error
        return LLMAPIError(
            message=message or "Unknown API error",
            status_code=status_code,
            request_id=request_id,
            response_data=data
        )


# Network Error Classes
class LLMNetworkError(LLMAPIError):
    """Base class for network-related errors during LLM API calls."""
    
    @property
    def is_retryable(self) -> bool:
        """Network errors are typically retryable."""
        return True


class LLMTimeoutError(LLMNetworkError):
    """Raised when an LLM API request times out."""
    
    def __init__(
        self, 
        message: str = "Request timed out", 
        **kwargs
    ):
        super().__init__(message=message, **kwargs)


class LLMConnectionError(LLMNetworkError):
    """Raised when there's a connection error to the LLM API."""
    
    def __init__(
        self, 
        message: str = "Failed to connect to API", 
        **kwargs
    ):
        super().__init__(message=message, **kwargs)


# Client Error Classes
class LLMClientError(LLMAPIError):
    """Base class for client-side errors (4xx status codes)."""
    
    @property
    def is_retryable(self) -> bool:
        """Client errors are typically not retryable."""
        return False


class LLMAuthenticationError(LLMClientError):
    """Raised when authentication fails (invalid API key)."""
    
    def __init__(
        self, 
        message: str = "Authentication failed", 
        **kwargs
    ):
        super().__init__(message=message, **kwargs)


class LLMRateLimitError(LLMClientError):
    """Raised when rate limits are exceeded."""
    
    def __init__(
        self, 
        message: str = "Rate limit exceeded", 
        **kwargs
    ):
        super().__init__(message=message, **kwargs)
    
    @property
    def is_retryable(self) -> bool:
        """Rate limit errors are retryable after a delay."""
        return True


class LLMInvalidRequestError(LLMClientError):
    """Raised when the request is invalid (malformed prompt, etc.)."""
    
    def __init__(
        self, 
        message: str = "Invalid request", 
        **kwargs
    ):
        super().__init__(message=message, **kwargs)


# Server Error Classes
class LLMServerError(LLMAPIError):
    """Base class for server-side errors (5xx status codes)."""
    
    @property
    def is_retryable(self) -> bool:
        """Server errors are typically retryable."""
        return True


class LLMServiceUnavailableError(LLMServerError):
    """Raised when the LLM service is unavailable."""
    
    def __init__(
        self, 
        message: str = "Service temporarily unavailable", 
        **kwargs
    ):
        super().__init__(message=message, **kwargs)


class LLMInternalError(LLMServerError):
    """Raised when the LLM service encounters an internal error."""
    
    def __init__(
        self, 
        message: str = "Internal server error", 
        **kwargs
    ):
        super().__init__(message=message, **kwargs)


# Utility functions
def map_exception_to_llm_error(exception: Exception) -> LLMAPIError:
    """Convert a standard exception to the appropriate LLM API error.
    
    Args:
        exception: The exception to convert
        
    Returns:
        An instance of the appropriate LLMAPIError subclass
    """
    import socket
    import requests
    from urllib3.exceptions import ReadTimeoutError, ConnectTimeoutError
    
    if isinstance(exception, (socket.timeout, TimeoutError, ReadTimeoutError, ConnectTimeoutError)):
        return LLMTimeoutError(original_error=exception)
    
    elif isinstance(exception, (ConnectionError, ConnectionRefusedError, ConnectionResetError)):
        return LLMConnectionError(original_error=exception)
    
    elif isinstance(exception, requests.RequestException):
        # Handle request exceptions from requests library
        if exception.response:
            # If we have a response, use that to determine the error type
            return LLMAPIError.from_response(exception.response, original_error=exception)
        elif isinstance(exception, requests.Timeout):
            return LLMTimeoutError(original_error=exception)
        elif isinstance(exception, requests.ConnectionError):
            return LLMConnectionError(original_error=exception)
        
    # For any other exception types, wrap in the base class
    return LLMAPIError(
        message=str(exception),
        original_error=exception
    ) 