"""
State tracking and tracing utilities for LangGraph workflow.

This module provides functions and decorators for tracing state changes
through the LangGraph execution flow, to ensure data properly flows
between nodes and to aid in debugging.
"""

import logging
import time
import inspect
import functools
import json
import traceback
import os
import uuid
import datetime
from collections import deque
from typing import Dict, Any, Callable, Optional, List, Set, Union, Tuple, TypeVar, Deque
from src.logger import setup_logger, set_log_level, get_log_level
from src.core.state import KFMAgentState

# Import profiling utilities
from src.profiling import get_profiler, start_profiling_run, end_profiling_run

# Import visualization module for reports and visualizations
try:
    from src.visualization import visualize_timeline, visualize_state_changes, create_execution_report
except ImportError:
    # Create placeholder functions if visualization module is not available
    def visualize_timeline(*args, **kwargs): return None
    def visualize_state_changes(*args, **kwargs): return None
    def create_execution_report(*args, **kwargs): return None

# Add visualize_trace_path function to fix import error in kfm_agent.py
def visualize_trace_path(trace_history=None, output_format='text', include_states=False, max_state_depth=2):
    """
    Visualize the execution trace path.
    
    Args:
        trace_history: The trace history to visualize (defaults to current trace history)
        output_format: Output format ('text', 'mermaid', 'dot')
        include_states: Whether to include state details in the visualization
        max_state_depth: Maximum depth for state rendering
        
    Returns:
        str: Visualization of the trace path in the specified format
    """
    if trace_history is None:
        trace_history = get_trace_history()
    
    if not trace_history:
        return "No trace history available."
    
    # Return a simple text representation for now
    lines = ["Execution Trace Path:"]
    for i, entry in enumerate(trace_history):
        node_name = entry.get('node', 'unknown')
        timestamp = entry.get('timestamp', 'unknown')
        lines.append(f"{i+1}. {node_name} @ {timestamp}")
    
    return "\n".join(lines)

# Setup logger for the tracing module
trace_logger = setup_logger('src.tracing')

# Global trace configuration
_trace_enabled = True  # Default to enabled
_trace_history = []

# Fields that should be filtered out of state logs
_filtered_keys = []

# State history tracker
_state_history_tracker = None

# Enable/disable profiling
_enable_profiling = True

# Current trace session ID
_current_trace_session = None

# Correlation ID for tracking execution flow
_current_correlation_id = None

# Node execution count within the current trace session
_node_execution_count = 0

# Dictionary to track node type information
_node_type_info = {}

def configure_tracing(log_level: Optional[Union[str, int]] = None, 
                     filter_keys: Optional[List[str]] = None,
                     history_buffer_size: int = 100,
                     enable_profiling: bool = True,
                     compiled_graph = None) -> None:
    """
    Configure the tracing system.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR) or corresponding integer
        filter_keys: State keys to filter from logs
        history_buffer_size: Size of state history buffer
        enable_profiling: Whether to enable performance profiling
        compiled_graph: Optional compiled graph to trace
    """
    global _filtered_keys, _state_history_tracker, _enable_profiling
    
    # Set logging level if provided
    if log_level is not None:
        # Handle different log level formats (string or int)
        if isinstance(log_level, str):
            level_value = getattr(logging, log_level.upper())
        else:
            level_value = log_level
            
        # Apply log level to tracing logger
        trace_logger.setLevel(level_value)
        trace_logger.info(f"Tracing log level set to {logging.getLevelName(level_value)}")
    
    # Set filtered keys if provided
    if filter_keys:
        _filtered_keys = filter_keys
        trace_logger.info(f"Tracing filter keys set: {filter_keys}")
    
    # Initialize state history tracker
    if _state_history_tracker is None:
        _state_history_tracker = StateHistoryTracker(max_size=history_buffer_size)
        trace_logger.info(f"State history tracker initialized with buffer size {history_buffer_size}")
    else:
        _state_history_tracker.reconfigure(max_size=history_buffer_size)
        trace_logger.info(f"State history tracker reconfigured with buffer size {history_buffer_size}")
    
    # Configure profiling
    _enable_profiling = enable_profiling
    if _enable_profiling:
        trace_logger.info("Performance profiling enabled")
    else:
        trace_logger.info("Performance profiling disabled")

def reset_trace_history() -> None:
    """
    Reset the trace history.
    """
    global _trace_history
    _trace_history = []
    trace_logger.debug("Trace history reset")
    
    # Also reset state history if available
    if _state_history_tracker:
        _state_history_tracker.clear()

def get_trace_history() -> List[Dict[str, Any]]:
    """
    Get the current trace history.
    
    Returns:
        List of trace history entries
    """
    return _trace_history

def save_trace_to_file(filepath: str, trace_history: Optional[List[Dict[str, Any]]] = None) -> bool:
    """
    Save the trace history to a file.
    
    Args:
        filepath: Path where to save the trace history
        trace_history: Trace history to save (default: current trace history)
        
    Returns:
        bool: True if the trace was successfully saved, False otherwise
    """
    if trace_history is None:
        trace_history = get_trace_history()
    
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(trace_history, f, indent=2, default=str)
        trace_logger.info(f"Trace history saved to {filepath}")
        return True
    except Exception as e:
        trace_logger.error(f"Failed to save trace history: {e}")
        return False

def get_state_history_tracker() -> 'StateHistoryTracker':
    """
    Get the state history tracker instance.
    
    Returns:
        StateHistoryTracker instance or None if not configured
    """
    global _state_history_tracker
    
    if _state_history_tracker is None:
        # Initialize with default settings if not configured
        _state_history_tracker = StateHistoryTracker()
        trace_logger.info("State history tracker initialized with default settings")
        
    return _state_history_tracker

def get_correlation_id() -> str:
    """
    Get the current correlation ID for linking logs.
    If none exists, generate a new one.
    
    Returns:
        Current correlation ID string
    """
    global _current_correlation_id
    
    if _current_correlation_id is None:
        _current_correlation_id = str(uuid.uuid4())
        
    return _current_correlation_id

def set_correlation_id(correlation_id: str) -> None:
    """
    Set the correlation ID for the current execution flow.
    
    Args:
        correlation_id: Correlation ID to set
    """
    global _current_correlation_id
    _current_correlation_id = correlation_id

def reset_correlation_id() -> None:
    """Reset the correlation ID to generate a new one on next request."""
    global _current_correlation_id
    _current_correlation_id = None

def get_trace_session() -> str:
    """
    Get the current trace session ID.
    If none exists, generate a new one.
    
    Returns:
        Current trace session ID string
    """
    global _current_trace_session
    
    if _current_trace_session is None:
        _current_trace_session = f"trace_{int(time.time())}"
        
    return _current_trace_session

def set_trace_session(session_id: str) -> None:
    """
    Set the trace session ID.
    
    Args:
        session_id: Session ID to set
    """
    global _current_trace_session
    _current_trace_session = session_id

def reset_trace_session() -> None:
    """Reset the trace session to generate a new one on next request."""
    global _current_trace_session
    _current_trace_session = None

def get_next_node_execution_id() -> int:
    """
    Get the next node execution count and increment the counter.
    
    Returns:
        Current node execution count
    """
    global _node_execution_count
    _node_execution_count += 1
    return _node_execution_count

def register_node_info(node_func: Callable, node_type: str = None, description: str = None) -> None:
    """
    Register additional information about a node function.
    
    Args:
        node_func: The node function
        node_type: Type of the node (e.g., 'action', 'decision', 'monitor')
        description: Human-readable description of the node's purpose
    """
    global _node_type_info
    
    node_name = node_func.__name__
    
    if node_type is None:
        # Try to infer node type from name
        if 'monitor' in node_name:
            node_type = 'monitor'
        elif 'decision' in node_name:
            node_type = 'decision'
        elif 'action' in node_name or 'execute' in node_name:
            node_type = 'action'
        elif 'reflect' in node_name:
            node_type = 'reflection'
        else:
            node_type = 'unknown'
    
    if description is None:
        # Use docstring as description if available
        if node_func.__doc__:
            # Extract first line of docstring
            description = node_func.__doc__.strip().split('\n')[0]
        else:
            description = f"{node_name} node"
    
    _node_type_info[node_name] = {
        'type': node_type,
        'description': description
    }
    
    trace_logger.debug(f"Registered node info for {node_name}: type={node_type}")

def get_node_type(node_name: str) -> Dict[str, str]:
    """
    Get type information for a node.
    
    Args:
        node_name: Name of the node
        
    Returns:
        Dictionary with node type information
    """
    global _node_type_info
    
    if node_name not in _node_type_info:
        # Default values for unregistered nodes
        return {
            'type': 'unknown',
            'description': f"{node_name} node"
        }
    
    return _node_type_info[node_name]

def trace_node(func):
    """
    Decorator to trace execution of a node function.
    
    Args:
        func (Callable): The node function to trace
        
    Returns:
        Callable: Wrapped function with tracing
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Skip tracing if disabled
        if not is_trace_enabled():
            return func(*args, **kwargs)
            
        # Get correlation ID or create a new one
        correlation_id = get_correlation_id()
        
        # Get function name
        node_name = func.__name__
        
        # Track execution counts
        global _node_execution_count
        _node_execution_count += 1
        execution_id = _node_execution_count
        
        # Log entry
        trace_logger.info(f"[corr:{correlation_id}] Entering node {node_name} (exec:{execution_id})")
        
        # Extract state from args if available (first argument is usually the state)
        input_state = None
        state_arg = None
        if args and hasattr(args[0], '__dict__'):
            state_arg = args[0]
            # Convert to dict for tracing
            if hasattr(state_arg, 'dict'):
                # Handle Pydantic models
                input_state = state_arg.dict()
            elif hasattr(state_arg, '__dict__'):
                # Handle regular objects
                input_state = state_arg.__dict__
        
        # Track timing
        start_time = time.time()
        start_timestamp = datetime.datetime.now().isoformat()
        
        # Create trace entry
        trace_entry = {
            "node": node_name,
            "timestamp": start_time,
            "start_timestamp": start_timestamp,
            "correlation_id": correlation_id,
            "execution_id": execution_id,
            "input_state": _extract_key_fields(input_state) if input_state else None
        }
        
        # Execute function
        success = True
        error = None
        output_state = None
        state_changes = {}
        
        try:
            # Execute the node function
            result = func(*args, **kwargs)
            
            # Extract output state if result is a state object
            if hasattr(result, '__dict__'):
                if hasattr(result, 'dict'):
                    # Handle Pydantic models
                    output_state = result.dict()
                elif hasattr(result, '__dict__'):
                    # Handle regular objects
                    output_state = result.__dict__
                    
                # Identify state changes
                if input_state and output_state:
                    state_changes = _identify_state_changes(input_state, output_state)
            
            # Log successful execution
            duration = time.time() - start_time
            trace_logger.info(f"[corr:{correlation_id}] Completed node {node_name} in {duration:.4f}s (exec:{execution_id})")
            
            # Add state changes to log if any
            if state_changes:
                change_summary = ", ".join(state_changes.keys())
                trace_logger.info(f"[corr:{correlation_id}] State changes: {change_summary}")
            
            return result
        except Exception as e:
            # Track failure
            success = False
            error = {
                "type": type(e).__name__,
                "message": str(e),
                "traceback": traceback.format_exc()
            }
            
            # Log error
            duration = time.time() - start_time
            trace_logger.error(f"[corr:{correlation_id}] Error in node {node_name} after {duration:.4f}s: {str(e)} (exec:{execution_id})")
            
            # Re-raise the exception
            raise
        finally:
            # Finalize trace entry
            duration = time.time() - start_time
            end_timestamp = datetime.datetime.now().isoformat()
            
            trace_entry.update({
                "duration": duration,
                "end_timestamp": end_timestamp,
                "success": success,
                "output_state": _extract_key_fields(output_state) if output_state else None,
                "state_changes": state_changes,
                "error": error
            })
            
            # Add memory usage if profiling
            if _enable_profiling:
                try:
                    import psutil
                    # Get current process memory usage
                    process = psutil.Process(os.getpid())
                    memory_info = process.memory_info()
                    trace_entry["memory_usage"] = memory_info.rss  # resident set size in bytes
                except ImportError:
                    pass
                except Exception as mem_error:
                    trace_logger.debug(f"Error getting memory usage: {mem_error}")
            
            # Add to trace history
            add_to_trace_history(trace_entry)
            
    return wrapper


def _filter_state_for_log(state_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Filter the state dictionary to remove sensitive or verbose fields."""
    filtered = {}
    
    for key, value in state_dict.items():
        if key in _filtered_keys:
            # Replace with a placeholder
            filtered[key] = "<filtered>"
        else:
            filtered[key] = value
            
    return filtered


def _extract_key_fields(state_dict: Dict[str, Any], max_depth: int = 2, max_items: int = 3, max_string_length: int = 100) -> Dict[str, Any]:
    """
    Extract the most important fields for concise logging with smart summarization.
    
    Args:
        state_dict: The state dictionary to extract fields from
        max_depth: Maximum depth to traverse for nested objects
        max_items: Maximum number of items to include in arrays/dictionaries
        max_string_length: Maximum length for string values
        
    Returns:
        Dictionary with extracted key fields
    """
    # If not a dictionary, return as is (or string summary for complex types)
    if not isinstance(state_dict, dict):
        if isinstance(state_dict, (list, tuple)):
            # For lists/tuples, summarize with length
            list_len = len(state_dict)
            if list_len == 0:
                return []
            elif list_len <= max_items:
                # For small lists, recursively process each item
                return [_summarize_value(item, max_depth-1, max_items, max_string_length) 
                        for item in state_dict[:max_items]]
            else:
                # For larger lists, include just a few items and indicate total size
                return {
                    "summary": f"{list_len} items", 
                    "sample": [_summarize_value(item, max_depth-1, max_items, max_string_length) 
                              for item in state_dict[:max_items]]
                }
        elif isinstance(state_dict, str):
            # Truncate long strings
            if len(state_dict) > max_string_length:
                return state_dict[:max_string_length] + "..."
            return state_dict
        else:
            # For other types, convert to string
            return str(state_dict)
    
    # Stop recursion at max depth
    if max_depth <= 0:
        keys = list(state_dict.keys())
        return f"<object with {len(keys)} keys: {', '.join(keys[:3])}...>"
        
    # Start with empty result
    result = {}
    
    # List of critical fields - always include these if present
    critical_fields = [
        'task_name', 'error', 'done', 'kfm_action', 'status', 
        'id', 'name', 'type', 'action', 'input', 'output', 'result',
        'timestamp', 'success'
    ]
    
    # First, extract critical fields
    for field in critical_fields:
        if field in state_dict:
            result[field] = _summarize_value(
                state_dict[field], max_depth-1, max_items, max_string_length
            )
    
    # Handle special cases
    if 'state' in state_dict and isinstance(state_dict['state'], dict):
        # Recursively process state field with reduced depth
        result['state'] = _extract_key_fields(
            state_dict['state'], max_depth-1, max_items, max_string_length
        )
    
    # If we still have room for more fields, add other important keys
    remaining_slots = max_items - len(result)
    if remaining_slots > 0:
        # Get remaining keys that aren't in critical fields or already processed
        remaining_keys = [k for k in state_dict.keys() 
                          if k not in critical_fields and k not in result]
        
        # Sort remaining keys - prioritize shorter dictionaries and non-empty values
        def key_priority(k):
            v = state_dict[k]
            if isinstance(v, dict):
                return (0, len(v))  # prioritize dict fields by size (smaller first)
            if isinstance(v, (list, tuple)):
                return (1, len(v))  # prioritize lists by size
            if v:  # non-empty value
                return (2, 0)
            return (3, 0)  # empty values last
            
        sorted_remaining = sorted(remaining_keys, key=key_priority)
        
        # Add the highest priority fields that fit
        for key in sorted_remaining[:remaining_slots]:
            result[key] = _summarize_value(
                state_dict[key], max_depth-1, max_items, max_string_length
            )
    
    # If there are more fields than we're showing, add a count
    if len(state_dict) > len(result):
        result['_additional_fields'] = len(state_dict) - len(result)
    
    return result


def _summarize_value(value: Any, max_depth: int, max_items: int, max_string_length: int) -> Any:
    """
    Summarize a value for logging based on its type.
    
    Args:
        value: The value to summarize
        max_depth: Maximum recursion depth remaining
        max_items: Maximum items to include
        max_string_length: Maximum string length
        
    Returns:
        Summarized value
    """
    if isinstance(value, dict):
        if max_depth <= 0:
            return f"<dict with {len(value)} keys>"
        return _extract_key_fields(value, max_depth, max_items, max_string_length)
    elif isinstance(value, (list, tuple)):
        if len(value) == 0:
            return []
        if len(value) <= max_items:
            return [_summarize_value(item, max_depth-1, max_items, max_string_length) 
                   for item in value[:max_items]]
        else:
            return {
                "length": len(value),
                "sample": [_summarize_value(item, max_depth-1, max_items, max_string_length) 
                          for item in value[:max_items]]
            }
    elif isinstance(value, str):
        if len(value) > max_string_length:
            return value[:max_string_length] + "..."
        return value
    else:
        return value


def _identify_state_changes(old_state: Dict[str, Any], new_state: Dict[str, Any], 
                           path: str = "", ignore_keys: List[str] = None) -> Dict[str, Dict[str, Any]]:
    """
    Identify changes between two state dictionaries.
    
    Args:
        old_state: Previous state dictionary
        new_state: New state dictionary
        path: Current path in nested dictionaries (for recursion)
        ignore_keys: Keys to ignore when comparing
        
    Returns:
        Dictionary of changes with before and after values
    """
    if ignore_keys is None:
        # Default keys to ignore (timestamps, internal tracking)
        ignore_keys = ['_timestamp', '_id', '_trace_id', '_node_executions']
        
    # Convert inputs to dictionaries if they aren't already
    if not isinstance(old_state, dict):
        old_state = {} if old_state is None else {'value': old_state}
    if not isinstance(new_state, dict):
        new_state = {} if new_state is None else {'value': new_state}
    
    changes = {}
    
    # Check for keys in old_state that changed or were removed
    for key, old_value in old_state.items():
        if key in ignore_keys:
            continue
            
        current_path = f"{path}.{key}" if path else key
        
        if key not in new_state:
            # Key was removed
            changes[current_path] = {
                'before': old_value,
                'after': None,
                'change_type': 'removed'
            }
        elif new_state[key] != old_value:
            # Value changed
            if isinstance(old_value, dict) and isinstance(new_state[key], dict):
                # Recursively check dictionaries
                nested_changes = _identify_state_changes(old_value, new_state[key], current_path, ignore_keys)
                if nested_changes:
                    changes.update(nested_changes)
            elif isinstance(old_value, list) and isinstance(new_state[key], list):
                # Special handling for lists to avoid noise from minor reordering
                if _lists_significantly_different(old_value, new_state[key]):
                    changes[current_path] = {
                        'before': old_value,
                        'after': new_state[key],
                        'change_type': 'modified',
                        'list_changes': {
                            'added': [item for item in new_state[key] if item not in old_value],
                            'removed': [item for item in old_value if item not in new_state[key]]
                        }
                    }
            else:
                # Simple value change
                changes[current_path] = {
                    'before': old_value,
                    'after': new_state[key],
                    'change_type': 'modified'
                }
    
    # Check for keys added in new_state
    for key, new_value in new_state.items():
        if key in ignore_keys or key in old_state:
            continue
            
        current_path = f"{path}.{key}" if path else key
        
        # Key was added
        changes[current_path] = {
            'before': None,
            'after': new_value,
            'change_type': 'added'
        }
    
    return changes

def _lists_significantly_different(list1: List[Any], list2: List[Any]) -> bool:
    """
    Determine if two lists are significantly different, not just reordered.
    
    Args:
        list1: First list
        list2: Second list
        
    Returns:
        True if the lists have significant differences beyond ordering
    """
    # Different lengths is a significant change
    if len(list1) != len(list2):
        return True
        
    # Check if content is the same regardless of order
    try:
        # Try to do set comparison for hashable items
        return set(list1) != set(list2)
    except:
        # For non-hashable items, check each way for membership
        for item in list1:
            if item not in list2:
                return True
        for item in list2:
            if item not in list1:
                return True
                
        return False

def visualize_execution_flow(
    include_states: bool = False,
    include_changes: bool = True,
    max_states: int = 5,
    width: int = 100
) -> str:
    """
    Generate a visualization of the execution flow from trace history.
    
    Args:
        include_states: Whether to include state details in the visualization
        include_changes: Whether to include state changes in the visualization
        max_states: Maximum number of states to include
        width: Width of the visualization in characters
        
    Returns:
        Text visualization of the execution flow
    """
    if not _trace_history:
        return "No trace history available."
    
    # Start with title and header
    lines = ["Execution Flow Visualization:"]
    lines.append("=" * width)
    
    # Add summary statistics
    total_nodes = len(_trace_history)
    total_time = sum(entry.get("duration", 0) for entry in _trace_history)
    successful_nodes = sum(1 for entry in _trace_history if entry.get("success", False))
    
    lines.append(f"Total Nodes: {total_nodes}  |  "
               f"Successful: {successful_nodes}  |  "
               f"Failed: {total_nodes - successful_nodes}  |  "
               f"Total Time: {total_time:.4f}s")
    lines.append("-" * width)
    
    # Show timeline
    timeline = ["│"] * width
    node_positions = {}
    
    if len(_trace_history) > 1:
        start_time = _trace_history[0].get("timestamp", 0)
        end_time = _trace_history[-1].get("timestamp", 0)
        time_range = end_time - start_time
        
        # Handle case where all timestamps are the same
        if time_range == 0:
            time_range = 1
        
        for i, entry in enumerate(_trace_history):
            timestamp = entry.get("timestamp", 0)
            # Calculate position on timeline
            pos = int(((timestamp - start_time) / time_range) * (width - 2))
            pos = max(0, min(pos, width - 1))  # Ensure it's within bounds
            
            # Mark with X for failures, O for success
            symbol = "⦿" if entry.get("success", True) else "✗"
            timeline[pos] = symbol
            
            # Label position with node name
            node_name = entry.get("node", f"Node{i}")
            if node_name in node_positions:
                node_positions[node_name].append(pos)
            else:
                node_positions[node_name] = [pos]
    
    lines.append("Timeline:")
    lines.append("".join(timeline))
    lines.append("")
    
    # Add each node execution with details
    lines.append("Node Executions:")
    for i, entry in enumerate(_trace_history):
        node_name = entry.get("node", f"Node{i}")
        success = entry.get("success", True)
        duration = entry.get("duration", 0)
        correlation_id = entry.get("correlation_id", "unknown")
        
        # Format status line
        status_symbol = "✅" if success else "❌"
        lines.append(f"{i+1}. {status_symbol} {node_name} ({duration:.4f}s) [corr:{correlation_id[:8]}...]")
        
        # Add changes if requested and available
        if include_changes and "state_changes" in entry and entry["state_changes"]:
            lines.append("   Changes:")
            changes = entry["state_changes"]
            # Limit to at most 3 changes for brevity
            for j, (field, change) in enumerate(list(changes.items())[:3]):
                before = change.get("before")
                after = change.get("after")
                lines.append(f"   - {field}: {before} → {after}")
            
            # Indicate if there are more changes
            if len(changes) > 3:
                lines.append(f"   - ... and {len(changes) - 3} more changes")
        
        # Add error details for failed nodes
        if not success and "error" in entry:
            error = entry["error"]
            lines.append(f"   Error: {error.get('type', 'Unknown')}: {error.get('message', 'No message')}")
            
        # Add state details if requested
        if include_states:
            if i < max_states:  # Limit number of states shown
                # Show input state
                if "input_state" in entry:
                    lines.append("   Input State (summary):")
                    state_viz = create_state_visualization(
                        entry["input_state"],
                        max_depth=1,
                        format_type='text'
                    )
                    # Indent each line
                    for line in state_viz.split("\n"):
                        if line.strip():
                            lines.append(f"     {line}")
            elif i == max_states:
                lines.append("   ... (remaining states omitted for brevity)")
                
        # Add separator between nodes
        lines.append("   " + "-" * (width - 3))
    
    return "\n".join(lines)

def visualize_state_changes(
    state_before: Dict[str, Any],
    state_after: Dict[str, Any],
    include_fields: Optional[List[str]] = None,
    exclude_fields: Optional[List[str]] = None,
    max_depth: int = 2
) -> str:
    """
    Visualize changes between two state dictionaries.
    
    Args:
        state_before: State before changes
        state_after: State after changes
        include_fields: Only include these fields in comparison
        exclude_fields: Exclude these fields from comparison
        max_depth: Maximum depth for nested objects
        
    Returns:
        Text visualization of state changes
    """
    # Filter states
    filtered_before = _filter_fields_for_visualization(state_before, include_fields, exclude_fields)
    filtered_after = _filter_fields_for_visualization(state_after, include_fields, exclude_fields)
    
    # Find changes
    changes = _identify_state_changes(filtered_before, filtered_after)
    
    # Format the visualization
    lines = ["State Changes:"]
    lines.append("=" * 60)
    
    if not changes:
        lines.append("No changes detected.")
        return "\n".join(lines)
    
    # Group changes by path components
    grouped_changes = {}
    for path, change in changes.items():
        # Split path into components
        parts = path.split('.')
        if len(parts) > 1:
            # Group by first component
            group = parts[0]
            if group not in grouped_changes:
                grouped_changes[group] = {}
            grouped_changes[group]['.'.join(parts[1:])] = change
        else:
            # Top level change
            if 'TOP_LEVEL' not in grouped_changes:
                grouped_changes['TOP_LEVEL'] = {}
            grouped_changes['TOP_LEVEL'][path] = change
    
    # Format each group
    for group, group_changes in grouped_changes.items():
        if group == 'TOP_LEVEL':
            lines.append("Top-level changes:")
        else:
            lines.append(f"Changes in {group}:")
            
        for path, change in group_changes.items():
            change_type = change.get('change_type', 'unknown')
            before = change.get('before')
            after = change.get('after')
            
            if change_type == 'added':
                lines.append(f"  + {path}: {after}")
            elif change_type == 'removed':
                lines.append(f"  - {path}: {before}")
            elif change_type == 'modified':
                # Format the before/after values
                before_str = _format_value_for_diff(before, max_depth)
                after_str = _format_value_for_diff(after, max_depth)
                
                lines.append(f"  ~ {path}:")
                lines.append(f"    - Before: {before_str}")
                lines.append(f"    - After:  {after_str}")
        
        lines.append("")  # Empty line between groups
    
    return "\n".join(lines)

def _format_value_for_diff(value: Any, max_depth: int = 2, current_depth: int = 0) -> str:
    """
    Format a value for display in a diff visualization.
    
    Args:
        value: The value to format
        max_depth: Maximum depth for nested objects
        current_depth: Current recursion depth
        
    Returns:
        Formatted string representation
    """
    if current_depth > max_depth:
        return "..."
        
    if isinstance(value, dict):
        if not value:
            return "{}"
        elif current_depth == max_depth:
            return f"{{...}} (dict with {len(value)} keys)"
        else:
            formatted = "{ "
            items = []
            for k, v in list(value.items())[:3]:  # Limit to 3 items
                items.append(f"{k}: {_format_value_for_diff(v, max_depth, current_depth + 1)}")
            formatted += ", ".join(items)
            if len(value) > 3:
                formatted += f", ... ({len(value) - 3} more)"
            formatted += " }"
            return formatted
    elif isinstance(value, list):
        if not value:
            return "[]"
        elif current_depth == max_depth:
            return f"[...] (list with {len(value)} items)"
        else:
            formatted = "[ "
            items = []
            for item in value[:3]:  # Limit to 3 items
                items.append(_format_value_for_diff(item, max_depth, current_depth + 1))
            formatted += ", ".join(items)
            if len(value) > 3:
                formatted += f", ... ({len(value) - 3} more)"
            formatted += " ]"
            return formatted
    elif isinstance(value, str):
        if len(value) > 100:
            return f'"{value[:100]}..."'
        else:
            return f'"{value}"'
    else:
        return str(value)

def create_execution_summary(include_reflection: bool = True) -> Dict[str, Any]:
    """
    Create a comprehensive summary of the execution.
    
    Args:
        include_reflection: Whether to include reflection analysis
        
    Returns:
        Dictionary with execution summary
    """
    if not _trace_history:
        return {"error": "No trace history available"}
    
    # Collect basic statistics
    nodes_count = len(_trace_history)
    successful_nodes = sum(1 for entry in _trace_history if entry.get("success", False))
    failed_nodes = nodes_count - successful_nodes
    
    # Calculate timing statistics
    durations = [entry.get("duration", 0) for entry in _trace_history]
    total_duration = sum(durations)
    avg_duration = total_duration / nodes_count if nodes_count > 0 else 0
    max_duration = max(durations) if durations else 0
    
    # Identify slow nodes (taking more than twice the average time)
    slow_nodes = []
    for entry in _trace_history:
        if entry.get("duration", 0) > avg_duration * 2:
            slow_nodes.append({
                "node": entry.get("node", "unknown"),
                "duration": entry.get("duration", 0)
            })
    
    # Count changes by field
    field_changes = {}
    for entry in _trace_history:
        if "state_changes" in entry:
            for field in entry["state_changes"]:
                field_changes[field] = field_changes.get(field, 0) + 1
    
    # Get most changed fields
    most_changed = sorted(
        [{"field": field, "changes": count} for field, count in field_changes.items()],
        key=lambda x: x["changes"],
        reverse=True
    )[:5]  # Top 5
    
    # Create summary
    summary = {
        "nodes": {
            "total": nodes_count,
            "successful": successful_nodes,
            "failed": failed_nodes
        },
        "timing": {
            "total_duration": total_duration,
            "average_node_duration": avg_duration,
            "maximum_node_duration": max_duration
        },
        "execution_path": [entry.get("node", f"Node{i}") for i, entry in enumerate(_trace_history)],
        "slow_nodes": slow_nodes,
        "most_changed_fields": most_changed
    }
    
    # Add node type distribution
    node_types = {}
    for entry in _trace_history:
        node_name = entry.get("node", "unknown")
        node_info = get_node_type(node_name)
        node_type = node_info.get("type", "unknown")
        node_types[node_type] = node_types.get(node_type, 0) + 1
    
    summary["node_types"] = node_types
    
    # Add reflection data if available and requested
    if include_reflection:
        last_entry = _trace_history[-1] if _trace_history else None
        if last_entry and "reflection" in last_entry:
            summary["reflection"] = {
                "text": last_entry["reflection"],
                "analysis": last_entry.get("reflection_analysis", {})
            }
    
    return summary

def save_execution_summary(filepath: str, include_visualizations: bool = True) -> bool:
    """
    Save a comprehensive execution summary to a file.
    
    Args:
        filepath: Path to save the summary
        include_visualizations: Whether to include visualizations
        
    Returns:
        Boolean indicating success
    """
    try:
        # Create summary data
        summary = create_execution_summary()
        
        # Add visualizations if requested
        if include_visualizations:
            visualizations = {
                "execution_flow": visualize_execution_flow(include_states=False),
                "timeline": get_state_timeline(width=80, include_states=False)
            }
            summary["visualizations"] = visualizations
        
        # Save to file
        with open(filepath, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
            
        trace_logger.info(f"Execution summary saved to {filepath}")
        return True
    except Exception as e:
        trace_logger.error(f"Error saving execution summary: {e}")
        trace_logger.debug(traceback.format_exc())
        return False

# Add the StateHistoryTracker class
class StateHistoryTracker:
    """
    Tracks state history in a circular buffer and provides functionality
    for state snapshots, search, and visualization.
    """
    
    def __init__(self, max_size: int = 100, snapshot_dir: str = "logs/state_snapshots"):
        """
        Initialize the state history tracker.
        
        Args:
            max_size: Maximum number of states to store in the circular buffer
            snapshot_dir: Directory to store state snapshots
        """
        self.buffer: Deque[Dict[str, Any]] = deque(maxlen=max_size)
        self.max_size = max_size
        self.snapshot_dir = snapshot_dir
        self.snapshots: Dict[str, Dict[str, Any]] = {}
        self.snapshot_metadata: Dict[str, Dict[str, Any]] = {}
        
        # Create snapshot directory if it doesn't exist
        if not os.path.exists(snapshot_dir):
            os.makedirs(snapshot_dir, exist_ok=True)
            
        trace_logger.info(f"State history tracker initialized with buffer size {max_size}")
    
    def reconfigure(self, max_size: Optional[int] = None, snapshot_dir: Optional[str] = None) -> None:
        """
        Reconfigure the state history tracker.
        
        Args:
            max_size: New maximum buffer size
            snapshot_dir: New snapshot directory
        """
        if max_size is not None and max_size != self.max_size:
            # Create a new buffer with the new size and copy over existing entries
            new_buffer = deque(maxlen=max_size)
            # Copy as many items as will fit in the new buffer
            items_to_copy = min(len(self.buffer), max_size)
            for _ in range(items_to_copy):
                if len(self.buffer) > items_to_copy:
                    self.buffer.popleft()  # Remove excess items
            
            # Copy remaining items to the new buffer
            new_buffer.extend(self.buffer)
            self.buffer = new_buffer
            self.max_size = max_size
            trace_logger.info(f"State history buffer size reconfigured to {max_size}")
        
        if snapshot_dir and snapshot_dir != self.snapshot_dir:
            self.snapshot_dir = snapshot_dir
            if not os.path.exists(snapshot_dir):
                os.makedirs(snapshot_dir, exist_ok=True)
            trace_logger.info(f"Snapshot directory reconfigured to {snapshot_dir}")
    
    def clear(self) -> None:
        """Clear the state history buffer."""
        self.buffer.clear()
        trace_logger.info("State history buffer cleared")
    
    def add_state(self, node_name: str, state: Dict[str, Any], is_input: bool = False, 
                 metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Add a state to the history buffer.
        
        Args:
            node_name: Name of the node that produced the state
            state: The state to add
            is_input: Whether this is an input state (True) or output state (False)
            metadata: Additional metadata to store with the state
        """
        # Create a deep copy of the state to prevent modification
        state_copy = json.loads(json.dumps(state))
        
        # Create the history entry
        entry = {
            "id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "datetime": datetime.datetime.now().isoformat(),
            "node_name": node_name,
            "is_input": is_input,
            "state": state_copy,
            "metadata": metadata or {}
        }
        
        # Add to the buffer
        self.buffer.append(entry)
        
        # Log at debug level
        trace_logger.debug(f"Added state to history buffer: {node_name} ({'input' if is_input else 'output'})")
    
    def get_history(self, count: Optional[int] = None, 
                   filter_func: Optional[Callable[[Dict[str, Any]], bool]] = None) -> List[Dict[str, Any]]:
        """
        Get the state history.
        
        Args:
            count: Number of most recent states to return (None for all)
            filter_func: Optional function to filter states
            
        Returns:
            List of state history entries
        """
        # Get all entries
        entries = list(self.buffer)
        
        # Apply filter if provided
        if filter_func:
            entries = [entry for entry in entries if filter_func(entry)]
        
        # Limit to count if provided
        if count is not None:
            entries = entries[-count:]
            
        return entries
    
    def create_snapshot(self, state: Dict[str, Any], label: str, 
                      category: Optional[str] = None, description: Optional[str] = None) -> str:
        """
        Create a snapshot of a state.
        
        Args:
            state: The state to snapshot
            label: Label for the snapshot
            category: Optional category for grouping snapshots
            description: Optional description of the snapshot
            
        Returns:
            ID of the snapshot
        """
        # Generate a unique ID for the snapshot
        snapshot_id = str(uuid.uuid4())
        
        # Create a deep copy of the state
        state_copy = json.loads(json.dumps(state))
        
        # Create metadata
        metadata = {
            "id": snapshot_id,
            "label": label,
            "category": category,
            "description": description,
            "timestamp": time.time(),
            "datetime": datetime.datetime.now().isoformat()
        }
        
        # Store in memory
        self.snapshots[snapshot_id] = state_copy
        self.snapshot_metadata[snapshot_id] = metadata
        
        # Save to disk
        self._save_snapshot_to_disk(snapshot_id, state_copy, metadata)
        
        trace_logger.info(f"Created snapshot {label} ({snapshot_id})")
        return snapshot_id
    
    def get_snapshot(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a snapshot by ID.
        
        Args:
            snapshot_id: ID of the snapshot
            
        Returns:
            The snapshot state or None if not found
        """
        # Check if in memory
        if snapshot_id in self.snapshots:
            return {
                "state": self.snapshots[snapshot_id],
                "metadata": self.snapshot_metadata[snapshot_id]
            }
        
        # Try to load from disk
        snapshot_path = os.path.join(self.snapshot_dir, f"{snapshot_id}.json")
        if os.path.exists(snapshot_path):
            try:
                with open(snapshot_path, 'r') as f:
                    data = json.load(f)
                    # Cache in memory for future use
                    self.snapshots[snapshot_id] = data["state"]
                    self.snapshot_metadata[snapshot_id] = data["metadata"]
                    return data
            except Exception as e:
                trace_logger.error(f"Error loading snapshot {snapshot_id}: {str(e)}")
                
        return None
    
    def list_snapshots(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all available snapshots.
        
        Args:
            category: Optional category to filter by
            
        Returns:
            List of snapshot metadata
        """
        # Get all metadata
        all_metadata = list(self.snapshot_metadata.values())
        
        # Filter by category if provided
        if category:
            all_metadata = [meta for meta in all_metadata if meta.get("category") == category]
            
        return sorted(all_metadata, key=lambda x: x["timestamp"], reverse=True)
    
    def search_history(self, query: str, case_sensitive: bool = False,
                     field_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search the state history for a string value.
        
        Args:
            query: String to search for
            case_sensitive: Whether the search is case sensitive
            field_path: Optional dot-notation path to limit search to specific field
            
        Returns:
            List of matching state history entries
        """
        results = []
        
        # Prepare query
        if not case_sensitive:
            query = query.lower()
        
        for entry in self.buffer:
            # Apply field path filter if provided
            if field_path:
                value = self._get_nested_value(entry["state"], field_path)
                if value is not None:
                    str_value = str(value)
                    if not case_sensitive:
                        str_value = str_value.lower()
                    if query in str_value:
                        results.append(entry)
            else:
                # Search entire state
                state_str = json.dumps(entry["state"])
                if not case_sensitive:
                    state_str = state_str.lower()
                if query in state_str:
                    results.append(entry)
        
        return results
    
    def find_state_by_condition(self, condition: Callable[[Dict[str, Any]], bool]) -> List[Dict[str, Any]]:
        """
        Find states that match a condition.
        
        Args:
            condition: Function that takes a state and returns True if it matches
            
        Returns:
            List of matching state history entries
        """
        return [entry for entry in self.buffer if condition(entry["state"])]
    
    def get_state_at_index(self, index: int) -> Optional[Dict[str, Any]]:
        """
        Get a state by its index in the buffer.
        
        Args:
            index: Index of the state to retrieve (negative indices count from the end)
            
        Returns:
            The state history entry or None if index is out of bounds
        """
        if not self.buffer:
            return None
            
        try:
            return list(self.buffer)[index]
        except IndexError:
            return None
    
    def generate_timeline_visualization(self, width: int = 80, 
                                      include_states: bool = False) -> str:
        """
        Generate a text-based visualization of the state timeline.
        
        Args:
            width: Width of the timeline in characters
            include_states: Whether to include state details
            
        Returns:
            String representation of the timeline
        """
        if not self.buffer:
            return "No state history available."
        
        # Get all entries
        entries = list(self.buffer)
        
        # Calculate time range
        start_time = entries[0]["timestamp"]
        end_time = entries[-1]["timestamp"]
        time_range = end_time - start_time
        
        # Handle zero time range (rare)
        if time_range == 0:
            time_range = 0.001  # Arbitrary small value
        
        # Generate timeline
        lines = ["State History Timeline:"]
        lines.append("=" * width)
        
        # Create a timeline with markers for each state
        timeline = [" "] * width
        node_positions = {}
        
        for i, entry in enumerate(entries):
            # Calculate position on timeline
            pos = int(((entry["timestamp"] - start_time) / time_range) * (width - 1))
            timeline[pos] = "│"
            
            # Store node name and position for labels
            node_name = entry["node_name"]
            if node_name in node_positions:
                node_positions[node_name].append(pos)
            else:
                node_positions[node_name] = [pos]
        
        # Add entry markers
        for i, entry in enumerate(entries):
            pos = int(((entry["timestamp"] - start_time) / time_range) * (width - 1))
            timeline[pos] = "●"
        
        # Add timeline to output
        lines.append("".join(timeline))
        lines.append("Start" + " " * (width - 10) + "End")
        
        # Add time markers
        time_fmt = "%H:%M:%S.%f"
        start_datetime = datetime.datetime.fromtimestamp(start_time).strftime(time_fmt)[:-3]
        end_datetime = datetime.datetime.fromtimestamp(end_time).strftime(time_fmt)[:-3]
        lines.append(f"{start_datetime}" + " " * (width - len(start_datetime) - len(end_datetime)) + f"{end_datetime}")
        
        # Add duration
        lines.append(f"Total duration: {time_range:.4f}s")
        lines.append("")
        
        # Add node labels
        lines.append("Nodes:")
        for node_name, positions in node_positions.items():
            # Count occurrences
            count = len(positions)
            # Get average position for label
            avg_pos = sum(positions) // count
            
            # Create label line
            label_line = [" "] * width
            for pos in positions:
                label_line[pos] = "│"
            label_line[avg_pos] = "●"
            
            # Add node label
            lines.append("".join(label_line) + f" {node_name} ({count}x)")
        
        # Add state details if requested
        if include_states:
            lines.append("")
            lines.append("State Details:")
            lines.append("-" * width)
            
            for i, entry in enumerate(entries):
                # Format timestamp
                dt = datetime.datetime.fromtimestamp(entry["timestamp"])
                time_str = dt.strftime("%H:%M:%S.%f")[:-3]
                
                # Add entry header
                lines.append(f"[{i+1}/{len(entries)}] {time_str} - {entry['node_name']} ({'input' if entry['is_input'] else 'output'})")
                
                # Add metadata
                if entry.get("metadata"):
                    metadata = entry["metadata"]
                    if "success" in metadata:
                        status = "✅ Success" if metadata["success"] else "❌ Error"
                        lines.append(f"Status: {status}")
                    if "duration" in metadata:
                        lines.append(f"Duration: {metadata['duration']:.4f}s")
                    if "error" in metadata:
                        lines.append(f"Error: {metadata['error']}")
                
                # Add state snippet (truncated)
                state_str = json.dumps(entry["state"], indent=2)
                if len(state_str) > 500:
                    state_str = state_str[:500] + "... [truncated]"
                lines.append("State:")
                lines.append(state_str)
                lines.append("-" * width)
        
        return "\n".join(lines)
    
    def _save_snapshot_to_disk(self, snapshot_id: str, state: Dict[str, Any], 
                             metadata: Dict[str, Any]) -> bool:
        """
        Save a snapshot to disk.
        
        Args:
            snapshot_id: ID of the snapshot
            state: State to save
            metadata: Metadata to save
            
        Returns:
            True if successful, False otherwise
        """
        snapshot_path = os.path.join(self.snapshot_dir, f"{snapshot_id}.json")
        
        try:
            with open(snapshot_path, 'w') as f:
                json.dump({
                    "state": state,
                    "metadata": metadata
                }, f, indent=2)
            return True
        except Exception as e:
            trace_logger.error(f"Error saving snapshot to disk: {str(e)}")
            return False
    
    def _get_nested_value(self, obj: Dict[str, Any], path: str) -> Any:
        """
        Get a value from a nested object using dot notation.
        
        Args:
            obj: Object to get value from
            path: Dot-notation path to the value
            
        Returns:
            The value or None if not found
        """
        if not path:
            return obj
            
        parts = path.split('.')
        current = obj
        
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
                
        return current

# Add functions to facilitate state history tracking

def save_state_snapshot(state: Dict[str, Any], label: str, 
                       category: Optional[str] = None, 
                       description: Optional[str] = None) -> str:
    """
    Save a snapshot of the current state.
    
    Args:
        state: The state to snapshot
        label: Label for the snapshot
        category: Optional category for grouping snapshots
        description: Optional description of the snapshot
        
    Returns:
        ID of the snapshot
    """
    tracker = get_state_history_tracker()
    return tracker.create_snapshot(state, label, category, description)

def get_state_snapshot(snapshot_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a state snapshot by ID.
    
    Args:
        snapshot_id: ID of the snapshot
        
    Returns:
        The snapshot state or None if not found
    """
    tracker = get_state_history_tracker()
    return tracker.get_snapshot(snapshot_id)

def list_state_snapshots(category: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List available state snapshots.
    
    Args:
        category: Optional category to filter by
        
    Returns:
        List of snapshot metadata
    """
    tracker = get_state_history_tracker()
    return tracker.list_snapshots(category)

def search_state_history(query: str, case_sensitive: bool = False,
                        field_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Search the state history for a string value.
    
    Args:
        query: String to search for
        case_sensitive: Whether the search is case sensitive
        field_path: Optional dot-notation path to limit search to specific field
        
    Returns:
        List of matching state history entries
    """
    tracker = get_state_history_tracker()
    return tracker.search_history(query, case_sensitive, field_path)

def get_state_timeline(width: int = 80, include_states: bool = False) -> str:
    """
    Generate a text-based visualization of the state timeline.
    
    Args:
        width: Width of the timeline in characters
        include_states: Whether to include state details
        
    Returns:
        String representation of the timeline
    """
    tracker = get_state_history_tracker()
    return tracker.generate_timeline_visualization(width, include_states)

def get_state_at_point(index: int) -> Optional[Dict[str, Any]]:
    """
    Get a state by its index in the history.
    
    Args:
        index: Index of the state to retrieve (negative indices count from the end)
        
    Returns:
        The state or None if index is out of bounds
    """
    tracker = get_state_history_tracker()
    return tracker.get_state_at_index(index)

# Add the StateFieldMonitor class for watching specific state fields
class StateFieldMonitor:
    """
    Monitor specific fields in the state with configurable watch expressions
    and alert mechanisms.
    """
    
    def __init__(self):
        """Initialize the state field monitor."""
        # Dictionary to store registered watches
        # Format: {watch_id: {field_path, expression, description, alert_level, callback}}
        self.watches = {}
        
        # Dictionary to track the previous values of watched fields
        self.previous_values = {}
        
        # Configure logger for this class
        self.logger = setup_logger('src.tracing.StateFieldMonitor')
        
        # Alert levels
        self.ALERT_LEVELS = {
            'INFO': 0,
            'WARNING': 1,
            'ERROR': 2,
            'CRITICAL': 3
        }
        
        # Statistics
        self.stats = {
            'triggers': 0,
            'evaluations': 0,
            'by_level': {level: 0 for level in self.ALERT_LEVELS}
        }
        
        self.logger.info("StateFieldMonitor initialized")
    
    def add_watch(self, field_path: str, expression: str = None, 
                description: str = None, alert_level: str = 'INFO',
                callback: Callable = None) -> str:
        """
        Add a watch for a specific field in the state.
        
        Args:
            field_path: Dot notation path to the field to watch (e.g., "options.verbose")
            expression: Optional watch expression (e.g., "value > 10" or "value != prev_value")
                        If None, triggers on any change.
            description: Optional description of what this watch is monitoring
            alert_level: Alert level ('INFO', 'WARNING', 'ERROR', 'CRITICAL')
            callback: Optional function to call when the watch is triggered
            
        Returns:
            str: ID of the created watch
        """
        # Generate a unique ID for the watch
        watch_id = str(uuid.uuid4())
        
        # Validate and normalize the alert level
        alert_level = alert_level.upper()
        if alert_level not in self.ALERT_LEVELS:
            alert_level = 'INFO'
            self.logger.warning(f"Invalid alert level '{alert_level}', defaulting to 'INFO'")
        
        # Create the watch entry
        watch = {
            'field_path': field_path,
            'expression': expression,
            'description': description or f"Watch for changes to {field_path}",
            'alert_level': alert_level,
            'callback': callback,
            'created_at': time.time(),
            'trigger_count': 0,
            'last_triggered': None
        }
        
        # Store the watch
        self.watches[watch_id] = watch
        
        self.logger.info(f"Added watch {watch_id} for field '{field_path}' with level {alert_level}")
        return watch_id
    
    def remove_watch(self, watch_id: str) -> bool:
        """
        Remove a watch by its ID.
        
        Args:
            watch_id: ID of the watch to remove
            
        Returns:
            bool: True if the watch was removed, False otherwise
        """
        if watch_id in self.watches:
            watch = self.watches.pop(watch_id)
            # Clean up any previous value
            field_path = watch['field_path']
            if field_path in self.previous_values:
                del self.previous_values[field_path]
                
            self.logger.info(f"Removed watch {watch_id} for field '{field_path}'")
            return True
        
        self.logger.warning(f"Attempted to remove non-existent watch {watch_id}")
        return False
    
    def clear_watches(self) -> None:
        """Clear all watches."""
        count = len(self.watches)
        self.watches = {}
        self.previous_values = {}
        self.logger.info(f"Cleared {count} watches")
    
    def enable_watch(self, watch_id: str) -> bool:
        """
        Enable a previously disabled watch.
        
        Args:
            watch_id: ID of the watch to enable
            
        Returns:
            bool: True if the watch was enabled, False otherwise
        """
        if watch_id in self.watches:
            self.watches[watch_id]['disabled'] = False
            self.logger.info(f"Enabled watch {watch_id}")
            return True
        
        self.logger.warning(f"Attempted to enable non-existent watch {watch_id}")
        return False
    
    def disable_watch(self, watch_id: str) -> bool:
        """
        Disable a watch without removing it.
        
        Args:
            watch_id: ID of the watch to disable
            
        Returns:
            bool: True if the watch was disabled, False otherwise
        """
        if watch_id in self.watches:
            self.watches[watch_id]['disabled'] = True
            self.logger.info(f"Disabled watch {watch_id}")
            return True
        
        self.logger.warning(f"Attempted to disable non-existent watch {watch_id}")
        return False
    
    def get_watch(self, watch_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a watch.
        
        Args:
            watch_id: ID of the watch
            
        Returns:
            Dict or None: Watch information or None if not found
        """
        return self.watches.get(watch_id)
    
    def list_watches(self, field_path: Optional[str] = None, 
                     alert_level: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all watches, optionally filtered.
        
        Args:
            field_path: Optional filter for field path
            alert_level: Optional filter for alert level
            
        Returns:
            List[Dict]: List of watch information dictionaries
        """
        result = []
        
        for watch_id, watch in self.watches.items():
            # Apply filters
            if field_path and watch['field_path'] != field_path:
                continue
                
            if alert_level and watch['alert_level'] != alert_level:
                continue
                
            # Add ID to the watch info
            watch_info = watch.copy()
            watch_info['id'] = watch_id
            result.append(watch_info)
        
        return result
    
    def evaluate_watches(self, state: Dict[str, Any], 
                        node_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Evaluate all watches against the given state.
        
        Args:
            state: The state to evaluate watches against
            node_name: Optional name of the node that produced this state
            
        Returns:
            List[Dict]: List of triggered watch alert information
        """
        triggered_watches = []
        
        # Update stats
        self.stats['evaluations'] += 1
        
        # Process each watch
        for watch_id, watch in self.watches.items():
            # Skip disabled watches
            if watch.get('disabled', False):
                continue
                
            field_path = watch['field_path']
            expression = watch['expression']
            
            # Get the current field value
            current_value = self._get_nested_value(state, field_path)
            
            # Get the previous value (if any)
            prev_value = self.previous_values.get(field_path)
            
            # Store the current value for next evaluation
            self.previous_values[field_path] = current_value
            
            # If no expression, trigger on any change
            if not expression:
                if current_value != prev_value:
                    triggered_watches.append(self._create_alert(
                        watch_id, watch, current_value, prev_value, node_name))
                continue
            
            # Evaluate the expression
            # Create a context with current_value, prev_value, and common functions
            context = {
                'value': current_value,
                'prev_value': prev_value,
                'field_path': field_path,
                'abs': abs,
                'len': len,
                'str': str,
                'int': int,
                'float': float,
                'max': max,
                'min': min,
                'sum': sum,
                'changed': current_value != prev_value,
                'node_name': node_name
            }
            
            try:
                result = eval(expression, {"__builtins__": {}}, context)
                
                if result:
                    # Expression evaluated to True, trigger the watch
                    triggered_watches.append(self._create_alert(
                        watch_id, watch, current_value, prev_value, node_name))
            except Exception as e:
                self.logger.error(f"Error evaluating watch expression '{expression}': {str(e)}")
        
        # Log triggered watches at the appropriate levels
        for alert in triggered_watches:
            self._log_alert(alert)
            
            # Call the callback if defined
            callback = self.watches[alert['watch_id']].get('callback')
            if callback and callable(callback):
                try:
                    callback(alert)
                except Exception as e:
                    self.logger.error(f"Error in watch callback: {str(e)}")
        
        return triggered_watches
    
    def _create_alert(self, watch_id: str, watch: Dict[str, Any], 
                     current_value: Any, prev_value: Any,
                     node_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Create an alert for a triggered watch.
        
        Args:
            watch_id: ID of the triggered watch
            watch: Watch information
            current_value: Current value of the watched field
            prev_value: Previous value of the watched field
            node_name: Optional name of the node that produced this state
            
        Returns:
            Dict: Alert information
        """
        # Update statistics
        self.stats['triggers'] += 1
        self.stats['by_level'][watch['alert_level']] += 1
        
        # Update watch trigger info
        watch['trigger_count'] += 1
        watch['last_triggered'] = time.time()
        
        # Create the alert
        alert = {
            'watch_id': watch_id,
            'timestamp': time.time(),
            'datetime': datetime.datetime.now().isoformat(),
            'field_path': watch['field_path'],
            'description': watch['description'],
            'alert_level': watch['alert_level'],
            'current_value': current_value,
            'previous_value': prev_value,
            'expression': watch['expression'],
            'node_name': node_name
        }
        
        return alert
    
    def _log_alert(self, alert: Dict[str, Any]) -> None:
        """
        Log an alert at the appropriate level.
        
        Args:
            alert: Alert information
        """
        level = alert['alert_level']
        message = (
            f"WATCH ALERT - {level}: {alert['description']} - "
            f"Field '{alert['field_path']}' changed from "
            f"{alert['previous_value']} to {alert['current_value']}"
        )
        
        if level == 'CRITICAL':
            self.logger.critical(message)
        elif level == 'ERROR':
            self.logger.error(message)
        elif level == 'WARNING':
            self.logger.warning(message)
        else:  # INFO or unknown
            self.logger.info(message)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about watch evaluations and triggers.
        
        Returns:
            Dict: Statistics about watch usage
        """
        return {
            'watches': len(self.watches),
            'evaluations': self.stats['evaluations'],
            'triggers': self.stats['triggers'],
            'by_level': self.stats['by_level'],
            'watches_details': [
                {
                    'id': watch_id,
                    'field_path': watch['field_path'],
                    'alert_level': watch['alert_level'],
                    'trigger_count': watch['trigger_count'],
                    'last_triggered': watch['last_triggered']
                }
                for watch_id, watch in self.watches.items()
            ]
        }
    
    def _get_nested_value(self, obj: Dict[str, Any], path: str) -> Any:
        """
        Get a value from a nested object using dot notation.
        
        Args:
            obj: Object to get value from
            path: Dot-notation path to the value
            
        Returns:
            The value or None if not found
        """
        if not path:
            return obj
            
        parts = path.split('.')
        current = obj
        
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
                
        return current

# Global field monitor instance
_field_monitor = None

def get_field_monitor() -> StateFieldMonitor:
    """
    Get the global field monitor instance.
    
    Returns:
        StateFieldMonitor: The global field monitor
    """
    global _field_monitor
    
    if _field_monitor is None:
        _field_monitor = StateFieldMonitor()
        
    return _field_monitor

def watch_field(field_path: str, expression: str = None, 
               description: str = None, alert_level: str = 'INFO',
               callback: Callable = None) -> str:
    """
    Add a watch for a specific field in the state.
    
    Args:
        field_path: Dot notation path to the field to watch (e.g., "options.verbose")
        expression: Optional watch expression (e.g., "value > 10" or "value != prev_value")
                    If None, triggers on any change.
        description: Optional description of what this watch is monitoring
        alert_level: Alert level ('INFO', 'WARNING', 'ERROR', 'CRITICAL')
        callback: Optional function to call when the watch is triggered
        
    Returns:
        str: ID of the created watch
    """
    monitor = get_field_monitor()
    return monitor.add_watch(field_path, expression, description, alert_level, callback)

def remove_watch(watch_id: str) -> bool:
    """
    Remove a watch by its ID.
    
    Args:
        watch_id: ID of the watch to remove
        
    Returns:
        bool: True if the watch was removed, False otherwise
    """
    monitor = get_field_monitor()
    return monitor.remove_watch(watch_id)

def clear_watches() -> None:
    """Clear all watches."""
    monitor = get_field_monitor()
    monitor.clear_watches()

def get_watch(watch_id: str) -> Optional[Dict[str, Any]]:
    """
    Get information about a watch.
    
    Args:
        watch_id: ID of the watch
        
    Returns:
        Dict or None: Watch information or None if not found
    """
    monitor = get_field_monitor()
    return monitor.get_watch(watch_id)

def list_watches(field_path: Optional[str] = None, 
                alert_level: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List all watches, optionally filtered.
    
    Args:
        field_path: Optional filter for field path
        alert_level: Optional filter for alert level
        
    Returns:
        List[Dict]: List of watch information dictionaries
    """
    monitor = get_field_monitor()
    return monitor.list_watches(field_path, alert_level)

def evaluate_watches(state: Dict[str, Any], 
                    node_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Evaluate all watches against the given state.
    
    Args:
        state: The state to evaluate watches against
        node_name: Optional name of the node that produced this state
        
    Returns:
        List[Dict]: List of triggered watch alert information
    """
    monitor = get_field_monitor()
    return monitor.evaluate_watches(state, node_name)

def get_monitor_statistics() -> Dict[str, Any]:
    """
    Get statistics about watch evaluations and triggers.
    
    Returns:
        Dict: Statistics about watch usage
    """
    monitor = get_field_monitor()
    return monitor.get_statistics()

def start_trace_session(run_id: Optional[str] = None) -> str:
    """
    Start a new trace session, resetting history and setting up profiling.
    
    Args:
        run_id: Optional identifier for this trace session/run
        
    Returns:
        The run ID (generated if not provided)
    """
    # Reset trace history
    reset_trace_history()
    
    # Start profiling if enabled
    profile_run_id = None
    if _enable_profiling:
        profile_run_id = start_profiling_run(run_id)
        trace_logger.info(f"Performance profiling started for run: {profile_run_id}")
    
    # Return the run ID (from profiling or generate a new one)
    if profile_run_id:
        return profile_run_id
    elif run_id:
        return run_id
    else:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"trace_{timestamp}"

def create_trace_summary() -> Dict[str, Any]:
    """
    Create a summary of the trace session.
    
    Returns:
        Dictionary with trace session summary
    """
    global _trace_history
    
    if not _trace_history:
        return {"error": "No trace history available"}
    
    # Get session ID
    session_id = get_trace_session()
    
    # Collect basic statistics
    nodes_count = len(_trace_history)
    successful_nodes = sum(1 for entry in _trace_history if entry.get("success", True))
    failed_nodes = nodes_count - successful_nodes
    
    # Calculate timing statistics
    durations = [entry.get("duration", 0) for entry in _trace_history]
    total_duration = sum(durations)
    avg_duration = total_duration / nodes_count if nodes_count > 0 else 0
    max_duration = max(durations) if durations else 0
    
    # Calculate first and last timestamp
    start_time = _trace_history[0].get("timestamp") if _trace_history else 0
    end_time = _trace_history[-1].get("timestamp") if _trace_history else 0
    
    # Get initial and final correlation IDs
    first_correlation_id = _trace_history[0].get("correlation_id", "") if _trace_history else ""
    last_correlation_id = _trace_history[-1].get("correlation_id", "") if _trace_history else ""
    
    # Create a list of node names in the order of execution
    execution_path = [entry.get("node", f"Node{i}") for i, entry in enumerate(_trace_history)]
    
    # Group by node type
    node_types = {}
    for entry in _trace_history:
        node_name = entry.get("node", "unknown")
        node_info = get_node_type(node_name)
        node_type = node_info.get("type", "unknown")
        node_types[node_type] = node_types.get(node_type, 0) + 1
    
    # Create the trace summary
    summary = {
        "session_id": session_id,
        "start_time": start_time,
        "end_time": end_time,
        "duration": total_duration,
        "correlation_ids": {
            "first": first_correlation_id,
            "last": last_correlation_id
        },
        "nodes": {
            "total": nodes_count,
            "successful": successful_nodes,
            "failed": failed_nodes,
            "types": node_types
        },
        "timing": {
            "total_duration": total_duration,
            "average_node_duration": avg_duration,
            "maximum_node_duration": max_duration
        },
        "execution_path": execution_path
    }
    
    # Add any errors detected
    errors = []
    for entry in _trace_history:
        if not entry.get("success", True) and "error" in entry:
            errors.append({
                "node": entry.get("node", "unknown"),
                "timestamp": entry.get("timestamp", 0),
                "error": entry["error"]
            })
    
    if errors:
        summary["errors"] = errors
    
    # Include state changes information if available
    state_changes_count = sum(1 for entry in _trace_history if "state_changes" in entry and entry["state_changes"])
    if state_changes_count > 0:
        summary["state_changes_detected"] = state_changes_count
    
    return summary

def end_trace_session() -> Dict[str, Any]:
    """
    End the current trace session and generate summary.
    
    Returns:
        Summary statistics for the trace session
    """
    # Get trace summary
    trace_summary = create_trace_summary()
    
    # End profiling if enabled
    profile_summary = {}
    if _enable_profiling:
        profile_summary = end_profiling_run()
        trace_logger.info("Performance profiling ended")
    
    # Combine summaries
    combined_summary = {
        "trace": trace_summary,
        "profile": profile_summary
    }
    
    return combined_summary

def generate_performance_report(include_graphs: bool = True) -> Dict[str, Any]:
    """
    Generate a comprehensive performance report based on the most recent trace session.
    
    Args:
        include_graphs: Whether to generate and save visualizations
        
    Returns:
        Performance report data
    """
    if not _enable_profiling:
        return {"error": "Performance profiling is not enabled"}
    
    from src.profiling import generate_performance_report as generate_report
    
    # Generate report from profiling data
    return generate_report(include_graphs=include_graphs)

def create_state_visualization(
    state: Dict[str, Any], 
    include_fields: Optional[List[str]] = None,
    exclude_fields: Optional[List[str]] = None,
    max_depth: int = 3,
    format_type: str = 'text'
) -> str:
    """
    Create a visualization of a state dictionary with selective field filtering.
    
    Args:
        state: The state dictionary to visualize
        include_fields: Only include these top-level fields (None for all)
        exclude_fields: Exclude these fields from visualization
        max_depth: Maximum depth for nested objects
        format_type: Output format ('text', 'json', 'tree')
        
    Returns:
        Formatted visualization as a string
    """
    # Apply field filtering
    filtered_state = _filter_fields_for_visualization(
        state, include_fields, exclude_fields
    )
    
    # Convert to appropriate format
    if format_type.lower() == 'json':
        # Indented JSON format
        return json.dumps(filtered_state, indent=2, default=str)
    
    elif format_type.lower() == 'tree':
        # Tree-like visualization
        return _create_tree_visualization(filtered_state, max_depth)
    
    else:
        # Default text format with custom formatting
        return _create_text_visualization(filtered_state, max_depth)

def _filter_fields_for_visualization(
    state: Dict[str, Any],
    include_fields: Optional[List[str]] = None,
    exclude_fields: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Filter state dictionary based on include/exclude field lists.
    
    Args:
        state: The state dictionary to filter
        include_fields: Only include these top-level fields (None for all)
        exclude_fields: Exclude these fields from visualization
        
    Returns:
        Filtered state dictionary
    """
    if not isinstance(state, dict):
        return state
        
    # Create a filtered copy
    filtered = {}
    
    # If include_fields is specified, only include those fields
    if include_fields:
        for field in include_fields:
            if field in state:
                filtered[field] = state[field]
    else:
        # Otherwise start with all fields
        filtered = state.copy()
    
    # Remove excluded fields
    if exclude_fields:
        for field in exclude_fields:
            if field in filtered:
                del filtered[field]
    
    return filtered

def _create_text_visualization(state: Dict[str, Any], max_depth: int = 3, current_depth: int = 0, indent: str = "") -> str:
    """
    Create a formatted text visualization of a state dictionary.
    
    Args:
        state: The state dictionary to visualize
        max_depth: Maximum depth for nested objects
        current_depth: Current recursion depth
        indent: Current indentation string
        
    Returns:
        Formatted text visualization
    """
    if current_depth > max_depth:
        return f"{indent}... (max depth reached)\n"
        
    if not isinstance(state, dict):
        if isinstance(state, list):
            if not state:
                return f"{indent}[]\n"
            elif len(state) > 5:
                return f"{indent}[List with {len(state)} items]\n"
            else:
                result = f"{indent}[\n"
                for item in state:
                    result += f"{indent}  {str(item)}\n"
                result += f"{indent}]\n"
                return result
        elif isinstance(state, str) and len(state) > 100:
            return f"{indent}\"{state[:100]}...\"\n"
        else:
            return f"{indent}{state}\n"
    
    if not state:
        return f"{indent}{{}}\n"
        
    result = ""
    
    # Get the longest key for alignment
    max_key_length = max([len(str(k)) for k in state.keys()]) if state else 0
    
    for key, value in state.items():
        # Format key with padding for alignment
        formatted_key = f"{str(key):<{max_key_length}}"
        
        if isinstance(value, dict):
            result += f"{indent}{formatted_key}: {{\n"
            result += _create_text_visualization(value, max_depth, current_depth + 1, indent + "  ")
            result += f"{indent}}}\n"
        elif isinstance(value, list):
            if not value:
                result += f"{indent}{formatted_key}: []\n"
            elif len(value) > 5:
                result += f"{indent}{formatted_key}: [List with {len(value)} items]\n"
            else:
                result += f"{indent}{formatted_key}: [\n"
                for item in value:
                    if isinstance(item, dict):
                        result += f"{indent}  {{\n"
                        result += _create_text_visualization(item, max_depth, current_depth + 1, indent + "    ")
                        result += f"{indent}  }}\n"
                    else:
                        result += f"{indent}  {str(item)}\n"
                result += f"{indent}]\n"
        elif isinstance(value, str) and len(value) > 100:
            result += f"{indent}{formatted_key}: \"{value[:100]}...\"\n"
        else:
            result += f"{indent}{formatted_key}: {value}\n"
    
    return result

def _create_tree_visualization(state: Dict[str, Any], max_depth: int = 3, current_depth: int = 0, prefix: str = "") -> str:
    """
    Create a tree-like visualization of a state dictionary.
    
    Args:
        state: The state dictionary to visualize
        max_depth: Maximum depth for nested objects
        current_depth: Current recursion depth
        prefix: Current line prefix
        
    Returns:
        Tree-like visualization string
    """
    if current_depth > max_depth:
        return f"{prefix}... (max depth reached)\n"
        
    if not isinstance(state, dict):
        if isinstance(state, list):
            if not state:
                return f"{prefix}[]\n"
            elif len(state) > 5:
                return f"{prefix}[List with {len(state)} items]\n"
            else:
                result = f"{prefix}[\n"
                for i, item in enumerate(state):
                    # Use different symbols for last item
                    if i == len(state) - 1:
                        item_prefix = f"{prefix}└── "
                        new_prefix = f"{prefix}    "
                    else:
                        item_prefix = f"{prefix}├── "
                        new_prefix = f"{prefix}│   "
                        
                    if isinstance(item, dict):
                        result += f"{item_prefix}{{\n"
                        result += _create_tree_visualization(item, max_depth, current_depth + 1, new_prefix)
                    else:
                        result += f"{item_prefix}{str(item)}\n"
                return result
        elif isinstance(state, str) and len(state) > 100:
            return f"{prefix}\"{state[:100]}...\"\n"
        else:
            return f"{prefix}{state}\n"
    
    if not state:
        return f"{prefix}{{}}\n"
        
    result = ""
    keys = list(state.keys())
    
    for i, key in enumerate(keys):
        value = state[key]
        
        # Use different symbols for last item
        if i == len(keys) - 1:
            key_prefix = f"{prefix}└── "
            new_prefix = f"{prefix}    "
        else:
            key_prefix = f"{prefix}├── "
            new_prefix = f"{prefix}│   "
        
        if isinstance(value, dict):
            result += f"{key_prefix}{key}: {{\n"
            result += _create_tree_visualization(value, max_depth, current_depth + 1, new_prefix)
        elif isinstance(value, list):
            if not value:
                result += f"{key_prefix}{key}: []\n"
            elif len(value) > 5:
                result += f"{key_prefix}{key}: [List with {len(value)} items]\n"
            else:
                result += f"{key_prefix}{key}: [\n"
                for j, item in enumerate(value):
                    # Use different symbols for last item in list
                    if j == len(value) - 1:
                        item_prefix = f"{new_prefix}└── "
                    else:
                        item_prefix = f"{new_prefix}├── "
                        
                    if isinstance(item, dict):
                        result += f"{item_prefix}{{\n"
                        result += _create_tree_visualization(item, max_depth, current_depth + 2, new_prefix + "│   ")
                    else:
                        result += f"{item_prefix}{str(item)}\n"
                result += f"{new_prefix}]\n"
        elif isinstance(value, str) and len(value) > 100:
            result += f"{key_prefix}{key}: \"{value[:100]}...\"\n"
        else:
            result += f"{key_prefix}{key}: {value}\n"
    
    return result 

def set_trace_enabled(enabled: bool) -> None:
    """
    Enable or disable tracing globally.
    
    Args:
        enabled: Whether to enable tracing
    """
    global _trace_enabled
    _trace_enabled = enabled
    trace_logger.info(f"Tracing {'enabled' if enabled else 'disabled'}")

def is_trace_enabled() -> bool:
    """
    Check if tracing is enabled.
    
    Returns:
        True if tracing is enabled, False otherwise
    """
    return _trace_enabled

def get_trace_history() -> List[Dict[str, Any]]:
    """
    Get the current trace history.
    
    Returns:
        List of trace entries
    """
    return _trace_history.copy()

def clear_trace_history() -> None:
    """
    Clear the trace history.
    """
    global _trace_history
    _trace_history = []
    trace_logger.info("Trace history cleared")

def add_to_trace_history(entry: Dict[str, Any]) -> None:
    """
    Add an entry to the trace history.
    
    Args:
        entry: The trace entry to add
    """
    global _trace_history
    
    if not is_trace_enabled():
        return
        
    _trace_history.append(entry)