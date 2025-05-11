"""
Error detection and classification for Google Generative AI API calls.

This module provides functions to analyze responses from Google's Generative AI API,
detect error conditions, and classify them into appropriate exception types defined
in the exceptions module.
"""

import json
import re
import logging
from typing import Any, Dict, Optional, Union, Tuple, Type

import google.api_core.exceptions
import google.generativeai as genai

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
    map_exception_to_llm_error
)

# Configure logging
logger = logging.getLogger(__name__)


def extract_request_id(response: Any) -> Optional[str]:
    """
    Extract the request ID from a Google API response if available.
    
    Args:
        response: The API response object
        
    Returns:
        The request ID string or None if not found
    """
    # Check if it's a standard HTTP response with headers
    if hasattr(response, 'headers'):
        # Google API often includes request IDs in headers
        for header_name in ['x-request-id', 'x-goog-request-id', 'request-id']:
            if header_name in response.headers:
                return response.headers[header_name]
    
    # Check if it's a JSON response with data
    if hasattr(response, 'json') and callable(response.json):
        try:
            data = response.json()
            # Check common locations for request IDs in Google API responses
            if isinstance(data, dict):
                for field in ['requestId', 'request_id', 'metadata.requestId', 'id']:
                    parts = field.split('.')
                    value = data
                    for part in parts:
                        if isinstance(value, dict) and part in value:
                            value = value[part]
                        else:
                            value = None
                            break
                    if value and isinstance(value, str):
                        return value
        except (ValueError, TypeError, AttributeError):
            pass
    
    # Check if it's a Google API Core HttpRequest
    if hasattr(response, 'request') and hasattr(response.request, 'request_id'):
        return response.request.request_id
    
    return None


def extract_error_details(response: Any) -> Tuple[Optional[int], Optional[str], Dict[str, Any]]:
    """
    Extract error details from a response object.
    
    Args:
        response: The API response object
        
    Returns:
        A tuple of (status_code, error_message, additional_data)
    """
    status_code = None
    error_message = None
    additional_data = {}
    
    # Extract status code
    if hasattr(response, 'status_code'):
        status_code = response.status_code
    elif hasattr(response, 'code'):
        status_code = response.code
    
    # Extract error message and data from response
    if hasattr(response, 'json') and callable(response.json):
        try:
            data = response.json()
            additional_data = data
            
            # Handle Google API error format
            if isinstance(data, dict):
                # Extract from standard Google API error format
                if 'error' in data:
                    error_data = data['error']
                    if isinstance(error_data, dict):
                        if 'message' in error_data:
                            error_message = error_data['message']
                        if 'status' in error_data and not status_code:
                            # Sometimes status is a string code like "INVALID_ARGUMENT"
                            error_status = error_data['status']
                            if isinstance(error_status, int):
                                status_code = error_status
                    elif isinstance(error_data, str):
                        error_message = error_data
                
                # Extract from other common error formats
                elif 'message' in data:
                    error_message = data['message']
                elif 'description' in data:
                    error_message = data['description']
        except (ValueError, TypeError):
            pass
    
    # If we still don't have an error message, try some other common attributes
    if not error_message:
        if hasattr(response, 'text'):
            try:
                # Try parsing as JSON first
                data = json.loads(response.text)
                if 'error' in data and 'message' in data['error']:
                    error_message = data['error']['message']
                elif 'message' in data:
                    error_message = data['message']
                else:
                    # Use the full text as error message
                    error_message = response.text
            except (ValueError, TypeError, json.JSONDecodeError):
                # Not JSON, use the raw text
                error_message = response.text
        elif hasattr(response, 'reason'):
            error_message = str(response.reason)
        elif hasattr(response, 'message'):
            error_message = response.message
        elif isinstance(response, Exception):
            error_message = str(response)
    
    return status_code, error_message, additional_data


def detect_rate_limit_error(status_code: Optional[int], error_message: Optional[str]) -> bool:
    """
    Detect if an error is related to rate limiting.
    
    Args:
        status_code: The HTTP status code
        error_message: The error message string
        
    Returns:
        True if the error appears to be a rate limit error
    """
    # Check status code first (most reliable)
    if status_code == 429:
        return True
    
    # Check for common rate limit error messages
    if error_message:
        rate_limit_patterns = [
            r'rate\s+limit',
            r'quota\s+exceeded',
            r'too\s+many\s+requests',
            r'resource\s+exhausted',
            r'try\s+again\s+later',
            r'throttl'
        ]
        for pattern in rate_limit_patterns:
            if re.search(pattern, error_message, re.IGNORECASE):
                return True
    
    return False


def detect_authentication_error(status_code: Optional[int], error_message: Optional[str]) -> bool:
    """
    Detect if an error is related to authentication.
    
    Args:
        status_code: The HTTP status code
        error_message: The error message string
        
    Returns:
        True if the error appears to be an authentication error
    """
    # Check status code first
    if status_code in (401, 403):
        return True
    
    # Check for common authentication error messages
    if error_message:
        auth_patterns = [
            r'auth',
            r'unauthorized',
            r'unauthenticated',
            r'forbidden',
            r'invalid.*key',
            r'invalid.*token',
            r'permission.*denied',
            r'access.*denied'
        ]
        for pattern in auth_patterns:
            if re.search(pattern, error_message, re.IGNORECASE):
                return True
    
    return False


def detect_invalid_request_error(status_code: Optional[int], error_message: Optional[str]) -> bool:
    """
    Detect if an error is related to an invalid request.
    
    Args:
        status_code: The HTTP status code
        error_message: The error message string
        
    Returns:
        True if the error appears to be an invalid request error
    """
    # Check status code first
    if status_code in (400, 404, 405, 406, 411, 413, 414, 415, 422):
        return True
    
    # Check for common invalid request error messages
    if error_message:
        invalid_patterns = [
            r'invalid',
            r'bad\s+request',
            r'missing\s+parameter',
            r'malformed',
            r'not\s+found',
            r'unsupported',
            r'validation\s+failed',
            r'incorrect\s+format'
        ]
        for pattern in invalid_patterns:
            if re.search(pattern, error_message, re.IGNORECASE):
                return True
    
    return False


def detect_service_unavailable_error(status_code: Optional[int], error_message: Optional[str]) -> bool:
    """
    Detect if an error is related to service unavailability.
    
    Args:
        status_code: The HTTP status code
        error_message: The error message string
        
    Returns:
        True if the error appears to be a service unavailability error
    """
    # Check status code first
    if status_code in (502, 503, 504):
        return True
    
    # Check for common service unavailable error messages
    if error_message:
        unavailable_patterns = [
            r'unavailable',
            r'down',
            r'maintenance',
            r'temporarily\s+offline',
            r'overloaded',
            r'timeout',
            r'gateway',
            r'bad\s+gateway'
        ]
        for pattern in unavailable_patterns:
            if re.search(pattern, error_message, re.IGNORECASE):
                return True
    
    return False


def classify_google_api_exception(exception: Exception) -> LLMAPIError:
    """
    Classify a Google API exception into our custom exception hierarchy.
    
    Args:
        exception: A Google API exception
        
    Returns:
        An instance of the appropriate LLMAPIError subclass
    """
    if isinstance(exception, google.api_core.exceptions.TooManyRequests):
        return LLMRateLimitError(
            message=str(exception),
            original_error=exception
        )
    elif isinstance(exception, google.api_core.exceptions.Unauthenticated):
        return LLMAuthenticationError(
            message=str(exception),
            original_error=exception
        )
    elif isinstance(exception, google.api_core.exceptions.PermissionDenied):
        return LLMAuthenticationError(
            message=str(exception),
            original_error=exception
        )
    elif isinstance(exception, google.api_core.exceptions.InvalidArgument):
        return LLMInvalidRequestError(
            message=str(exception),
            original_error=exception
        )
    elif isinstance(exception, google.api_core.exceptions.NotFound):
        return LLMInvalidRequestError(
            message=str(exception),
            original_error=exception
        )
    elif isinstance(exception, google.api_core.exceptions.Aborted):
        return LLMAPIError(
            message=str(exception),
            original_error=exception
        )
    elif isinstance(exception, google.api_core.exceptions.DeadlineExceeded):
        return LLMTimeoutError(
            message=str(exception),
            original_error=exception
        )
    elif isinstance(exception, google.api_core.exceptions.ServiceUnavailable):
        return LLMServiceUnavailableError(
            message=str(exception),
            original_error=exception
        )
    elif isinstance(exception, google.api_core.exceptions.InternalServerError):
        return LLMInternalError(
            message=str(exception),
            original_error=exception
        )
    elif isinstance(exception, google.api_core.exceptions.ResourceExhausted):
        return LLMRateLimitError(
            message=str(exception),
            original_error=exception
        )
    else:
        # For all other Google API exceptions, use the base class
        return LLMAPIError(
            message=str(exception),
            original_error=exception
        )


def classify_error(response_or_exception: Any) -> LLMAPIError:
    """
    Classify a response or exception into the appropriate LLMAPIError subclass.
    
    This is the main entry point for error classification.
    
    Args:
        response_or_exception: An API response or exception
        
    Returns:
        An instance of the appropriate LLMAPIError subclass
    """
    # First, handle Google API exceptions directly
    if isinstance(response_or_exception, google.api_core.exceptions.GoogleAPIError):
        return classify_google_api_exception(response_or_exception)
    
    # Then, handle standard Python exceptions
    if isinstance(response_or_exception, Exception) and not hasattr(response_or_exception, 'status_code'):
        return map_exception_to_llm_error(response_or_exception)
    
    # For response objects or exception objects with response data, extract the details
    request_id = extract_request_id(response_or_exception)
    status_code, error_message, additional_data = extract_error_details(response_or_exception)
    
    # Create kwargs for the exception
    exception_kwargs = {
        'status_code': status_code,
        'message': error_message or "Unknown error",
        'request_id': request_id,
        'response_data': additional_data,
        'original_error': response_or_exception if isinstance(response_or_exception, Exception) else None
    }
    
    # Classify based on the extracted details
    if status_code:
        # Use status code for primary classification
        if 400 <= status_code < 500:
            if detect_authentication_error(status_code, error_message):
                return LLMAuthenticationError(**exception_kwargs)
            elif detect_rate_limit_error(status_code, error_message):
                return LLMRateLimitError(**exception_kwargs)
            else:
                return LLMInvalidRequestError(**exception_kwargs)
        elif 500 <= status_code < 600:
            if detect_service_unavailable_error(status_code, error_message):
                return LLMServiceUnavailableError(**exception_kwargs)
            else:
                return LLMInternalError(**exception_kwargs)
    else:
        # No status code, use message patterns for classification
        if detect_authentication_error(None, error_message):
            return LLMAuthenticationError(**exception_kwargs)
        elif detect_rate_limit_error(None, error_message):
            return LLMRateLimitError(**exception_kwargs)
        elif detect_invalid_request_error(None, error_message):
            return LLMInvalidRequestError(**exception_kwargs)
        elif detect_service_unavailable_error(None, error_message):
            return LLMServiceUnavailableError(**exception_kwargs)
    
    # If we couldn't classify it more specifically, return a generic LLMAPIError
    return LLMAPIError(**exception_kwargs) 