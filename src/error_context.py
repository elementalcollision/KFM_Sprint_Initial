"""
Enhanced error context for LangGraph workflow.

This module provides utilities for enhancing error handling with detailed
contextual information, state snapshots, and error classification to aid
in debugging and analysis of failures in LangGraph applications.
"""

import re
import sys
import types
import inspect
import logging
import traceback
import datetime
import uuid
import json
import os
from typing import Dict, Any, Optional, List, Callable, Type, Union, Tuple, Set
from collections import defaultdict
from functools import wraps

from src.logger import setup_logger
from src.core.state import KFMAgentState

# Setup logger for the error context module
error_logger = setup_logger('src.error_context')

# Define error severity levels
ERROR_SEVERITY = {
    "CRITICAL": 50,  # System-level or unrecoverable errors
    "ERROR": 40,     # Application logic errors
    "WARNING": 30,   # Potential issues that don't prevent execution
    "INFO": 20,      # Informational errors
    "DEBUG": 10      # Development-only errors
}

# Define error categories
ERROR_CATEGORIES = {
    "GRAPH_EXECUTION": "Errors in graph execution flow",
    "STATE_VALIDATION": "Errors in state validation or schema",
    "API_INTEGRATION": "Errors in external API calls",
    "USER_INPUT": "Errors related to user input",
    "CONFIGURATION": "Errors in configuration or settings",
    "RESOURCE": "Errors related to resource availability",
    "TIMEOUT": "Errors related to timeouts",
    "UNEXPECTED": "Unexpected or unclassified errors",
    "PERMISSION": "Errors related to permissions or access",
    "DATA_FORMAT": "Errors in data formatting or parsing"
}

# Error code format: E[CATEGORY_CODE][SEVERITY_CODE][3-DIGIT_ERROR_CODE]
# Example: E0140001 = Graph execution (01) error (40) code 001

# Define error code ranges
ERROR_CATEGORY_CODES = {
    "GRAPH_EXECUTION": "01",
    "STATE_VALIDATION": "02",
    "API_INTEGRATION": "03",
    "USER_INPUT": "04",
    "CONFIGURATION": "05",
    "RESOURCE": "06",
    "TIMEOUT": "07",
    "UNEXPECTED": "08",
    "PERMISSION": "09",
    "DATA_FORMAT": "10"
}

# Global registry to track error patterns
_error_registry = {}
_error_statistics = defaultdict(int)
_similar_errors = defaultdict(list)

# Error snapshot directory
ERROR_SNAPSHOT_DIR = "logs/error_snapshots"

# Ensure error snapshot directory exists
os.makedirs(ERROR_SNAPSHOT_DIR, exist_ok=True)

class EnhancedError(Exception):
    """
    Enhanced error class with rich contextual information.
    
    This exception type includes:
    - Detailed error messages
    - Error classification (category, severity)
    - Error code
    - Execution context
    - State snapshots
    - Timestamps
    """
    
    def __init__(self, 
                message: str, 
                original_error: Optional[Exception] = None,
                category: str = "UNEXPECTED",
                severity: str = "ERROR",
                error_code: Optional[str] = None,
                context: Optional[Dict[str, Any]] = None,
                state: Optional[Dict[str, Any]] = None,
                node_name: Optional[str] = None):
        """
        Initialize the enhanced error.
        
        Args:
            message: Human-readable error message
            original_error: The original exception that triggered this error
            category: Error category (from ERROR_CATEGORIES)
            severity: Error severity (from ERROR_SEVERITY)
            error_code: Optional specific error code
            context: Additional context information
            state: State at the time of the error
            node_name: Name of the node where the error occurred
        """
        self.message = message
        self.original_error = original_error
        
        # Validate and set category
        if category not in ERROR_CATEGORIES:
            category = "UNEXPECTED"
        self.category = category
        
        # Validate and set severity
        if severity not in ERROR_SEVERITY:
            severity = "ERROR"
        self.severity = severity
        
        # Generate or validate error code
        if error_code is None:
            self.error_code = generate_error_code(category, severity)
        else:
            self.error_code = error_code
        
        # Set metadata
        self.timestamp = datetime.datetime.now().isoformat()
        self.uid = str(uuid.uuid4())
        self.context = context or {}
        self.state_snapshot_id = None
        self.state = state
        self.node_name = node_name
        self.traceback = None
        
        # Capture traceback
        if original_error:
            self.traceback = traceback.format_exception(
                type(original_error), 
                original_error, 
                original_error.__traceback__
            )
        else:
            try:
                # Create a new traceback without this constructor
                frame = sys._getframe(1)
                tb = types.TracebackType(None, frame, frame.f_lasti, frame.f_lineno)
                self.traceback = traceback.format_tb(tb)
            except Exception:
                # Fall back to current traceback if there's an issue
                self.traceback = traceback.format_exc().splitlines()
        
        # If state is provided, create a snapshot
        if state:
            try:
                # Import at runtime to avoid circular imports
                from src.tracing import save_state_snapshot
                
                snapshot_label = f"Error_{self.error_code}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
                self.state_snapshot_id = save_state_snapshot(
                    state=state,
                    label=snapshot_label,
                    category="error",
                    description=f"State at error: {message}"
                )
                self.context["state_snapshot_id"] = self.state_snapshot_id
            except Exception as e:
                error_logger.warning(f"Failed to create state snapshot: {e}")
        
        # Register this error for pattern recognition
        register_error(self)
        
        # Call the parent constructor
        super().__init__(self.formatted_message())
    
    def formatted_message(self) -> str:
        """
        Create a detailed formatted error message.
        
        Returns:
            Formatted error message with contextual information
        """
        lines = [
            f"[{self.error_code}] {self.category} ({self.severity}): {self.message}",
        ]
        
        # Add original error details if available
        if self.original_error:
            lines.append(f"Original error: {type(self.original_error).__name__}: {str(self.original_error)}")
        
        # Add node information if available
        if self.node_name:
            lines.append(f"Node: {self.node_name}")
        
        # Add timestamp
        lines.append(f"Time: {self.timestamp}")
        
        # Add snapshot reference if available
        if self.state_snapshot_id:
            lines.append(f"State snapshot ID: {self.state_snapshot_id}")
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the enhanced error to a dictionary.
        
        Returns:
            Dictionary representation of the error
        """
        error_dict = {
            "error_code": self.error_code,
            "category": self.category,
            "severity": self.severity,
            "message": self.message,
            "timestamp": self.timestamp,
            "uid": self.uid,
            "node_name": self.node_name,
            "context": self.context,
            "state_snapshot_id": self.state_snapshot_id
        }
        
        # Add original error details if available
        if self.original_error:
            error_dict["original_error"] = {
                "type": type(self.original_error).__name__,
                "message": str(self.original_error)
            }
        
        # Add traceback if available
        if self.traceback:
            error_dict["traceback"] = self.traceback
        
        return error_dict
    
    def to_json(self, indent: Optional[int] = None) -> str:
        """
        Convert the enhanced error to a JSON string.
        
        Args:
            indent: Optional indentation level for JSON formatting
            
        Returns:
            JSON string representation of the error
        """
        return json.dumps(self.to_dict(), indent=indent, default=str)
    
    def save_to_file(self, directory: Optional[str] = None) -> str:
        """
        Save the error details to a file.
        
        Args:
            directory: Directory to save the error file (defaults to ERROR_SNAPSHOT_DIR)
            
        Returns:
            Path to the saved file
        """
        if directory is None:
            directory = ERROR_SNAPSHOT_DIR
        
        # Create directory if it doesn't exist
        os.makedirs(directory, exist_ok=True)
        
        # Create filename based on error code and timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"error_{self.error_code}_{timestamp}.json"
        filepath = os.path.join(directory, filename)
        
        # Write error details to file
        with open(filepath, 'w') as f:
            f.write(self.to_json(indent=2))
        
        return filepath
    
    def log(self) -> None:
        """
        Log the error with the appropriate severity level.
        """
        # Convert severity to logging level
        log_level = {
            "CRITICAL": logging.CRITICAL,
            "ERROR": logging.ERROR,
            "WARNING": logging.WARNING,
            "INFO": logging.INFO,
            "DEBUG": logging.DEBUG
        }.get(self.severity, logging.ERROR)
        
        # Log the error with appropriate level
        error_logger.log(log_level, self.formatted_message())
        
        # Log stacktrace at DEBUG level
        if self.traceback:
            error_logger.debug("Traceback:\n" + "".join(self.traceback))

def generate_error_code(category: str, severity: str, specific_code: Optional[int] = None) -> str:
    """
    Generate a structured error code.
    
    Format: E[CATEGORY_CODE][SEVERITY_CODE][3-DIGIT_ERROR_CODE]
    Example: E0140001
    
    Args:
        category: Error category
        severity: Error severity
        specific_code: Optional specific error code number
        
    Returns:
        Formatted error code
    """
    # Get category code
    category_code = ERROR_CATEGORY_CODES.get(category, "08")  # Default to UNEXPECTED
    
    # Get severity code
    severity_code = str(ERROR_SEVERITY.get(severity, 40))  # Default to ERROR
    
    # Generate specific code if not provided
    if specific_code is None:
        # Get current count of errors in this category/severity
        key = f"{category}_{severity}"
        _error_statistics[key] += 1
        specific_code = _error_statistics[key]
    
    # Ensure 3 digits with leading zeros
    specific_code_str = f"{specific_code:03d}"
    
    # Combine all parts
    return f"E{category_code}{severity_code}{specific_code_str}"

def register_error(error: EnhancedError) -> None:
    """
    Register an error in the global registry for pattern recognition.
    
    Args:
        error: The enhanced error to register
    """
    # Add to registry
    _error_registry[error.uid] = error
    
    # Update statistics
    _error_statistics[error.category] += 1
    _error_statistics[error.severity] += 1
    _error_statistics[error.error_code] += 1
    
    # Check for similar errors based on message similarity
    for uid, existing_error in _error_registry.items():
        if uid != error.uid and is_similar_error(error, existing_error):
            _similar_errors[error.error_code].append(existing_error.uid)
            _similar_errors[existing_error.error_code].append(error.uid)

def is_similar_error(error1: EnhancedError, error2: EnhancedError) -> bool:
    """
    Check if two errors are similar based on message and context.
    
    Args:
        error1: First error
        error2: Second error
        
    Returns:
        True if errors are similar, False otherwise
    """
    # Same category is a strong indicator
    if error1.category == error2.category:
        # If both have node names and they match, that's a very strong indicator
        if error1.node_name and error2.node_name and error1.node_name == error2.node_name:
            return True
            
        # Check for similar messages (ignoring variable parts)
        msg1 = normalize_error_message(error1.message)
        msg2 = normalize_error_message(error2.message)
        
        # If normalized messages match, they're similar
        if msg1 == msg2:
            return True
        
        # If messages are similar enough (contains same keywords)
        # This helps catch errors with different variable parts but same root cause
        if len(msg1) > 5 and len(msg2) > 5:  # Avoid matching very short messages
            common_words = set(msg1.split()) & set(msg2.split())
            if len(common_words) >= 2:  # At least 2 common words
                return True
    
    return False

def normalize_error_message(message: str) -> str:
    """
    Normalize an error message by removing variable parts.
    
    Args:
        message: Error message to normalize
        
    Returns:
        Normalized message
    """
    # Handle file paths first before number replacement to avoid multiple PATH placeholders
    normalized = re.sub(r'(?:/|\\)[^\s/\\]+(?:/[^\s/\\]+)*', 'PATH', message)
    
    # Replace numbers, UUIDs, timestamps with placeholders
    normalized = re.sub(r'\d+', 'NUM', normalized)
    normalized = re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', 'UUID', normalized)
    
    # Handle ISO format timestamps (YYYY-MM-DDThh:mm:ss)
    normalized = re.sub(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', 'TIMESTAMP', normalized)
    
    # Also handle timestamps that were already partially normalized
    normalized = re.sub(r'NUM-NUM-NUMTNUM:NUM:NUM', 'TIMESTAMP', normalized)
    
    return normalized

def get_error_statistics() -> Dict[str, Any]:
    """
    Get statistics about recorded errors.
    
    Returns:
        Dictionary with error statistics
    """
    # Prepare statistics report
    stats = {
        "total_errors": sum(count for key, count in _error_statistics.items()
                       if key not in list(ERROR_CATEGORIES.keys()) + list(ERROR_SEVERITY.keys())),
        "by_category": {category: _error_statistics[category] for category in ERROR_CATEGORIES},
        "by_severity": {severity: _error_statistics[severity] for severity in ERROR_SEVERITY},
        "error_codes": {code: count for code, count in _error_statistics.items() 
                       if code.startswith('E')}
    }
    
    return stats

def get_recent_errors(count: int = 10) -> List[Dict[str, Any]]:
    """
    Get the most recent errors.
    
    Args:
        count: Number of recent errors to return
        
    Returns:
        List of recent errors as dictionaries
    """
    # Convert registry to list and sort by timestamp (newest first)
    errors = list(_error_registry.values())
    errors.sort(key=lambda e: e.timestamp, reverse=True)
    
    # Return the most recent errors
    return [error.to_dict() for error in errors[:count]]

def get_similar_errors(error_code: str) -> List[Dict[str, Any]]:
    """
    Get errors similar to the specified error code.
    
    Args:
        error_code: Error code to find similar errors for
        
    Returns:
        List of similar errors as dictionaries
    """
    similar = []
    
    # Get UIDs of similar errors
    similar_uids = _similar_errors.get(error_code, [])
    
    # Convert to error dictionaries
    for uid in similar_uids:
        if uid in _error_registry:
            similar.append(_error_registry[uid].to_dict())
    
    return similar

def clear_error_registry() -> None:
    """
    Clear the error registry.
    """
    global _error_registry, _error_statistics, _similar_errors
    _error_registry = {}
    _error_statistics = defaultdict(int)
    _similar_errors = defaultdict(list)

def with_enhanced_error(category: str, severity: str = "ERROR", 
                      include_state: bool = True) -> Callable:
    """
    Decorator to enhance functions with detailed error handling.
    
    Args:
        category: Error category
        severity: Error severity
        include_state: Whether to include state in error context
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                # Extract state from arguments if available
                state = None
                node_name = func.__name__
                
                # Check if first argument is state
                if args and (isinstance(args[0], dict) or hasattr(args[0], 'to_dict')):
                    if hasattr(args[0], 'to_dict'):
                        state = args[0].to_dict()
                    else:
                        state = args[0].copy()  # For TypedDict
                
                # Execute the function
                return func(*args, **kwargs)
                
            except EnhancedError:
                # If already an EnhancedError, re-raise
                raise
                
            except Exception as e:
                # Get context information
                context = {
                    "function": func.__name__,
                    "arguments": str({
                        "args": [str(arg)[:100] for arg in args],
                        "kwargs": {k: str(v)[:100] for k, v in kwargs.items()}
                    }),
                    "module": func.__module__
                }
                
                # Create message from exception
                message = str(e) or f"Error in {func.__name__}"
                
                # Create enhanced error
                enhanced_error = EnhancedError(
                    message=message,
                    original_error=e,
                    category=category,
                    severity=severity,
                    context=context,
                    state=state if include_state else None,
                    node_name=node_name
                )
                
                # Log the enhanced error
                enhanced_error.log()
                
                # Save error details to file
                enhanced_error.save_to_file()
                
                # Re-raise as EnhancedError
                raise enhanced_error from e
                
        return wrapper
    
    return decorator

def capture_error_context(error: Exception, 
                        state: Optional[Dict[str, Any]] = None,
                        node_name: Optional[str] = None,
                        category: str = "UNEXPECTED",
                        severity: str = "ERROR") -> EnhancedError:
    """
    Capture error context to create an EnhancedError from a regular exception.
    
    Args:
        error: The original exception
        state: State at the time of the error
        node_name: Name of the node where the error occurred
        category: Error category
        severity: Error severity
        
    Returns:
        Enhanced error with context
    """
    # Get additional context from trace history if available
    context = {}
    
    try:
        # Import at runtime to avoid circular imports
        from src.tracing import get_trace_history
        
        trace_history = get_trace_history()
        if trace_history:
            # Find the most recent error in trace history
            for entry in reversed(trace_history):
                if not entry.get("success", True) and entry.get("error"):
                    context["trace_entry"] = {
                        "node": entry.get("node"),
                        "timestamp": entry.get("timestamp"),
                        "error": entry.get("error")
                    }
                    break
    except ImportError:
        error_logger.debug("Could not import trace_history - continuing without trace context")
    
    # Add call stack information
    stack = inspect.stack()
    if len(stack) > 1:
        caller = stack[1]
        context["caller"] = {
            "function": caller.function,
            "filename": caller.filename,
            "lineno": caller.lineno
        }
    
    # Create enhanced error
    message = str(error) or "Unknown error"
    enhanced_error = EnhancedError(
        message=message,
        original_error=error,
        category=category,
        severity=severity,
        context=context,
        state=state,
        node_name=node_name
    )
    
    # Log the enhanced error
    enhanced_error.log()
    
    # Save error details to file
    enhanced_error.save_to_file()
    
    return enhanced_error

def analyze_error_patterns() -> Dict[str, Any]:
    """
    Analyze patterns in the error registry to identify common issues.
    
    Returns:
        Dictionary with analysis results
    """
    # Prepare analysis report
    analysis = {
        "frequent_errors": [],
        "error_clusters": [],
        "recent_patterns": []
    }
    
    # Find frequent errors (top 5)
    error_counts = defaultdict(int)
    for error in _error_registry.values():
        normalized_msg = normalize_error_message(error.message)
        error_counts[f"{error.category}:{normalized_msg}"] += 1
    
    # Sort by count and get top 5
    frequent = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    for key, count in frequent:
        category, message = key.split(':', 1)
        analysis["frequent_errors"].append({
            "category": category,
            "message_pattern": message,
            "count": count
        })
    
    # Find error clusters based on similar errors
    cluster_counts = {code: len(uids) for code, uids in _similar_errors.items()}
    top_clusters = sorted(cluster_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    
    for code, count in top_clusters:
        if code in _error_registry:
            representative = _error_registry[code]
            analysis["error_clusters"].append({
                "error_code": code,
                "category": representative.category,
                "message_pattern": normalize_error_message(representative.message),
                "similar_errors_count": count
            })
    
    # Analyze recent errors for emerging patterns
    recent_errors = list(_error_registry.values())
    recent_errors.sort(key=lambda e: e.timestamp, reverse=True)
    recent_errors = recent_errors[:20]  # Look at 20 most recent errors
    
    # Count categories in recent errors
    recent_categories = defaultdict(int)
    for error in recent_errors:
        recent_categories[error.category] += 1
    
    # Add to analysis
    for category, count in recent_categories.items():
        if count >= 3:  # If 3 or more recent errors in the same category
            analysis["recent_patterns"].append({
                "category": category,
                "count": count,
                "description": f"Recent increase in {category} errors"
            })
    
    return analysis

def get_error_suggestions(error: Union[EnhancedError, str]) -> Dict[str, Any]:
    """
    Get suggestions for resolving an error.
    
    Args:
        error: EnhancedError object or error code
        
    Returns:
        Dictionary with suggestions
    """
    # Check if we have an imported get_suggestions function
    # Use a safer import approach to avoid circular imports
    suggestions_module = sys.modules.get('src.suggestions')
    if suggestions_module and hasattr(suggestions_module, 'get_suggestions'):
        # Use the already imported function
        suggestions_func = getattr(suggestions_module, 'get_suggestions')
        error_logger.debug("Using advanced suggestions engine")
        return suggestions_func(error)
    
    # If advanced engine not available, use basic suggestions
    error_logger.debug("Using basic suggestions engine")
    
    # If string provided, try to find the error
    if isinstance(error, str):
        # Check if it's an error code or UID
        for uid, err in _error_registry.items():
            if uid == error or err.error_code == error:
                error = err
                break
        
        # If still a string, return empty suggestions
        if isinstance(error, str):
            return {
                "error": f"Error not found: {error}",
                "suggestions": []
            }
    
    # Prepare suggestions based on category
    suggestions = []
    
    # Common suggestions based on category
    category_suggestions = {
        "GRAPH_EXECUTION": [
            "Check for proper node connectivity in the graph",
            "Verify that state is properly flowing between nodes",
            "Check for cycles or termination conditions"
        ],
        "STATE_VALIDATION": [
            "Check the expected schema of the state",
            "Verify that required fields are present",
            "Check for type mismatches in state fields"
        ],
        "API_INTEGRATION": [
            "Verify API credentials and permissions",
            "Check network connectivity",
            "Validate request format and parameters"
        ],
        "USER_INPUT": [
            "Validate user input before processing",
            "Add input sanitization",
            "Provide clearer error messages to users"
        ],
        "CONFIGURATION": [
            "Check configuration files for correctness",
            "Verify environment variables are set",
            "Ensure configuration matches expected schema"
        ],
        "RESOURCE": [
            "Check for sufficient memory and CPU",
            "Verify file system permissions",
            "Check for available disk space"
        ],
        "TIMEOUT": [
            "Increase timeout thresholds if appropriate",
            "Optimize operations to reduce execution time",
            "Add retry logic with backoff"
        ],
        "PERMISSION": [
            "Check user or service account permissions",
            "Verify file system access rights",
            "Ensure proper authentication is in place"
        ],
        "DATA_FORMAT": [
            "Check for proper JSON/data format",
            "Validate data types match the expected schema",
            "Handle edge cases in data formatting"
        ]
    }
    
    # Add category-based suggestions
    if error.category in category_suggestions:
        suggestions.extend(category_suggestions[error.category])
    
    # Add specific suggestions based on error code or patterns
    if error.original_error:
        error_type = type(error.original_error).__name__
        if error_type == "KeyError":
            suggestions.append("Check if the required key exists in the dictionary")
            suggestions.append("Add defensive checks before accessing dictionary keys")
        elif error_type == "TypeError":
            suggestions.append("Verify that objects are of the expected types")
            suggestions.append("Add type checking before operations")
        elif error_type == "ValueError":
            suggestions.append("Validate input values before processing")
        elif error_type == "AttributeError":
            suggestions.append("Ensure the object has the expected attributes or methods")
            suggestions.append("Check for None or uninitialized objects")
    
    # Look for similar errors and their resolutions
    similar_errors = get_similar_errors(error.error_code)
    if similar_errors:
        suggestions.append(f"Check for similar errors (found {len(similar_errors)} similar issues)")
    
    # Create response
    response = {
        "error_code": error.error_code,
        "category": error.category,
        "message": error.message,
        "suggestions": suggestions,
        "similar_errors_count": len(similar_errors)
    }
    
    return response
