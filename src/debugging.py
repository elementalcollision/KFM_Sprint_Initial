"""
Debugging utilities for LangGraph applications.

This module provides utilities for debugging LangGraph applications
by tracking state changes, comparing states, and tracing execution.
"""

import traceback
import logging
import json
import sys
import os
import uuid
import datetime
import builtins
from typing import Dict, Any, Optional, List, Callable, TypeVar, Set, Tuple
from src.logger import setup_logger, set_log_level, get_log_level
from src.state_types import KFMAgentState
from src.tracing import (
    get_state_history_tracker,
    save_state_snapshot,
    get_state_timeline,
    search_state_history,
    watch_field,
    remove_watch,
    clear_watches,
    list_watches,
    get_monitor_statistics,
    evaluate_watches
)

# Module exports for external use
__all__ = [
    "configure_debug_level",
    "debug_node_execution",
    "diff_states",
    "visualize_diff",
    "wrap_node_for_debug",
    "debug_graph_execution",
    "extract_subgraph_for_debugging",
    "step_through_execution",
    "step_through_execution_with_history",
    "create_state_checkpoint",
    "compare_with_checkpoint",
    "show_execution_timeline",
    "find_states_with_value",
    "time_travel_to_state",
    # Breakpoint functionality
    "get_breakpoint_manager",
    "set_breakpoint",
    "clear_breakpoint",
    "clear_node_breakpoints",
    "clear_all_breakpoints",
    "enable_breakpoint",
    "disable_breakpoint",
    "get_breakpoint",
    "list_breakpoints",
    "run_with_breakpoints",
    "interactive_debug",
    "step_forward",
    "step_backward",
    "run_to_node",
    "run_to_condition",
    # Monitoring functionality
    "monitor_field",
    "monitor_value_change",
    "monitor_threshold",
    "monitor_pattern_match",
    "monitor_state_condition",
    "stop_monitoring",
    "stop_all_monitoring",
    "get_active_monitors",
    "get_monitoring_statistics"
]

# Setup logger for the debugging module - use enhanced logger configuration
debug_logger = setup_logger('src.debugging')

# Constants for diff visualization
DIFF_SYMBOLS = {
    'added': '+',
    'removed': '-',
    'modified': '~',
    'unchanged': ' '
}

# ANSI color codes for visual diff output
DIFF_COLORS = {
    'added': '\033[92m',     # Green
    'removed': '\033[91m',   # Red
    'modified': '\033[93m',  # Yellow
    'unchanged': '\033[0m',  # Default
    'reset': '\033[0m'       # Reset
}

# Type variable for state type
StateT = TypeVar('StateT', bound=Dict[str, Any])

class BreakpointManager:
    """
    Manages breakpoints for nodes in the graph execution.
    
    This class provides functionality for:
    - Setting and clearing breakpoints on specific nodes
    - Enabling and disabling breakpoints
    - Checking if a node has breakpoints
    - Evaluating conditional breakpoints
    - Persisting breakpoint configurations
    """
    
    def __init__(self, breakpoint_dir: str = "logs/breakpoints"):
        """
        Initialize the breakpoint manager.
        
        Args:
            breakpoint_dir: Directory to store breakpoint configurations
        """
        self.breakpoints = {}  # node_name -> [breakpoint_info, ...]
        self.breakpoint_dir = breakpoint_dir
        
        # Create breakpoint directory if it doesn't exist
        if not os.path.exists(breakpoint_dir):
            os.makedirs(breakpoint_dir, exist_ok=True)
            
        self.load_breakpoints()
        debug_logger.info("Breakpoint manager initialized")
    
    def set_breakpoint(self, node_name: str, condition: Optional[str] = None, 
                     enabled: bool = True, description: Optional[str] = None) -> str:
        """
        Set a breakpoint on a node.
        
        Args:
            node_name: Name of the node to set the breakpoint on
            condition: Optional condition expression for conditional breakpoints
            enabled: Whether the breakpoint is enabled
            description: Optional description of the breakpoint
            
        Returns:
            ID of the created breakpoint
        """
        breakpoint_id = str(uuid.uuid4())
        
        # Create breakpoint info
        breakpoint_info = {
            "id": breakpoint_id,
            "node_name": node_name,
            "condition": condition,
            "enabled": enabled,
            "description": description,
            "created_at": datetime.datetime.now().isoformat(),
            "hit_count": 0
        }
        
        # Add to dict
        if node_name not in self.breakpoints:
            self.breakpoints[node_name] = []
        self.breakpoints[node_name].append(breakpoint_info)
        
        debug_logger.info(f"Set breakpoint on node '{node_name}'{' (disabled)' if not enabled else ''}"
                        f"{f' with condition: {condition}' if condition else ''}")
        
        # Save breakpoints
        self.save_breakpoints()
        
        return breakpoint_id
    
    def clear_breakpoint(self, breakpoint_id: str) -> bool:
        """
        Clear a breakpoint by ID.
        
        Args:
            breakpoint_id: ID of the breakpoint to clear
            
        Returns:
            True if the breakpoint was found and cleared, False otherwise
        """
        for node_name, breakpoints in self.breakpoints.items():
            for i, bp in enumerate(breakpoints):
                if bp["id"] == breakpoint_id:
                    # Remove the breakpoint
                    self.breakpoints[node_name].pop(i)
                    
                    # If no more breakpoints for this node, remove the key
                    if not self.breakpoints[node_name]:
                        del self.breakpoints[node_name]
                    
                    debug_logger.info(f"Cleared breakpoint {breakpoint_id} on node '{node_name}'")
                    
                    # Save breakpoints
                    self.save_breakpoints()
                    
                    return True
        
        debug_logger.warning(f"No breakpoint found with ID {breakpoint_id}")
        return False
    
    def clear_node_breakpoints(self, node_name: str) -> int:
        """
        Clear all breakpoints on a node.
        
        Args:
            node_name: Name of the node to clear breakpoints from
            
        Returns:
            Number of breakpoints cleared
        """
        if node_name not in self.breakpoints:
            debug_logger.warning(f"No breakpoints found on node '{node_name}'")
            return 0
        
        count = len(self.breakpoints[node_name])
        del self.breakpoints[node_name]
        
        debug_logger.info(f"Cleared {count} breakpoint(s) on node '{node_name}'")
        
        # Save breakpoints
        self.save_breakpoints()
        
        return count
    
    def clear_all_breakpoints(self) -> int:
        """
        Clear all breakpoints.
        
        Returns:
            Number of breakpoints cleared
        """
        count = sum(len(breakpoints) for breakpoints in self.breakpoints.values())
        self.breakpoints = {}
        
        debug_logger.info(f"Cleared all breakpoints ({count} total)")
        
        # Save breakpoints
        self.save_breakpoints()
        
        return count
    
    def enable_breakpoint(self, breakpoint_id: str) -> bool:
        """
        Enable a breakpoint.
        
        Args:
            breakpoint_id: ID of the breakpoint to enable
            
        Returns:
            True if the breakpoint was found and enabled, False otherwise
        """
        for node_name, breakpoints in self.breakpoints.items():
            for bp in breakpoints:
                if bp["id"] == breakpoint_id:
                    if bp["enabled"]:
                        debug_logger.info(f"Breakpoint {breakpoint_id} already enabled")
                        return True
                    
                    bp["enabled"] = True
                    debug_logger.info(f"Enabled breakpoint {breakpoint_id} on node '{node_name}'")
                    
                    # Save breakpoints
                    self.save_breakpoints()
                    
                    return True
        
        debug_logger.warning(f"No breakpoint found with ID {breakpoint_id}")
        return False
    
    def disable_breakpoint(self, breakpoint_id: str) -> bool:
        """
        Disable a breakpoint.
        
        Args:
            breakpoint_id: ID of the breakpoint to disable
            
        Returns:
            True if the breakpoint was found and disabled, False otherwise
        """
        for node_name, breakpoints in self.breakpoints.items():
            for bp in breakpoints:
                if bp["id"] == breakpoint_id:
                    if not bp["enabled"]:
                        debug_logger.info(f"Breakpoint {breakpoint_id} already disabled")
                        return True
                    
                    bp["enabled"] = False
                    debug_logger.info(f"Disabled breakpoint {breakpoint_id} on node '{node_name}'")
                    
                    # Save breakpoints
                    self.save_breakpoints()
                    
                    return True
        
        debug_logger.warning(f"No breakpoint found with ID {breakpoint_id}")
        return False
    
    def get_breakpoint(self, breakpoint_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a breakpoint by ID.
        
        Args:
            breakpoint_id: ID of the breakpoint to get
            
        Returns:
            Breakpoint info or None if not found
        """
        for breakpoints in self.breakpoints.values():
            for bp in breakpoints:
                if bp["id"] == breakpoint_id:
                    return bp.copy()
        
        return None
    
    def list_breakpoints(self, node_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all breakpoints, optionally filtered by node.
        
        Args:
            node_name: Optional node name to filter by
            
        Returns:
            List of breakpoint info dictionaries
        """
        result = []
        
        if node_name:
            # List breakpoints for just this node
            if node_name in self.breakpoints:
                result.extend(bp.copy() for bp in self.breakpoints[node_name])
        else:
            # List all breakpoints
            for node_breakpoints in self.breakpoints.values():
                result.extend(bp.copy() for bp in node_breakpoints)
        
        return result
    
    def has_breakpoint(self, node_name: str) -> bool:
        """
        Check if a node has any enabled breakpoints.
        
        Args:
            node_name: Name of the node to check
            
        Returns:
            True if the node has at least one enabled breakpoint, False otherwise
        """
        if node_name not in self.breakpoints:
            return False
        
        # Check if any breakpoints are enabled
        return any(bp["enabled"] for bp in self.breakpoints[node_name])
    
    def check_breakpoints(self, node_name: str, state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Check if any breakpoints should be triggered for a node.
        
        Args:
            node_name: Name of the node to check
            state: Current state to evaluate conditions against
            
        Returns:
            Breakpoint info if a breakpoint should be triggered, None otherwise
        """
        if node_name not in self.breakpoints:
            return None
        
        for bp in self.breakpoints[node_name]:
            if not bp["enabled"]:
                continue
                
            # Unconditional breakpoint or condition evaluates to True
            if not bp["condition"] or self._evaluate_condition(bp["condition"], state):
                # Increment hit count
                bp["hit_count"] += 1
                
                # Save breakpoints to update hit count
                self.save_breakpoints()
                
                return bp.copy()
        
        return None
    
    def _evaluate_condition(self, condition: str, state: Dict[str, Any]) -> bool:
        """
        Evaluate a condition against the current state.
        
        Args:
            condition: Condition expression
            state: Current state to evaluate against
            
        Returns:
            True if the condition evaluates to True, False otherwise
        """
        try:
            # Create a safe evaluation environment with access to state fields
            local_env = {"state": state}
            
            # Add helper functions for state access
            local_env["get"] = lambda path, default=None: self._get_nested_value(state, path, default)
            
            # Add math functions
            for name in ['abs', 'max', 'min', 'sum', 'len', 'round']:
                local_env[name] = getattr(builtins, name)
            
            # Evaluate the condition
            return bool(eval(condition, {"__builtins__": {}}, local_env))
        except Exception as e:
            debug_logger.error(f"Error evaluating breakpoint condition: {str(e)}")
            return False
    
    def _get_nested_value(self, obj: Dict[str, Any], path: str, default: Any = None) -> Any:
        """
        Get a nested value from an object using dot notation.
        
        Args:
            obj: Object to get value from
            path: Dot notation path (e.g., "user.preferences.theme")
            default: Default value to return if path not found
            
        Returns:
            Value at the path or default if not found
        """
        keys = path.split(".")
        current = obj
        
        try:
            for key in keys:
                # Handle list indices
                if key.endswith("]") and "[" in key:
                    # Split into key and index
                    base_key, index_str = key.split("[")
                    index = int(index_str.rstrip("]"))
                    
                    # Get the list from the dict, then get the item at index
                    current = current[base_key][index]
                else:
                    current = current[key]
            return current
        except (KeyError, IndexError, TypeError):
            return default
    
    def save_breakpoints(self) -> bool:
        """
        Save breakpoints to disk.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create breakpoints file
            breakpoints_file = os.path.join(self.breakpoint_dir, "breakpoints.json")
            
            with open(breakpoints_file, "w") as f:
                json.dump(self.breakpoints, f, indent=2)
                
            debug_logger.debug(f"Saved breakpoints to {breakpoints_file}")
            return True
        except Exception as e:
            debug_logger.error(f"Error saving breakpoints: {str(e)}")
            return False
    
    def load_breakpoints(self) -> bool:
        """
        Load breakpoints from disk.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if breakpoints file exists
            breakpoints_file = os.path.join(self.breakpoint_dir, "breakpoints.json")
            
            if not os.path.exists(breakpoints_file):
                debug_logger.debug("No saved breakpoints found")
                return False
                
            with open(breakpoints_file, "r") as f:
                self.breakpoints = json.load(f)
                
            debug_logger.info(f"Loaded breakpoints from {breakpoints_file}")
            return True
        except Exception as e:
            debug_logger.error(f"Error loading breakpoints: {str(e)}")
            return False

# Global instance
_breakpoint_manager = None

def get_breakpoint_manager() -> BreakpointManager:
    """
    Get the breakpoint manager instance.
    
    Returns:
        The BreakpointManager instance
    """
    global _breakpoint_manager
    
    if _breakpoint_manager is None:
        _breakpoint_manager = BreakpointManager()
        
    return _breakpoint_manager

# Breakpoint management functions

def set_breakpoint(node_name: str, condition: Optional[str] = None, 
                 enabled: bool = True, description: Optional[str] = None) -> str:
    """
    Set a breakpoint on a node.
    
    Args:
        node_name: Name of the node to set the breakpoint on
        condition: Optional condition expression for conditional breakpoints
        enabled: Whether the breakpoint is enabled
        description: Optional description of the breakpoint
        
    Returns:
        ID of the created breakpoint
    """
    manager = get_breakpoint_manager()
    return manager.set_breakpoint(node_name, condition, enabled, description)

def clear_breakpoint(breakpoint_id: str) -> bool:
    """
    Clear a breakpoint by ID.
    
    Args:
        breakpoint_id: ID of the breakpoint to clear
        
    Returns:
        True if the breakpoint was found and cleared, False otherwise
    """
    manager = get_breakpoint_manager()
    return manager.clear_breakpoint(breakpoint_id)

def clear_node_breakpoints(node_name: str) -> int:
    """
    Clear all breakpoints on a node.
    
    Args:
        node_name: Name of the node to clear breakpoints from
        
    Returns:
        Number of breakpoints cleared
    """
    manager = get_breakpoint_manager()
    return manager.clear_node_breakpoints(node_name)

def clear_all_breakpoints() -> int:
    """
    Clear all breakpoints.
    
    Returns:
        Number of breakpoints cleared
    """
    manager = get_breakpoint_manager()
    return manager.clear_all_breakpoints()

def enable_breakpoint(breakpoint_id: str) -> bool:
    """
    Enable a breakpoint.
    
    Args:
        breakpoint_id: ID of the breakpoint to enable
        
    Returns:
        True if the breakpoint was found and enabled, False otherwise
    """
    manager = get_breakpoint_manager()
    return manager.enable_breakpoint(breakpoint_id)

def disable_breakpoint(breakpoint_id: str) -> bool:
    """
    Disable a breakpoint.
    
    Args:
        breakpoint_id: ID of the breakpoint to disable
        
    Returns:
        True if the breakpoint was found and disabled, False otherwise
    """
    manager = get_breakpoint_manager()
    return manager.disable_breakpoint(breakpoint_id)

def get_breakpoint(breakpoint_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a breakpoint by ID.
    
    Args:
        breakpoint_id: ID of the breakpoint to get
        
    Returns:
        Breakpoint info or None if not found
    """
    manager = get_breakpoint_manager()
    return manager.get_breakpoint(breakpoint_id)

def list_breakpoints(node_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List all breakpoints, optionally filtered by node.
    
    Args:
        node_name: Optional node name to filter by
        
    Returns:
        List of breakpoint info dictionaries
    """
    manager = get_breakpoint_manager()
    return manager.list_breakpoints(node_name)

def configure_debug_level(level: str) -> None:
    """Configure the debug logger level.
    
    Args:
        level (str): Logging level ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
    """
    set_log_level('src.debugging', level)
    debug_logger.info(f"Debug logging level set to {level}")

def debug_node_execution(node_name: str, state_before: StateT, state_after: StateT) -> None:
    """Debug helper to track state changes in a node.
    
    Args:
        node_name (str): Name of the node being debugged
        state_before (Dict): State before node execution
        state_after (Dict): State after node execution
    """
    debug_logger.info(f"\n--- DEBUG: {node_name} ---")
    
    # Convert to dictionaries if they are KFMAgentState objects
    if not isinstance(state_before, dict):
        state_before_dict = state_before.to_dict() if hasattr(state_before, 'to_dict') else vars(state_before)
    else:
        state_before_dict = state_before
        
    if not isinstance(state_after, dict):
        state_after_dict = state_after.to_dict() if hasattr(state_after, 'to_dict') else vars(state_after)
    else:
        state_after_dict = state_after
    
    # Use debug level for detailed state information
    debug_logger.debug(f"State BEFORE: {json.dumps(state_before_dict, indent=2)}")
    debug_logger.debug(f"State AFTER: {json.dumps(state_after_dict, indent=2)}")
    
    # Use enhanced diff_states with 'detailed' mode
    diff_result = diff_states(state_before_dict, state_after_dict, mode='detailed')
    
    # Use info level to show the changes
    if diff_result['stats']['added'] + diff_result['stats']['removed'] + diff_result['stats']['modified'] > 0:
        debug_logger.info(f"Changes: {diff_result['summary']}")
        debug_logger.info(diff_result['visualization'])
    else:
        debug_logger.info("No state changes detected")
        
    debug_logger.info("-------------------\n")

def diff_states(state1: Dict[str, Any], state2: Dict[str, Any], 
                mode: str = 'basic', max_depth: int = 10, 
                use_colors: bool = True, show_unchanged: bool = False) -> Dict[str, Any]:
    """Compare two states and return differences with enhanced visualization.
    
    Args:
        state1 (Dict): First state to compare (before state)
        state2 (Dict): Second state to compare (after state)
        mode (str): Comparison mode - 'basic', 'detailed', or 'comprehensive'
        max_depth (int): Maximum depth for recursive comparison
        use_colors (bool): Whether to use colors in the output
        show_unchanged (bool): Whether to include unchanged fields in the output
        
    Returns:
        Dict[str, Any]: Dictionary containing structured diff information
    """
    # Determine if the terminal supports colors
    use_colors = use_colors and hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    
    # Create a root diff result
    result = {
        'changes': {},
        'stats': {
            'added': 0,
            'removed': 0,
            'modified': 0,
            'unchanged': 0
        }
    }
    
    # Recursively compare the states
    _compare_objects(state1, state2, result['changes'], '', 0, max_depth, mode, result['stats'])
    
    # Add human-readable summary
    total_changes = result['stats']['added'] + result['stats']['removed'] + result['stats']['modified']
    result['summary'] = f"Found {total_changes} differences: {result['stats']['added']} additions, " \
                       f"{result['stats']['removed']} removals, {result['stats']['modified']} modifications"
    
    # Generate visualization if requested
    if mode != 'basic':
        result['visualization'] = _generate_diff_visualization(
            result['changes'], use_colors, show_unchanged)
    
    return result

def _compare_objects(obj1: Any, obj2: Any, changes: Dict[str, Any], path: str, 
                   depth: int, max_depth: int, mode: str, stats: Dict[str, int]) -> None:
    """Recursively compare two objects and record the differences.
    
    Args:
        obj1: First object to compare
        obj2: Second object to compare
        changes: Dictionary to store changes
        path: Current path in the object tree
        depth: Current depth in the recursion
        max_depth: Maximum depth for recursion
        mode: Comparison mode
        stats: Statistics to update
    """
    # Check if we've reached the maximum depth
    if depth >= max_depth:
        if obj1 != obj2:
            changes[path] = {
                'type': 'modified',
                'before': _safe_truncate(obj1),
                'after': _safe_truncate(obj2),
                'note': 'Truncated at max depth'
            }
            stats['modified'] += 1
        return
    
    # Handle the case where values are None
    if obj1 is None and obj2 is None:
        return
    
    # Handle different types
    if type(obj1) != type(obj2):
        changes[path] = {
            'type': 'modified',
            'before': _safe_truncate(obj1),
            'after': _safe_truncate(obj2),
            'note': f'Type changed: {type(obj1).__name__} -> {type(obj2).__name__}'
        }
        stats['modified'] += 1
        return
    
    # Handle dictionaries
    if isinstance(obj1, dict) and isinstance(obj2, dict):
        _compare_dicts(obj1, obj2, changes, path, depth, max_depth, mode, stats)
    
    # Handle lists
    elif isinstance(obj1, list) and isinstance(obj2, list):
        _compare_lists(obj1, obj2, changes, path, depth, max_depth, mode, stats)
    
    # Handle sets
    elif isinstance(obj1, set) and isinstance(obj2, set):
        _compare_sets(obj1, obj2, changes, path, depth, max_depth, mode, stats)
    
    # Handle primitive values or unsupported collections
    else:
        if obj1 != obj2:
            changes[path] = {
                'type': 'modified',
                'before': _safe_truncate(obj1),
                'after': _safe_truncate(obj2)
            }
            stats['modified'] += 1

def _compare_dicts(dict1: Dict[str, Any], dict2: Dict[str, Any], changes: Dict[str, Any], 
                  path: str, depth: int, max_depth: int, mode: str, stats: Dict[str, int]) -> None:
    """Compare two dictionaries and record the differences.
    
    Args:
        dict1: First dictionary to compare
        dict2: Second dictionary to compare
        changes: Dictionary to store changes
        path: Current path in the object tree
        depth: Current depth in the recursion
        max_depth: Maximum depth for recursion
        mode: Comparison mode
        stats: Statistics to update
    """
    # Get all keys from both dictionaries
    all_keys = set(dict1.keys()) | set(dict2.keys())
    
    for key in all_keys:
        # Construct the current path
        current_path = f"{path}.{key}" if path else key
        
        # Check if key exists in both dictionaries
        if key in dict1 and key in dict2:
            # Recursively compare values
            _compare_objects(dict1[key], dict2[key], changes, current_path, 
                           depth + 1, max_depth, mode, stats)
        
        # Key is in dict1 but not in dict2 (removed)
        elif key in dict1:
            changes[current_path] = {
                'type': 'removed',
                'before': _safe_truncate(dict1[key]),
                'after': None
            }
            stats['removed'] += 1
        
        # Key is in dict2 but not in dict1 (added)
        else:
            changes[current_path] = {
                'type': 'added',
                'before': None,
                'after': _safe_truncate(dict2[key])
            }
            stats['added'] += 1

def _compare_lists(list1: List[Any], list2: List[Any], changes: Dict[str, Any], 
                  path: str, depth: int, max_depth: int, mode: str, stats: Dict[str, int]) -> None:
    """Compare two lists and record the differences.
    
    Args:
        list1: First list to compare
        list2: Second list to compare
        changes: Dictionary to store changes
        path: Current path in the object tree
        depth: Current depth in the recursion
        max_depth: Maximum depth for recursion
        mode: Comparison mode
        stats: Statistics to update
    """
    # Special case: empty lists
    if not list1 and not list2:
        return
    
    # For 'basic' mode, just compare the lists directly
    if mode == 'basic':
        if list1 != list2:
            changes[path] = {
                'type': 'modified',
                'before': _safe_truncate(list1),
                'after': _safe_truncate(list2),
                'note': f'List lengths: {len(list1)} -> {len(list2)}'
            }
            stats['modified'] += 1
        return
    
    # For detailed modes, compare elements individually
    max_len = max(len(list1), len(list2))
    
    # Handle list length changes
    if len(list1) != len(list2):
        changes[f"{path}._length"] = {
            'type': 'modified',
            'before': len(list1),
            'after': len(list2),
            'note': 'List length changed'
        }
        stats['modified'] += 1
    
    # Compare each element
    for i in range(max_len):
        current_path = f"{path}[{i}]"
        
        # Element exists in both lists
        if i < len(list1) and i < len(list2):
            _compare_objects(list1[i], list2[i], changes, current_path, 
                           depth + 1, max_depth, mode, stats)
        
        # Element is in list1 but not in list2 (removed)
        elif i < len(list1):
            changes[current_path] = {
                'type': 'removed',
                'before': _safe_truncate(list1[i]),
                'after': None
            }
            stats['removed'] += 1
        
        # Element is in list2 but not in list1 (added)
        else:
            changes[current_path] = {
                'type': 'added',
                'before': None,
                'after': _safe_truncate(list2[i])
            }
            stats['added'] += 1

def _compare_sets(set1: Set[Any], set2: Set[Any], changes: Dict[str, Any], 
                 path: str, depth: int, max_depth: int, mode: str, stats: Dict[str, int]) -> None:
    """Compare two sets and record the differences.
    
    Args:
        set1: First set to compare
        set2: Second set to compare
        changes: Dictionary to store changes
        path: Current path in the object tree
        depth: Current depth in the recursion
        max_depth: Maximum depth for recursion
        mode: Comparison mode
        stats: Statistics to update
    """
    # For 'basic' mode or for complex element types, just compare the sets directly
    has_complex_elements = any(isinstance(x, (dict, list, set)) for x in (set1 | set2))
    
    if mode == 'basic' or has_complex_elements:
        if set1 != set2:
            changes[path] = {
                'type': 'modified',
                'before': _safe_truncate(sorted(set1) if len(set1) > 0 and isinstance(next(iter(set1)), type) and hasattr(next(iter(set1)), "__lt__") else set1),
                'after': _safe_truncate(sorted(set2) if len(set2) > 0 and isinstance(next(iter(set2)), type) and hasattr(next(iter(set2)), "__lt__") else set2),
                'note': f'Set sizes: {len(set1)} -> {len(set2)}'
            }
            stats['modified'] += 1
        return
    
    # For detailed modes, compare elements individually
    removed = set1 - set2
    added = set2 - set1
    
    # Handle set size changes
    if len(set1) != len(set2):
        changes[f"{path}._size"] = {
            'type': 'modified',
            'before': len(set1),
            'after': len(set2),
            'note': 'Set size changed'
        }
        stats['modified'] += 1
    
    # Handle removed elements
    if removed:
        changes[f"{path}._removed"] = {
            'type': 'removed',
            'before': _safe_truncate(sorted(removed) if all(hasattr(x, "__lt__") for x in removed) else list(removed)),
            'after': None,
            'note': f'Removed {len(removed)} elements'
        }
        stats['removed'] += 1
    
    # Handle added elements
    if added:
        changes[f"{path}._added"] = {
            'type': 'added',
            'before': None,
            'after': _safe_truncate(sorted(added) if all(hasattr(x, "__lt__") for x in added) else list(added)),
            'note': f'Added {len(added)} elements'
        }
        stats['added'] += 1

def _safe_truncate(obj: Any, max_len: int = 1000) -> Any:
    """Safely truncate an object for display.
    
    Args:
        obj: Object to truncate
        max_len: Maximum length for strings and collections
        
    Returns:
        Truncated version of the object
    """
    if obj is None:
        return None
    
    # Handle strings
    if isinstance(obj, str):
        if len(obj) > max_len:
            return obj[:max_len] + "... (truncated)"
        return obj
    
    # Handle lists
    if isinstance(obj, list):
        if len(obj) > max_len // 10:
            return obj[:max_len // 10] + [f"... ({len(obj) - (max_len // 10)} more items)"]
        return obj
    
    # Handle dictionaries
    if isinstance(obj, dict):
        if len(obj) > max_len // 20:
            truncated = {k: obj[k] for k in list(obj.keys())[:max_len // 20]}
            truncated['...'] = f"({len(obj) - (max_len // 20)} more items)"
            return truncated
        return obj
    
    # Handle sets
    if isinstance(obj, set):
        if len(obj) > max_len // 10:
            # Convert to list for truncation
            obj_list = list(obj)[:max_len // 10]
            obj_list.append(f"... ({len(obj) - (max_len // 10)} more items)")
            return obj_list
        return obj
    
    # Handle other types
    try:
        # Try to convert to string and truncate
        obj_str = str(obj)
        if len(obj_str) > max_len:
            return obj_str[:max_len] + "... (truncated)"
        return obj
    except:
        # If conversion fails, return a placeholder
        return f"<{type(obj).__name__} object>"

def _generate_diff_visualization(changes: Dict[str, Any], use_colors: bool = True, 
                                show_unchanged: bool = False) -> str:
    """Generate a human-readable visualization of the changes.
    
    Args:
        changes: Dictionary of changes from diff_states
        use_colors: Whether to use colors in the output
        show_unchanged: Whether to include unchanged fields
        
    Returns:
        str: Formatted visualization of the changes
    """
    lines = []
    lines.append("DIFF VISUALIZATION:")
    lines.append("===================")
    
    # Sort paths for consistent output
    sorted_paths = sorted(changes.keys())
    
    for path in sorted_paths:
        change = changes[path]
        change_type = change.get('type', 'unknown')
        
        # Skip unchanged fields if not requested
        if change_type == 'unchanged' and not show_unchanged:
            continue
        
        # Get the appropriate symbol and color
        symbol = DIFF_SYMBOLS.get(change_type, '?')
        color_start = DIFF_COLORS.get(change_type, '') if use_colors else ''
        color_reset = DIFF_COLORS['reset'] if use_colors else ''
        
        # Format the change
        if change_type == 'added':
            line = f"{color_start}{symbol} {path}: {change['after']}{color_reset}"
        elif change_type == 'removed':
            line = f"{color_start}{symbol} {path}: {change['before']}{color_reset}"
        elif change_type == 'modified':
            line = f"{color_start}{symbol} {path}: {change['before']} -> {change['after']}{color_reset}"
            if 'note' in change:
                line += f" ({change['note']})"
        else:
            line = f"{color_start}{symbol} {path}: {change.get('before', None)}{color_reset}"
        
        lines.append(line)
    
    # Add a summary line
    if not changes:
        lines.append("\nNo changes detected.")
    
    return "\n".join(lines)

def _format_diff_table(changes: Dict[str, Any], use_colors: bool = True) -> str:
    """Format changes as a table for clearer visualization.
    
    Args:
        changes: Dictionary of changes from diff_states
        use_colors: Whether to use colors in the output
        
    Returns:
        str: Table-formatted visualization of the changes
    """
    lines = []
    lines.append("┌───────┬────────────────────────┬─────────────────────┬─────────────────────┐")
    lines.append("│ Type  │ Path                   │ Before              │ After               │")
    lines.append("├───────┼────────────────────────┼─────────────────────┼─────────────────────┤")
    
    # Sort paths for consistent output
    sorted_paths = sorted(changes.keys())
    
    for path in sorted_paths:
        change = changes[path]
        change_type = change.get('type', 'unknown')
        
        # Get the appropriate symbol and color
        symbol = DIFF_SYMBOLS.get(change_type, '?')
        color_start = DIFF_COLORS.get(change_type, '') if use_colors else ''
        color_reset = DIFF_COLORS['reset'] if use_colors else ''
        
        # Format path, before, and after values
        path_str = path[:20] + '...' if len(path) > 23 else path
        before_str = str(change.get('before', ''))[:15] + '...' if len(str(change.get('before', ''))) > 18 else str(change.get('before', ''))
        after_str = str(change.get('after', ''))[:15] + '...' if len(str(change.get('after', ''))) > 18 else str(change.get('after', ''))
        
        # Construct the table row
        line = f"│ {color_start}{symbol}{change_type[0]}{color_reset} │ {path_str.ljust(22)} │ {before_str.ljust(19)} │ {after_str.ljust(19)} │"
        lines.append(line)
    
    lines.append("└───────┴────────────────────────┴─────────────────────┴─────────────────────┘")
    
    return "\n".join(lines)

def visualize_diff(diff_result: Dict[str, Any], format_type: str = 'standard', 
                  use_colors: bool = True) -> str:
    """Generate a visualization of diff results in various formats.
    
    Args:
        diff_result: Result from diff_states function
        format_type: Format type ('standard', 'table', 'json', etc.)
        use_colors: Whether to use colors in the output
        
    Returns:
        str: Formatted visualization of the diff
    """
    if 'visualization' in diff_result:
        # Use pre-generated visualization if available
        return diff_result['visualization']
    
    if format_type == 'table':
        return _format_diff_table(diff_result['changes'], use_colors)
    
    elif format_type == 'json':
        return json.dumps(diff_result, indent=2)
    
    else:  # standard format
        return _generate_diff_visualization(diff_result['changes'], use_colors)

def wrap_node_for_debug(node_func: Callable, node_name: str) -> Callable:
    """Wrap a node function to add debugging output.
    
    Args:
        node_func (Callable): Original node function
        node_name (str): Name of the node for debugging
        
    Returns:
        Callable: Wrapped node function with debugging
    """
    def wrapped_node(state: StateT, *args, **kwargs) -> StateT:
        debug_logger.info(f"Entering node: {node_name}")
        
        try:
            # Execute the original node function
            result = node_func(state, *args, **kwargs)
            
            # Debug the execution
            debug_node_execution(node_name, state, result)
            
            return result
        except Exception as e:
            debug_logger.error(f"Error in node {node_name}: {str(e)}")
            debug_logger.debug(traceback.format_exc())  # Use debug level for full traceback
            raise
    
    return wrapped_node

def debug_graph_execution(app, initial_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Debug helper to trace execution through the entire graph.
    
    Args:
        app: LangGraph application (compiled StateGraph)
        initial_state (Dict): Initial state to pass to the graph
        
    Returns:
        Optional[Dict]: Final state after execution or None if error occurs
    """
    debug_logger.info("Starting debug graph execution")
    debug_logger.debug(f"Initial state: {json.dumps(initial_state, indent=2)}")
    
    checkpoint_states = []
    
    try:
        # Create a checkpoint before execution
        checkpoint_states.append(("Initial", initial_state))
        
        # Execute the graph
        final_state = app.invoke(initial_state)
        
        # Create a checkpoint after execution
        checkpoint_states.append(("Final", final_state))
        
        debug_logger.info("Graph execution completed successfully")
        debug_logger.debug(f"Final state: {json.dumps(final_state, indent=2)}")
        
        # Show state differences using enhanced visualization
        if len(checkpoint_states) >= 2:
            debug_logger.info("\n=== State Changes During Execution ===")
            start_state = checkpoint_states[0][1]
            end_state = checkpoint_states[-1][1]
            
            # Generate detailed diff with visualization
            diff_result = diff_states(start_state, end_state, mode='comprehensive')
            debug_logger.info(f"Summary: {diff_result['summary']}")
            debug_logger.info(diff_result['visualization'])
            debug_logger.info("=====================================")
        
        return final_state
    except Exception as e:
        debug_logger.error(f"Error during graph execution: {e}")
        debug_logger.debug(traceback.format_exc())  # Use debug level for full traceback
        return None
    finally:
        # Print checkpoint states
        if checkpoint_states:
            debug_logger.info("\n=== Checkpoint States ===")
            for i, (name, state) in enumerate(checkpoint_states):
                debug_logger.info(f"\nCheckpoint {i}: {name}")
                debug_logger.debug(f"{json.dumps(state, indent=2)}")  # Use debug level for full state
                
                # Show diffs between consecutive checkpoints
                if i > 0:
                    prev_name, prev_state = checkpoint_states[i-1]
                    debug_logger.info(f"\nChanges from {prev_name} to {name}:")
                    
                    # Generate diff with visualization
                    diff_result = diff_states(prev_state, state, mode='detailed')
                    if diff_result['stats']['added'] + diff_result['stats']['removed'] + diff_result['stats']['modified'] > 0:
                        debug_logger.info(f"Summary: {diff_result['summary']}")
                        debug_logger.info(diff_result['visualization'])
                    else:
                        debug_logger.info("No state changes detected")
                    
            debug_logger.info("========================")

def extract_subgraph_for_debugging(app, nodes_to_include: List[str]):
    """Extract a subgraph from a LangGraph application for targeted debugging.
    
    Args:
        app: LangGraph application (compiled StateGraph)
        nodes_to_include (List[str]): Names of nodes to include in the subgraph
        
    Returns:
        A subgraph containing only the specified nodes, for targeted debugging
    """
    debug_logger.info(f"Extracting subgraph with nodes: {nodes_to_include}")
    
    try:
        # This is a placeholder as actual implementation depends on LangGraph internals
        debug_logger.warning("Subgraph extraction not fully implemented - depends on LangGraph internals")
        
        # In a real implementation, we would:
        # 1. Extract the nodes from the original graph
        # 2. Create a new graph with just those nodes
        # 3. Connect the nodes as they were in the original graph
        # 4. Return the new subgraph
        
        return None
    except Exception as e:
        debug_logger.error(f"Error extracting subgraph: {e}")
        debug_logger.debug(traceback.format_exc())  # Use debug level for full traceback
        return None

def step_through_execution(app, initial_state: Dict[str, Any], 
                           step_callback: Optional[Callable] = None) -> Optional[Dict[str, Any]]:
    """Step-by-step execution of the graph with manual intervention.
    
    Args:
        app: LangGraph application (compiled StateGraph)
        initial_state (Dict): Initial state to pass to the graph
        step_callback (Callable): Optional callback to call after each step
        
    Returns:
        Optional[Dict]: Final state after execution or None if error occurs
    """
    debug_logger.info("Starting step-by-step execution")
    debug_logger.debug(f"Initial state: {json.dumps(initial_state, indent=2)}")
    
    # Track states at each step for visualization
    step_states = [("Initial", initial_state)]
    current_state = initial_state
    
    # Note: This is a placeholder as the actual implementation would require
    # deeper integration with LangGraph internals to pause between nodes
    
    debug_logger.warning("Step-through execution not fully implemented - depends on LangGraph internals")
    
    # In a real implementation, we would:
    # 1. Access the graph's nodes and edges
    # 2. Execute nodes one by one
    # 3. Allow examination of state between nodes
    # 4. Optionally allow state modification between nodes
    
    try:
        # Fallback to normal execution
        final_state = app.invoke(initial_state)
        
        # Add final state to steps
        step_states.append(("Final", final_state))
        
        # Show diffs between initial and final states
        debug_logger.info("\n=== Step-by-Step State Changes ===")
        
        if len(step_states) >= 2:
            initial_name, initial_step_state = step_states[0]
            final_name, final_step_state = step_states[-1]
            
            debug_logger.info(f"\nChanges from {initial_name} to {final_name}:")
            
            # Generate comprehensive diff with visualization
            diff_result = diff_states(initial_step_state, final_step_state, mode='comprehensive')
            debug_logger.info(f"Summary: {diff_result['summary']}")
            debug_logger.info(visualize_diff(diff_result, format_type='table'))
        
        debug_logger.info("==================================")
        
        return final_state
    except Exception as e:
        debug_logger.error(f"Error during step-through execution: {e}")
        debug_logger.debug(traceback.format_exc())
        return None

# Add new functions to integrate with state history tracking

def create_state_checkpoint(state: Dict[str, Any], label: str, 
                          category: Optional[str] = None, 
                          description: Optional[str] = None) -> str:
    """
    Create a named checkpoint of the current state that can be referenced later.
    
    Args:
        state (Dict): State to checkpoint
        label (str): Descriptive label for the checkpoint
        category (str, optional): Category for organizing checkpoints
        description (str, optional): Detailed description of the checkpoint
        
    Returns:
        str: Unique ID of the checkpoint for future reference
    """
    checkpoint_id = save_state_snapshot(state, label, category, description)
    debug_logger.info(f"Created state checkpoint '{label}' with ID {checkpoint_id}")
    return checkpoint_id

def compare_with_checkpoint(current_state: Dict[str, Any], checkpoint_id: str, 
                          mode: str = 'detailed') -> Dict[str, Any]:
    """
    Compare the current state with a previously saved checkpoint.
    
    Args:
        current_state (Dict): Current state to compare
        checkpoint_id (str): ID of the checkpoint to compare against
        mode (str): Comparison mode - 'basic', 'detailed', or 'comprehensive'
        
    Returns:
        Dict: Diff result between checkpoint state and current state
    """
    from src.tracing import get_state_snapshot
    
    # Get the checkpoint
    checkpoint_data = get_state_snapshot(checkpoint_id)
    if not checkpoint_data:
        debug_logger.error(f"Checkpoint with ID {checkpoint_id} not found")
        return {
            "error": f"Checkpoint with ID {checkpoint_id} not found",
            "stats": {"added": 0, "removed": 0, "modified": 0, "unchanged": 0},
            "summary": "Error: Checkpoint not found"
        }
    
    checkpoint_state = checkpoint_data["state"]
    checkpoint_meta = checkpoint_data["metadata"]
    
    debug_logger.info(f"Comparing current state with checkpoint '{checkpoint_meta['label']}' ({checkpoint_id})")
    
    # Compare the states
    diff_result = diff_states(checkpoint_state, current_state, mode=mode)
    
    # Add checkpoint info to the result
    diff_result["checkpoint_info"] = {
        "id": checkpoint_id,
        "label": checkpoint_meta["label"],
        "timestamp": checkpoint_meta["timestamp"],
        "datetime": checkpoint_meta["datetime"],
        "category": checkpoint_meta.get("category"),
        "description": checkpoint_meta.get("description")
    }
    
    return diff_result

def show_execution_timeline(width: int = 80, include_states: bool = False) -> str:
    """
    Generate a text visualization of the execution timeline.
    
    Args:
        width (int): Width of the timeline in characters
        include_states (bool): Whether to include state details
        
    Returns:
        str: String representation of the timeline
    """
    timeline = get_state_timeline(width, include_states)
    debug_logger.info("Generated execution timeline")
    return timeline

def find_states_with_value(search_term: str, field_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Search state history for states containing a specific value.
    
    Args:
        search_term (str): Term to search for
        field_path (str, optional): Dot notation path to limit search to a specific field
        
    Returns:
        List[Dict]: List of matching state history entries
    """
    results = search_state_history(search_term, False, field_path)
    debug_logger.info(f"Found {len(results)} states matching search term '{search_term}'")
    return results

def time_travel_to_state(index: int) -> Optional[Dict[str, Any]]:
    """
    Retrieve a state from history by its index, enabling "time travel" debugging.
    
    Args:
        index (int): Index of the state to retrieve (negative indices count from the end)
        
    Returns:
        Dict: The historical state or None if index is out of bounds
    """
    from src.tracing import get_state_at_point
    
    state_entry = get_state_at_point(index)
    if state_entry:
        debug_logger.info(f"Time traveled to state at index {index} "
                        f"(node: {state_entry['node_name']}, "
                        f"time: {state_entry['datetime']})")
        return state_entry["state"]
    else:
        debug_logger.error(f"No state found at index {index}")
        return None

def step_through_execution_with_history(app, initial_state: Dict[str, Any], 
                                     step_callback: Optional[Callable] = None,
                                     interactive: bool = False) -> Optional[Dict[str, Any]]:
    """
    Enhanced version of step_through_execution that leverages state history tracking.
    
    Args:
        app: The LangGraph app to execute
        initial_state (Dict): Initial state for execution
        step_callback (Callable, optional): Function to call after each step
        interactive (bool): Whether to enable interactive mode with breakpoints
        
    Returns:
        Dict: Final state after execution or None if execution failed
    """
    # This enhances the existing step_through_execution function
    tracker = get_state_history_tracker()
    
    # Create a checkpoint of the initial state
    initial_checkpoint_id = create_state_checkpoint(
        initial_state, 
        "Execution Start", 
        "execution_steps",
        "Initial state before execution"
    )
    
    nodes = list(app.graph.nodes)
    current_state = initial_state.copy()
    
    debug_logger.info(f"Starting step-through execution with {len(nodes)} nodes")
    debug_logger.info(f"Nodes: {', '.join(nodes)}")
    
    # Control flow variables
    current_node_index = 0
    execution_mode = "continue"  # "continue", "step", "run_to"
    run_to_target = None
    step_backward_count = 0
    
    try:
        while current_node_index < len(nodes):
            # Get current node
            node_name = nodes[current_node_index]
            debug_logger.info(f"\n=== STEP {current_node_index+1}/{len(nodes)}: {node_name} ===")
            
            # Create a checkpoint before the node execution
            pre_checkpoint_id = create_state_checkpoint(
                current_state,
                f"Before {node_name}",
                "execution_steps",
                f"State before executing node {node_name}"
            )
            
            # Check for breakpoints if in interactive mode
            if interactive:
                breakpoint_manager = get_breakpoint_manager()
                
                # Check if this node has a breakpoint
                breakpoint_hit = breakpoint_manager.check_breakpoints(node_name, current_state)
                
                if breakpoint_hit:
                    execution_mode = "step"  # Pause at breakpoint
                    debug_logger.info(f"🛑 Breakpoint hit on node '{node_name}'")
                    
                    if breakpoint_hit["condition"]:
                        debug_logger.info(f"Condition: {breakpoint_hit['condition']}")
                    
                    if breakpoint_hit["description"]:
                        debug_logger.info(f"Description: {breakpoint_hit['description']}")
                    
                    debug_logger.info(f"Hit count: {breakpoint_hit['hit_count']}")
                
                # Handle step control flow
                if execution_mode == "step" or (execution_mode == "run_to" and node_name == run_to_target):
                    if execution_mode == "run_to":
                        debug_logger.info(f"🎯 Reached target node: {run_to_target}")
                        execution_mode = "step"  # Switch to step mode when target is reached
                    
                    # Capture user input for execution control
                    if step_callback:
                        command = step_callback(node_name, current_node_index, current_state)
                        
                        if command == "continue":
                            execution_mode = "continue"
                        elif command == "step":
                            execution_mode = "step"
                        elif command.startswith("run_to "):
                            target_node = command.split("run_to ")[1].strip()
                            if target_node in nodes:
                                execution_mode = "run_to"
                                run_to_target = target_node
                                debug_logger.info(f"Will run until node: {target_node}")
                            else:
                                debug_logger.warning(f"Node '{target_node}' not found in graph")
                        elif command == "step_back":
                            step_backward_count += 1
                            if step_backward_count > current_node_index:
                                debug_logger.warning("Cannot step back beyond first node")
                                step_backward_count = current_node_index
                            else:
                                # Go back to previous node
                                new_index = current_node_index - step_backward_count
                                previous_node = nodes[new_index]
                                debug_logger.info(f"Stepping back to node {new_index+1}: {previous_node}")
                                
                                # Restore state from checkpoint
                                history_entry = tracker.get_history()
                                matching_entries = [
                                    entry for entry in history_entry 
                                    if entry["node_name"] == previous_node and not entry["is_input"]
                                ]
                                
                                if matching_entries:
                                    # Use the most recent state for this node
                                    restored_state = matching_entries[-1]["state"]
                                    current_state = restored_state.copy()
                                    current_node_index = new_index
                                    debug_logger.info(f"Restored state from node: {previous_node}")
                                    continue
                                else:
                                    debug_logger.warning(f"Could not find state for node: {previous_node}")
                        elif command == "quit":
                            debug_logger.info("Execution terminated by user")
                            return current_state
                        else:
                            debug_logger.info(f"Unknown command: {command}")
            
            # Get the node function
            node_func = app.graph.get_node(node_name)["fn"]
            
            # Log and execute the node
            debug_logger.info(f"Executing node: {node_name}")
            node_state_before = current_state.copy()
            
            # Execute the node
            current_state = node_func(current_state)
            
            # Log state changes
            debug_node_execution(node_name, node_state_before, current_state)
            
            # Create a checkpoint after the node execution
            post_checkpoint_id = create_state_checkpoint(
                current_state,
                f"After {node_name}",
                "execution_steps",
                f"State after executing node {node_name}"
            )
            
            # Call the step callback if provided (for non-interactive mode)
            if step_callback and not interactive:
                should_continue = step_callback(node_name, current_node_index, current_state)
                if should_continue is False:
                    debug_logger.info("Step callback requested execution stop")
                    break
                    
            # Display compact timeline after each step
            debug_logger.debug("Timeline so far:")
            debug_logger.debug(show_execution_timeline(width=60, include_states=False))
            
            # Move to next node
            current_node_index += 1
            step_backward_count = 0  # Reset step back count after moving forward
        
        # Create a final checkpoint
        create_state_checkpoint(
            current_state,
            "Execution Complete",
            "execution_steps",
            "Final state after full execution"
        )
        
        debug_logger.info("Step-through execution completed successfully")
        debug_logger.info("Final timeline:")
        debug_logger.info(show_execution_timeline(width=80, include_states=True))
        
        # Compare final state with initial state
        diff_result = compare_with_checkpoint(current_state, initial_checkpoint_id)
        debug_logger.info("Changes from initial state:")
        debug_logger.info(diff_result["visualization"])
        
        return current_state
        
    except Exception as e:
        debug_logger.error(f"Error during step-through execution: {str(e)}")
        debug_logger.debug(traceback.format_exc())
        
        # Create an error checkpoint
        create_state_checkpoint(
            current_state,
            "Execution Error",
            "execution_steps",
            f"State at point of error: {str(e)}"
        )
        
        debug_logger.info("Partial timeline until error:")
        debug_logger.info(show_execution_timeline(width=80, include_states=True))
        
        return None 

# Add step control functions

def run_with_breakpoints(app, initial_state: Dict[str, Any], 
                       step_handler: Optional[Callable] = None) -> Optional[Dict[str, Any]]:
    """
    Run the graph execution with breakpoint support.
    
    This function runs the graph execution with support for breakpoints,
    allowing for interactive debugging.
    
    Args:
        app: The LangGraph app to execute
        initial_state (Dict): Initial state for execution
        step_handler (Callable, optional): Function to handle interaction at steps/breakpoints
            The handler should accept (node_name, index, state) and return a command string:
            - "continue": Continue execution until next breakpoint
            - "step": Execute the next node and pause
            - "run_to <node_name>": Run until the specified node
            - "step_back": Go back to the previous node
            - "quit": Terminate execution
            
    Returns:
        Dict: Final state after execution or None if error occurs
    """
    # Default handler that just returns "continue"
    if step_handler is None:
        def default_handler(node_name, index, state):
            debug_logger.info("Breakpoint hit. Continuing execution...")
            return "continue"
        step_handler = default_handler
    
    return step_through_execution_with_history(app, initial_state, step_handler, True)

def step_forward(app, current_state: Dict[str, Any], current_node_index: int) -> Tuple[Dict[str, Any], int]:
    """
    Execute one node and return the updated state.
    
    Args:
        app: The LangGraph app
        current_state: Current state
        current_node_index: Current node index
        
    Returns:
        Tuple of (new state, new node index)
    """
    nodes = list(app.graph.nodes)
    
    if current_node_index >= len(nodes):
        debug_logger.warning("Already at the end of execution")
        return current_state, current_node_index
    
    node_name = nodes[current_node_index]
    node_func = app.graph.get_node(node_name)["fn"]
    
    debug_logger.info(f"Stepping forward to node {current_node_index+1}/{len(nodes)}: {node_name}")
    new_state = node_func(current_state.copy())
    
    # Create checkpoints
    create_state_checkpoint(
        current_state,
        f"Before {node_name} (step forward)",
        "execution_steps",
        f"State before executing node {node_name} via step forward"
    )
    
    create_state_checkpoint(
        new_state,
        f"After {node_name} (step forward)",
        "execution_steps",
        f"State after executing node {node_name} via step forward"
    )
    
    # Show diff
    debug_node_execution(node_name, current_state, new_state)
    
    return new_state, current_node_index + 1

def step_backward(current_state: Dict[str, Any], current_node_index: int) -> Tuple[Dict[str, Any], int]:
    """
    Step back to the previous node's state using history.
    
    Args:
        current_state: Current state
        current_node_index: Current node index
        
    Returns:
        Tuple of (previous state, previous node index)
    """
    if current_node_index <= 0:
        debug_logger.warning("Already at the beginning of execution")
        return current_state, current_node_index
    
    tracker = get_state_history_tracker()
    history = tracker.get_history()
    
    # Get the node name of the previous step
    nodes = list(app.graph.nodes)
    previous_node_index = current_node_index - 1
    previous_node = nodes[previous_node_index]
    
    # Find the state after the previous node's execution
    matching_entries = [
        entry for entry in history 
        if entry["node_name"] == previous_node and not entry["is_input"]
    ]
    
    if not matching_entries:
        debug_logger.warning(f"Could not find state history for node: {previous_node}")
        return current_state, current_node_index
    
    # Use the most recent state for this node
    previous_state = matching_entries[-1]["state"].copy()
    
    debug_logger.info(f"Stepping back to node {previous_node_index+1}/{len(nodes)}: {previous_node}")
    
    # Create checkpoint
    create_state_checkpoint(
        previous_state,
        f"Step back to {previous_node}",
        "execution_steps",
        f"State restored from node {previous_node} via step back"
    )
    
    # Show diff between current and previous
    diff_result = diff_states(previous_state, current_state, mode='detailed')
    debug_logger.info(f"State changes that will be reverted:")
    debug_logger.info(visualize_diff(diff_result, format_type='table'))
    
    return previous_state, previous_node_index

def run_to_node(app, current_state: Dict[str, Any], current_node_index: int, 
              target_node: str) -> Tuple[Dict[str, Any], int]:
    """
    Run execution until a specific node is reached.
    
    Args:
        app: The LangGraph app
        current_state: Current state
        current_node_index: Current node index
        target_node: Target node name
        
    Returns:
        Tuple of (new state, new node index)
    """
    nodes = list(app.graph.nodes)
    
    if current_node_index >= len(nodes):
        debug_logger.warning("Already at the end of execution")
        return current_state, current_node_index
    
    # Find the target node index
    try:
        target_index = nodes.index(target_node)
    except ValueError:
        debug_logger.warning(f"Target node '{target_node}' not found in graph")
        return current_state, current_node_index
    
    if target_index < current_node_index:
        debug_logger.warning(f"Target node '{target_node}' is behind the current position")
        return current_state, current_node_index
    
    debug_logger.info(f"Running to node {target_index+1}/{len(nodes)}: {target_node}")
    
    # Execute nodes until target is reached
    new_state = current_state.copy()
    new_node_index = current_node_index
    
    while new_node_index <= target_index:
        node_name = nodes[new_node_index]
        node_func = app.graph.get_node(node_name)["fn"]
        
        # Create checkpoint before execution
        create_state_checkpoint(
            new_state,
            f"Before {node_name} (run to)",
            "execution_steps",
            f"State before executing node {node_name} via run to {target_node}"
        )
        
        # Execute node
        debug_logger.info(f"Executing node {new_node_index+1}/{len(nodes)}: {node_name}")
        state_before = new_state.copy()
        new_state = node_func(new_state)
        
        # Log state changes
        debug_node_execution(node_name, state_before, new_state)
        
        # Create checkpoint after execution
        create_state_checkpoint(
            new_state,
            f"After {node_name} (run to)",
            "execution_steps",
            f"State after executing node {node_name} via run to {target_node}"
        )
        
        new_node_index += 1
        
        # Check if we reached the target
        if node_name == target_node:
            debug_logger.info(f"Reached target node: {target_node}")
            break
    
    return new_state, new_node_index

def run_to_condition(app, current_state: Dict[str, Any], current_node_index: int,
                   condition: str) -> Tuple[Dict[str, Any], int]:
    """
    Run execution until a condition is met.
    
    Args:
        app: The LangGraph app
        current_state: Current state
        current_node_index: Current node index
        condition: Condition expression
        
    Returns:
        Tuple of (new state, new node index)
    """
    nodes = list(app.graph.nodes)
    
    if current_node_index >= len(nodes):
        debug_logger.warning("Already at the end of execution")
        return current_state, current_node_index
    
    debug_logger.info(f"Running until condition is met: {condition}")
    
    # Set up condition evaluation
    breakpoint_manager = get_breakpoint_manager()
    
    # Execute nodes until condition is met
    new_state = current_state.copy()
    new_node_index = current_node_index
    
    while new_node_index < len(nodes):
        node_name = nodes[new_node_index]
        node_func = app.graph.get_node(node_name)["fn"]
        
        # Create checkpoint before execution
        create_state_checkpoint(
            new_state,
            f"Before {node_name} (run to condition)",
            "execution_steps",
            f"State before executing node {node_name} via run to condition: {condition}"
        )
        
        # Execute node
        debug_logger.info(f"Executing node {new_node_index+1}/{len(nodes)}: {node_name}")
        state_before = new_state.copy()
        new_state = node_func(new_state)
        
        # Log state changes
        debug_node_execution(node_name, state_before, new_state)
        
        # Create checkpoint after execution
        create_state_checkpoint(
            new_state,
            f"After {node_name} (run to condition)",
            "execution_steps",
            f"State after executing node {node_name} via run to condition: {condition}"
        )
        
        # Check if condition is met
        if breakpoint_manager._evaluate_condition(condition, new_state):
            debug_logger.info(f"Condition met: {condition}")
            break
        
        new_node_index += 1
    
    if new_node_index >= len(nodes):
        debug_logger.warning("Reached end of execution without condition being met")
    
    return new_state, new_node_index

# Add interactive debugging function with CLI interface

def interactive_debug(app, initial_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Start an interactive debugging session for graph execution.
    
    This function runs the graph execution with an interactive CLI that allows:
    - Setting breakpoints
    - Stepping through execution
    - Examining state
    - Going back in execution history
    
    Args:
        app: The LangGraph app to execute
        initial_state: Initial state for execution
        
    Returns:
        Dict: Final state after execution or None if error occurs
    """
    debug_logger.info("Starting interactive debugging session")
    debug_logger.info("Type 'help' to see available commands")
    
    # Initialize control variables
    nodes = list(app.graph.nodes)
    current_state = initial_state.copy()
    current_node_index = 0
    execution_active = True
    execution_complete = False
    
    def step_handler(node_name, index, state):
        nonlocal current_state, current_node_index, execution_active, execution_complete
        
        # Update current state and index
        current_state = state.copy()
        current_node_index = index
        
        # Command loop
        while True:
            try:
                command = input(f"Debug [{node_name}]> ").strip()
                
                if not command:
                    return "step"
                
                if command == "help":
                    print("\nAvailable commands:")
                    print("  s, step         - Execute current node and pause")
                    print("  c, continue     - Continue execution until next breakpoint")
                    print("  r NODE, run_to NODE - Run until specified node")
                    print("  b, back         - Step back to previous node")
                    print("  list            - List all nodes in the graph")
                    print("  bp NODE         - Set breakpoint on a node")
                    print("  bp NODE COND    - Set conditional breakpoint")
                    print("  bp clear [ID]   - Clear a breakpoint or all if no ID")
                    print("  bp list         - List all breakpoints")
                    print("  state           - Show current state")
                    print("  diff            - Show changes from previous node")
                    print("  timeline        - Show execution timeline")
                    print("  q, quit         - Terminate execution")
                    print("  help            - Show this help message")
                    print()
                    
                elif command in ("s", "step"):
                    return "step"
                    
                elif command in ("c", "continue"):
                    return "continue"
                    
                elif command.startswith("r ") or command.startswith("run_to "):
                    parts = command.split(" ", 1)
                    if len(parts) == 2:
                        target_node = parts[1].strip()
                        if target_node in nodes:
                            return f"run_to {target_node}"
                        else:
                            print(f"Node '{target_node}' not found")
                            print(f"Available nodes: {', '.join(nodes)}")
                    else:
                        print("Usage: run_to NODE")
                        
                elif command in ("b", "back"):
                    return "step_back"
                    
                elif command == "list":
                    print("\nNodes in graph:")
                    for i, n in enumerate(nodes):
                        prefix = "➡️ " if i == current_node_index else "  "
                        status = "completed" if i < current_node_index else \
                                 "current" if i == current_node_index else "pending"
                        print(f"{prefix}{i+1}: {n} ({status})")
                    print()
                    
                elif command.startswith("bp "):
                    bp_parts = command.split(" ")
                    
                    if len(bp_parts) == 2 and bp_parts[1] == "list":
                        breakpoints = list_breakpoints()
                        print("\nBreakpoints:")
                        if not breakpoints:
                            print("  No breakpoints set")
                        else:
                            for bp in breakpoints:
                                status = "enabled" if bp["enabled"] else "disabled"
                                condition_str = f" condition: {bp['condition']}" if bp["condition"] else ""
                                print(f"  ID: {bp['id']}")
                                print(f"    Node: {bp['node_name']}")
                                print(f"    Status: {status}{condition_str}")
                                print(f"    Hit count: {bp['hit_count']}")
                                if bp["description"]:
                                    print(f"    Desc: {bp['description']}")
                                print()
                        
                    elif len(bp_parts) >= 3 and bp_parts[1] == "clear":
                        if len(bp_parts) == 3:
                            # Clear specific breakpoint
                            bp_id = bp_parts[2]
                            if clear_breakpoint(bp_id):
                                print(f"Cleared breakpoint {bp_id}")
                            else:
                                print(f"Breakpoint {bp_id} not found")
                        else:
                            # Clear all breakpoints
                            count = clear_all_breakpoints()
                            print(f"Cleared {count} breakpoints")
                            
                    elif len(bp_parts) >= 3:
                        # Set breakpoint
                        target_node = bp_parts[1]
                        
                        if target_node not in nodes:
                            print(f"Node '{target_node}' not found")
                            continue
                            
                        condition = None
                        if len(bp_parts) > 3:
                            condition = " ".join(bp_parts[2:])
                            
                        bp_id = set_breakpoint(
                            target_node, 
                            condition=condition,
                            description=f"Set during interactive debug at node {node_name}"
                        )
                        
                        condition_str = f" with condition: {condition}" if condition else ""
                        print(f"Set breakpoint on {target_node}{condition_str}")
                        print(f"ID: {bp_id}")
                        
                    else:
                        print("Usage: bp NODE [CONDITION] | bp clear [ID] | bp list")
                        
                elif command == "state":
                    print("\nCurrent state:")
                    print(json.dumps(current_state, indent=2))
                    print()
                    
                elif command == "diff":
                    if current_node_index > 0:
                        prev_node = nodes[current_node_index - 1]
                        
                        # Get previous state from history
                        tracker = get_state_history_tracker()
                        history = tracker.get_history()
                        matching_entries = [
                            entry for entry in history 
                            if entry["node_name"] == prev_node and not entry["is_input"]
                        ]
                        
                        if matching_entries:
                            prev_state = matching_entries[-1]["state"]
                            diff_result = diff_states(prev_state, current_state, mode='detailed')
                            print("\nChanges from previous node:")
                            print(visualize_diff(diff_result, format_type='table'))
                            print()
                        else:
                            print(f"Could not find state for previous node: {prev_node}")
                    else:
                        print("No previous node to compare with")
                        
                elif command == "timeline":
                    print("\nExecution timeline:")
                    print(show_execution_timeline(width=80, include_states=False))
                    print()
                    
                elif command in ("q", "quit"):
                    execution_active = False
                    return "quit"
                    
                else:
                    print(f"Unknown command: {command}")
                    print("Type 'help' to see available commands")
                
            except Exception as e:
                print(f"Error: {str(e)}")
                traceback.print_exc()
    
    # Run with breakpoints and our interactive handler
    return run_with_breakpoints(app, initial_state, step_handler)

# Add enhanced state field monitoring convenience functions

def monitor_field(field_path: str, condition: str = None, 
                 description: str = None, level: str = 'INFO') -> str:
    """
    Monitor a specific field in the state with an optional condition.
    
    This is a convenience function for watch_field with a simplified interface.
    
    Args:
        field_path: Dot notation path to the field (e.g., "user.preferences.theme")
        condition: Optional condition to trigger alerts (e.g., "value > 100")
                  If None, triggers on any change.
        description: Optional description of the monitoring
        level: Alert level ('INFO', 'WARNING', 'ERROR', 'CRITICAL')
        
    Returns:
        str: ID of the created monitor
    """
    return watch_field(
        field_path=field_path,
        expression=condition,
        description=description or f"Monitoring {field_path}",
        alert_level=level
    )

def monitor_value_change(field_path: str, min_change: Optional[float] = None, 
                        percentage: bool = False, level: str = 'INFO') -> str:
    """
    Monitor a field for value changes exceeding a threshold.
    
    Args:
        field_path: Dot notation path to the field (e.g., "metrics.response_time")
        min_change: Minimum absolute or percentage change to trigger an alert
                   If None, any change will trigger.
        percentage: If True, min_change is treated as a percentage
        level: Alert level ('INFO', 'WARNING', 'ERROR', 'CRITICAL')
        
    Returns:
        str: ID of the created monitor
    """
    if min_change is None:
        expr = "value != prev_value"
        description = f"Monitoring any change to {field_path}"
    elif percentage:
        # Calculate percentage change, handling division by zero
        expr = f"prev_value is not None and prev_value != 0 and abs((value - prev_value) / prev_value * 100) >= {min_change}"
        description = f"Monitoring {field_path} for ≥{min_change}% change"
    else:
        expr = f"prev_value is not None and abs(value - prev_value) >= {min_change}"
        description = f"Monitoring {field_path} for changes ≥{min_change}"
    
    return watch_field(
        field_path=field_path,
        expression=expr,
        description=description,
        alert_level=level
    )

def monitor_threshold(field_path: str, threshold: Any, comparison: str = ">", 
                     level: str = 'WARNING') -> str:
    """
    Monitor a field for exceeding a specific threshold.
    
    Args:
        field_path: Dot notation path to the field (e.g., "metrics.error_count")
        threshold: Threshold value to compare against
        comparison: Comparison operator ('>', '>=', '<', '<=', '==', '!=')
        level: Alert level ('INFO', 'WARNING', 'ERROR', 'CRITICAL')
        
    Returns:
        str: ID of the created monitor
    """
    valid_comparisons = {'>', '>=', '<', '<=', '==', '!='}
    if comparison not in valid_comparisons:
        debug_logger.warning(f"Invalid comparison '{comparison}', defaulting to '>'")
        comparison = '>'
    
    # Create appropriate expression
    if isinstance(threshold, str):
        expr = f"value is not None and value {comparison} '{threshold}'"
    else:
        expr = f"value is not None and value {comparison} {threshold}"
    
    description = f"Monitoring {field_path} for {comparison} {threshold}"
    
    return watch_field(
        field_path=field_path,
        expression=expr,
        description=description,
        alert_level=level
    )

def monitor_pattern_match(field_path: str, pattern: str, case_sensitive: bool = False,
                        level: str = 'INFO') -> str:
    """
    Monitor a string field for pattern matches.
    
    Args:
        field_path: Dot notation path to the field (e.g., "user.message")
        pattern: String pattern to look for
        case_sensitive: Whether the match should be case sensitive
        level: Alert level ('INFO', 'WARNING', 'ERROR', 'CRITICAL')
        
    Returns:
        str: ID of the created monitor
    """
    # Escape single quotes in the pattern
    safe_pattern = pattern.replace("'", "\\'")
    
    if case_sensitive:
        expr = f"value is not None and str(value).find('{safe_pattern}') >= 0"
        description = f"Monitoring {field_path} for case-sensitive match: '{pattern}'"
    else:
        expr = f"value is not None and str(value).lower().find('{safe_pattern.lower()}') >= 0"
        description = f"Monitoring {field_path} for match: '{pattern}'"
    
    return watch_field(
        field_path=field_path,
        expression=expr,
        description=description,
        alert_level=level
    )

def monitor_state_condition(condition: str, description: str = None, 
                          level: str = 'WARNING') -> str:
    """
    Monitor the entire state with a custom condition expression.
    
    This is more advanced and evaluates the condition against the entire state.
    
    Args:
        condition: Custom condition to evaluate (e.g., "len(value.get('items', [])) > max_items")
        description: Description of the condition being monitored
        level: Alert level ('INFO', 'WARNING', 'ERROR', 'CRITICAL')
        
    Returns:
        str: ID of the created monitor
    """
    return watch_field(
        field_path="",  # Root of the state
        expression=condition,
        description=description or f"Monitoring state condition: {condition}",
        alert_level=level
    )

def stop_monitoring(monitor_id: str) -> bool:
    """
    Stop monitoring a field by removing the watch.
    
    Args:
        monitor_id: ID of the monitor to remove
        
    Returns:
        bool: True if the monitor was removed, False otherwise
    """
    return remove_watch(monitor_id)

def stop_all_monitoring():
    """Stop all field monitoring."""
    clear_watches()
    debug_logger.info("Stopped all field monitoring")

def get_active_monitors():
    """
    Get information about all active monitors.
    
    Returns:
        List[Dict]: Information about all active monitors
    """
    return list_watches()

def get_monitoring_statistics():
    """
    Get statistics about field monitoring.
    
    Returns:
        Dict: Statistics about monitoring activities
    """
    return get_monitor_statistics() 