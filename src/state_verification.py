"""
State Propagation Verification Framework for KFM Agent.

This module provides a comprehensive framework to verify, visualize, and analyze
the propagation of KFMAgentState objects between nodes in the LangGraph workflow.
It builds upon the existing tracing and debugging infrastructure to provide
deeper insights into state transitions, data integrity, and error detection.
"""

import os
import json
import logging
import time
import copy
from typing import Dict, Any, List, Optional, Set, Tuple, Callable
import pandas as pd
from pathlib import Path
from datetime import datetime
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from src.core.state import KFMAgentState
from src.logger import setup_logger, setup_file_logger
from src.tracing import get_trace_history, reset_trace_history, configure_tracing

# Setup a dedicated logger for state verification
state_verify_logger = setup_logger('StateVerify')

# Define constants for verification levels
VERIFICATION_LEVEL_BASIC = 0      # Basic checks only
VERIFICATION_LEVEL_STANDARD = 1   # Standard verification
VERIFICATION_LEVEL_DETAILED = 2   # Detailed state validation including field-level checks
VERIFICATION_LEVEL_DIAGNOSTIC = 3 # Full diagnostic with additional data integrity tests

# Global configuration settings
config = {
    "verification_level": VERIFICATION_LEVEL_STANDARD,
    "visualization_enabled": True,
    "output_dir": "logs/state_verification",
    "log_state_size": True,
    "inject_test_states": False,
    "track_performance_metrics": True,
    "field_validators": {},      # Field-specific validators
    "state_validators": {},      # Whole state validators
    "transition_validators": {}, # Node transition validators
    "field_trackers": set(),     # Fields to track across state transitions
    "verbosity": 1,              # Default verbosity level
    "throw_on_validation_error": False
}

# Global container for state history
state_history = []

# Error and warning counters
error_count = 0
warning_count = 0

class ValidationResult:
    """Container for validation results with information about issues found."""
    
    def __init__(self, valid: bool, message: str = "", data: Optional[Dict[str, Any]] = None):
        self.valid = valid
        self.message = message
        self.data = data or {}
        self.timestamp = time.time()
    
    def __bool__(self):
        return self.valid
    
    def __str__(self):
        status = "VALID" if self.valid else "INVALID"
        return f"[{status}] {self.message}"

def configure_verification_framework(
    verification_level: int = VERIFICATION_LEVEL_STANDARD,
    visualization_enabled: bool = True,
    output_dir: str = "logs/state_verification",
    log_state_size: bool = True,
    track_performance_metrics: bool = True,
    verbosity: int = 1,
    throw_on_validation_error: bool = False
) -> None:
    """
    Configure the state verification framework.
    
    Args:
        verification_level: Level of verification detail (0-3)
        visualization_enabled: Whether to generate visualizations
        output_dir: Directory for output files
        log_state_size: Whether to log state object sizes
        track_performance_metrics: Whether to track performance metrics
        verbosity: Verbosity level for logging (0-3)
        throw_on_validation_error: Whether to raise exceptions on validation errors
    """
    global config
    
    config["verification_level"] = verification_level
    config["visualization_enabled"] = visualization_enabled
    config["output_dir"] = output_dir
    config["log_state_size"] = log_state_size
    config["track_performance_metrics"] = track_performance_metrics
    config["verbosity"] = verbosity
    config["throw_on_validation_error"] = throw_on_validation_error
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Set up a file logger for the verification framework
    file_handler = setup_file_logger(os.path.join(output_dir, "state_verification.log"))
    state_verify_logger.addHandler(file_handler)
    
    # Configure tracing level based on verification level
    if verification_level >= VERIFICATION_LEVEL_DETAILED:
        trace_level = logging.DEBUG
    else:
        trace_level = logging.INFO
    
    # Configure the tracing module to work with our verification framework
    configure_tracing(log_level=trace_level, filter_keys=["input"] if verification_level < VERIFICATION_LEVEL_DIAGNOSTIC else [])
    
    state_verify_logger.info(f"State Verification Framework configured - Level: {verification_level}, Verbosity: {verbosity}")

def reset_verification() -> None:
    """Reset the verification framework state, clearing all history and counters."""
    global state_history, error_count, warning_count
    state_history = []
    error_count = 0
    warning_count = 0
    reset_trace_history()
    state_verify_logger.info("State verification framework reset")

def register_field_validator(field_name: str, validator_func: Callable[[Any], ValidationResult]) -> None:
    """
    Register a validator function for a specific field.
    
    Args:
        field_name: Name of the field to validate
        validator_func: Function that takes a field value and returns a ValidationResult
    """
    config["field_validators"][field_name] = validator_func
    state_verify_logger.info(f"Registered field validator for '{field_name}'")

def register_state_validator(validator_name: str, validator_func: Callable[[Dict[str, Any]], ValidationResult]) -> None:
    """
    Register a validator function for the entire state.
    
    Args:
        validator_name: Name for the validator
        validator_func: Function that takes a state dict and returns a ValidationResult
    """
    config["state_validators"][validator_name] = validator_func
    state_verify_logger.info(f"Registered state validator '{validator_name}'")

def register_transition_validator(
    from_node: str, 
    to_node: str, 
    validator_func: Callable[[Dict[str, Any], Dict[str, Any]], ValidationResult]
) -> None:
    """
    Register a validator for transitions between specific nodes.
    
    Args:
        from_node: Source node name
        to_node: Target node name
        validator_func: Function that takes source and target states and returns a ValidationResult
    """
    transition_key = f"{from_node}->{to_node}"
    config["transition_validators"][transition_key] = validator_func
    state_verify_logger.info(f"Registered transition validator for '{transition_key}'")

def track_field(field_name: str) -> None:
    """
    Register a field to track across all state transitions.
    
    Args:
        field_name: Name of the field to track
    """
    config["field_trackers"].add(field_name)
    state_verify_logger.info(f"Field '{field_name}' will be tracked across transitions")

def create_test_state(
    test_name: str, 
    state_data: Optional[Dict[str, Any]] = None
) -> KFMAgentState:
    """
    Create a test state for verification purposes.
    
    Args:
        test_name: Name of the test
        state_data: Initial state data (optional)
        
    Returns:
        KFMAgentState: A state object for testing
    """
    test_state_data = state_data or {
        "task_name": f"test_{test_name}",
        "input": {"test_query": f"Test query for {test_name}"},
        "active_component": None,
        "performance_data": {
            "component1": {"accuracy": 0.8, "latency": 1.0},
            "component2": {"accuracy": 0.9, "latency": 2.0}
        },
        "task_requirements": {"min_accuracy": 0.8, "max_latency": 2.0}
    }
    
    # Add test marker
    test_state_data["_test_state"] = True
    test_state_data["_test_name"] = test_name
    
    state_verify_logger.info(f"Created test state '{test_name}'")
    return KFMAgentState(test_state_data)

def capture_state(node_name: str, state: Dict[str, Any]) -> None:
    """
    Capture state at a specific node for later verification.
    
    Args:
        node_name: Name of the node where state is captured
        state: State dict to capture
    """
    global state_history
    
    # Create a deep copy to ensure we're not affected by later modifications
    state_copy = copy.deepcopy(state)
    
    # Add metadata
    entry = {
        "timestamp": time.time(),
        "node": node_name,
        "state": state_copy
    }
    
    # Track state size if enabled
    if config["log_state_size"]:
        # Convert to JSON to get a realistic size estimate
        state_json = json.dumps(state_copy)
        entry["state_size"] = len(state_json)
    
    state_history.append(entry)
    
    if config["verbosity"] >= 2:
        state_verify_logger.debug(f"Captured state at node '{node_name}' - Size: {entry.get('state_size', 'unknown')} bytes")

def verify_field(field_name: str, field_value: Any) -> ValidationResult:
    """
    Verify a specific field using registered field validators.
    
    Args:
        field_name: Name of the field
        field_value: Value to verify
        
    Returns:
        ValidationResult: Validation result
    """
    if field_name in config["field_validators"]:
        validator = config["field_validators"][field_name]
        try:
            result = validator(field_value)
            if not result.valid and config["verbosity"] >= 1:
                state_verify_logger.warning(f"Field validation failed for '{field_name}': {result.message}")
            return result
        except Exception as e:
            error_msg = f"Error in field validator for '{field_name}': {str(e)}"
            state_verify_logger.error(error_msg)
            return ValidationResult(False, error_msg)
    
    # No validator registered for this field
    return ValidationResult(True, f"No validator for field '{field_name}'")

def verify_state(state: Dict[str, Any]) -> List[ValidationResult]:
    """
    Verify an entire state using registered state validators.
    
    Args:
        state: State dictionary to verify
        
    Returns:
        List[ValidationResult]: List of validation results
    """
    results = []
    
    # First verify individual fields
    if config["verification_level"] >= VERIFICATION_LEVEL_STANDARD:
        for field_name, field_value in state.items():
            if field_name in config["field_validators"]:
                result = verify_field(field_name, field_value)
                results.append(result)
    
    # Then verify the whole state with registered validators
    for validator_name, validator_func in config["state_validators"].items():
        try:
            result = validator_func(state)
            results.append(result)
            
            if not result.valid and config["verbosity"] >= 1:
                state_verify_logger.warning(f"State validation '{validator_name}' failed: {result.message}")
        except Exception as e:
            error_msg = f"Error in state validator '{validator_name}': {str(e)}"
            state_verify_logger.error(error_msg)
            results.append(ValidationResult(False, error_msg))
    
    return results

def verify_transition(from_node: str, to_node: str, from_state: Dict[str, Any], to_state: Dict[str, Any]) -> List[ValidationResult]:
    """
    Verify a state transition between two nodes.
    
    Args:
        from_node: Source node name
        to_node: Target node name
        from_state: State before transition
        to_state: State after transition
        
    Returns:
        List[ValidationResult]: List of validation results
    """
    results = []
    transition_key = f"{from_node}->{to_node}"
    
    # Check if we have a specific validator for this transition
    if transition_key in config["transition_validators"]:
        validator = config["transition_validators"][transition_key]
        try:
            result = validator(from_state, to_state)
            results.append(result)
            
            if not result.valid and config["verbosity"] >= 1:
                state_verify_logger.warning(f"Transition validation '{transition_key}' failed: {result.message}")
        except Exception as e:
            error_msg = f"Error in transition validator '{transition_key}': {str(e)}"
            state_verify_logger.error(error_msg)
            results.append(ValidationResult(False, error_msg))
    
    # Track specific fields across the transition
    if config["verification_level"] >= VERIFICATION_LEVEL_DETAILED:
        for field in config["field_trackers"]:
            if field in from_state and field in to_state:
                # For fields that shouldn't change during this transition
                if field in config["field_trackers"] and from_state[field] != to_state[field]:
                    msg = f"Field '{field}' changed during '{transition_key}' transition: {from_state[field]} -> {to_state[field]}"
                    if config["verbosity"] >= 2:
                        state_verify_logger.info(msg)
    
    return results

def analyze_trace_history() -> Dict[str, Any]:
    """
    Analyze the trace history to identify patterns and issues.
    
    Returns:
        Dict[str, Any]: Analysis results
    """
    trace_history = get_trace_history()
    if not trace_history:
        state_verify_logger.warning("No trace history available for analysis")
        return {"status": "empty", "message": "No trace history available"}
    
    # Basic statistics
    node_counts = {}
    transition_counts = {}
    error_nodes = []
    duration_by_node = {}
    
    # Track previous node for transitions
    prev_node = None
    
    for entry in trace_history:
        node = entry["node"]
        
        # Count node occurrences
        node_counts[node] = node_counts.get(node, 0) + 1
        
        # Track durations
        if "duration" in entry:
            if node not in duration_by_node:
                duration_by_node[node] = []
            duration_by_node[node].append(entry["duration"])
        
        # Track errors
        if not entry.get("success", True):
            error_nodes.append(node)
        
        # Track transitions
        if prev_node is not None:
            transition_key = f"{prev_node}->{node}"
            transition_counts[transition_key] = transition_counts.get(transition_key, 0) + 1
        
        prev_node = node
    
    # Calculate average durations
    avg_durations = {
        node: sum(durations) / len(durations) 
        for node, durations in duration_by_node.items()
    }
    
    # Identify bottlenecks (nodes with highest average duration)
    bottlenecks = sorted(
        avg_durations.items(),
        key=lambda x: x[1],
        reverse=True
    )
    
    # State size analysis (if available)
    state_sizes = []
    for entry in state_history:
        if "state_size" in entry:
            state_sizes.append({
                "node": entry["node"],
                "size": entry["state_size"]
            })
    
    return {
        "status": "complete",
        "node_counts": node_counts,
        "transition_counts": transition_counts,
        "error_nodes": error_nodes,
        "bottlenecks": bottlenecks[:3] if bottlenecks else [],  # Top 3 bottlenecks
        "avg_durations": avg_durations,
        "state_sizes": state_sizes,
        "total_transitions": len(trace_history) - 1,
        "total_errors": len(error_nodes)
    }

def generate_state_flow_visualization(output_path: str = None) -> str:
    """
    Generate a visualization of the state flow.
    
    Args:
        output_path: Optional path to save the visualization
        
    Returns:
        str: Path to the saved visualization
    """
    if not config["visualization_enabled"]:
        state_verify_logger.info("Visualization is disabled")
        return ""
    
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(config["output_dir"], f"state_flow_{timestamp}.png")
    
    trace_history = get_trace_history()
    if not trace_history:
        state_verify_logger.warning("No trace history available for visualization")
        return ""
    
    try:
        # Create directed graph
        G = nx.DiGraph()
        
        # Add nodes
        for entry in trace_history:
            node = entry["node"]
            success = entry.get("success", True)
            G.add_node(node, success=success)
        
        # Add edges
        for i in range(1, len(trace_history)):
            from_node = trace_history[i-1]["node"]
            to_node = trace_history[i]["node"]
            G.add_edge(from_node, to_node)
        
        # Prepare the visualization
        plt.figure(figsize=(12, 8))
        
        # Define node colors based on success status
        node_colors = []
        for node in G.nodes():
            success = G.nodes[node].get("success", True)
            node_colors.append("green" if success else "red")
        
        # Create the plot
        pos = nx.spring_layout(G)
        nx.draw(G, pos, with_labels=True, node_color=node_colors, node_size=2000, 
                font_size=12, font_weight="bold", arrowsize=20)
        
        # Add title
        plt.title("KFM Agent State Flow", fontsize=16)
        
        # Save the plot
        plt.savefig(output_path)
        plt.close()
        
        state_verify_logger.info(f"State flow visualization saved to {output_path}")
        return output_path
    except Exception as e:
        state_verify_logger.error(f"Error generating state flow visualization: {e}")
        return ""

def generate_verification_report(output_path: str = None) -> str:
    """
    Generate a comprehensive report of the state verification.
    
    Args:
        output_path: Optional path to save the report
        
    Returns:
        str: Path to the saved report
    """
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(config["output_dir"], f"verification_report_{timestamp}.json")
    
    # Analyze trace history
    analysis = analyze_trace_history()
    
    # Create report
    report = {
        "timestamp": datetime.now().isoformat(),
        "config": {k: v for k, v in config.items() if not callable(v)},
        "analysis": analysis,
        "error_count": error_count,
        "warning_count": warning_count,
        "state_count": len(state_history)
    }
    
    # Add visualization path if enabled
    if config["visualization_enabled"]:
        viz_path = generate_state_flow_visualization()
        if viz_path:
            report["visualization_path"] = viz_path
    
    # Save report
    try:
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        state_verify_logger.info(f"Verification report saved to {output_path}")
        return output_path
    except Exception as e:
        state_verify_logger.error(f"Error saving verification report: {e}")
        return ""

def inject_test_state_hook(node_name: str, state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Hook for injecting test states at specific nodes.
    
    Args:
        node_name: Name of the node
        state: Current state
        
    Returns:
        Dict[str, Any]: State to use (could be modified or test state)
    """
    if not config["inject_test_states"]:
        return state
    
    # Here we would implement logic to inject specific test states
    # based on node_name and testing scenarios
    return state

def register_common_validators() -> None:
    """Register a set of common validators for KFM Agent states."""
    
    def validate_task_name(value):
        if not isinstance(value, str):
            return ValidationResult(False, f"Task name must be a string, got {type(value)}")
        return ValidationResult(True, "Valid task name")
    
    def validate_performance_data(value):
        if not isinstance(value, dict):
            return ValidationResult(False, "Performance data must be a dictionary")
        
        valid = True
        issues = []
        
        for component, metrics in value.items():
            if not isinstance(metrics, dict):
                valid = False
                issues.append(f"Metrics for {component} must be a dictionary")
                continue
            
            for metric_name, metric_value in metrics.items():
                if not isinstance(metric_value, (int, float)):
                    valid = False
                    issues.append(f"Metric {metric_name} for {component} must be numeric")
        
        if valid:
            return ValidationResult(True, "Valid performance data")
        return ValidationResult(False, f"Invalid performance data: {'; '.join(issues)}")
    
    def validate_kfm_action(value):
        if value is None:
            # None is a valid value for kfm_action when no decision is made
            return ValidationResult(True, "Valid empty KFM action")
            
        if not isinstance(value, dict):
            return ValidationResult(False, "KFM action must be a dictionary or None")
        
        valid = True
        issues = []
        
        if 'action' not in value:
            valid = False
            issues.append("Missing 'action' field")
        elif not isinstance(value['action'], str):
            valid = False
            issues.append("'action' must be a string")
        
        if 'component' not in value:
            valid = False
            issues.append("Missing 'component' field")
        elif not isinstance(value['component'], str):
            valid = False
            issues.append("'component' must be a string")
        
        if valid:
            return ValidationResult(True, "Valid KFM action")
        return ValidationResult(False, f"Invalid KFM action: {'; '.join(issues)}")
    
    def validate_reflections(value):
        if value is None:
            return ValidationResult(False, "Reflections cannot be None, should be an empty list if no reflections")
        if not isinstance(value, list):
            return ValidationResult(False, f"Reflections must be a list, got {type(value)}")
        
        valid = True
        issues = []
        
        for i, reflection in enumerate(value):
            if not isinstance(reflection, str):
                valid = False
                issues.append(f"Reflection {i} must be a string")
        
        if valid:
            return ValidationResult(True, "Valid reflections list")
        return ValidationResult(False, f"Invalid reflections: {'; '.join(issues)}")
        
    # Register field validators
    register_field_validator("task_name", validate_task_name)
    register_field_validator("performance_data", validate_performance_data)
    register_field_validator("kfm_action", validate_kfm_action)
    register_field_validator("reflections", validate_reflections)
    
    # Track important fields
    track_field("task_name")
    track_field("input")
    track_field("kfm_action")
    track_field("active_component")
    track_field("result")
    track_field("reflections")
    
    # Register state validators
    register_state_validator("integrity", validate_state_integrity)
    register_state_validator("consistency", validate_consistency)

def verify_graph_execution(graph_input: Dict[str, Any], execution_result: Dict[str, Any]) -> ValidationResult:
    """
    Verify the entire graph execution from initial input to final result.
    
    Args:
        graph_input: Initial input state to the graph
        execution_result: Final output state from the graph
        
    Returns:
        ValidationResult: Overall validation result
    """
    # Analyze trace history
    analysis = analyze_trace_history()
    
    # Check if we have errors in the trace
    if analysis["total_errors"] > 0:
        return ValidationResult(False, 
            f"Graph execution had {analysis['total_errors']} errors", 
            {"error_nodes": analysis["error_nodes"]})
    
    # Verify input fields are preserved
    input_preserved = True
    comparison_issues = []
    
    for field in config["field_trackers"]:
        if field in graph_input and field in execution_result:
            if graph_input[field] != execution_result[field] and field != "active_component":
                input_preserved = False
                comparison_issues.append(f"Field '{field}' changed during execution")
    
    if not input_preserved:
        return ValidationResult(False, 
            "Input fields were not preserved during execution", 
            {"issues": comparison_issues})
    
    # Check we got a result or an error
    if "result" not in execution_result and "error" not in execution_result:
        return ValidationResult(False, 
            "Execution did not produce a result or error", 
            {"final_state_keys": list(execution_result.keys())})
    
    # Check for error in final state
    if "error" in execution_result and execution_result["error"] is not None:
        return ValidationResult(False, 
            f"Execution ended with error: {execution_result['error']}", 
            {"error": execution_result["error"]})
    
    # If we reach here, everything passed
    return ValidationResult(True, 
        "Graph execution successfully verified", 
        {"analysis": analysis})

def measure_state_size_metrics() -> Dict[str, Any]:
    """
    Measure size metrics for state objects in the history.
    
    Returns:
        Dict[str, Any]: Size metrics by node
    """
    if not state_history:
        return {}
    
    size_metrics = {}
    
    for entry in state_history:
        if "state_size" not in entry:
            continue
            
        node = entry["node"]
        size = entry["state_size"]
        
        if node not in size_metrics:
            size_metrics[node] = {
                "min_size": size,
                "max_size": size,
                "total_size": size,
                "count": 1
            }
        else:
            metrics = size_metrics[node]
            metrics["min_size"] = min(metrics["min_size"], size)
            metrics["max_size"] = max(metrics["max_size"], size)
            metrics["total_size"] += size
            metrics["count"] += 1
    
    # Calculate averages
    for node, metrics in size_metrics.items():
        metrics["avg_size"] = metrics["total_size"] / metrics["count"]
    
    return size_metrics

def load_test_states_from_file(file_path: str) -> List[Dict[str, Any]]:
    """
    Load test states from a JSON file.
    
    Args:
        file_path: Path to the JSON file containing test states
        
    Returns:
        List[Dict[str, Any]]: List of test state dictionaries
    """
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            state_verify_logger.error("Test states file must contain a list of state dictionaries")
            return []
        
        state_verify_logger.info(f"Loaded {len(data)} test states from {file_path}")
        return data
    except Exception as e:
        state_verify_logger.error(f"Error loading test states from {file_path}: {e}")
        return []

# Standard state validators

def validate_state_integrity(state: Dict[str, Any]) -> ValidationResult:
    """
    Validate the basic integrity of a state.
    
    Args:
        state: State to validate
        
    Returns:
        ValidationResult: Validation result
    """
    # Check for required fields
    required_fields = ["task_name", "input"]
    missing_fields = [field for field in required_fields if field not in state]
    
    if missing_fields:
        return ValidationResult(False, 
            f"State missing required fields: {', '.join(missing_fields)}", 
            {"missing_fields": missing_fields})
    
    # Check data types
    if "task_name" in state and not isinstance(state["task_name"], str):
        return ValidationResult(False, 
            f"task_name must be a string, got {type(state['task_name'])}")
    
    if "input" in state and not isinstance(state["input"], dict):
        return ValidationResult(False, 
            f"input must be a dictionary, got {type(state['input'])}")
    
    # All checks passed
    return ValidationResult(True, "State integrity validated")

def validate_consistency(state: Dict[str, Any]) -> ValidationResult:
    """
    Validate the consistency of a state (e.g., no contradictory data).
    
    Args:
        state: State to validate
        
    Returns:
        ValidationResult: Validation result
    """
    issues = []
    
    # Check that if error is present, done should be True
    if state.get("error") is not None and not state.get("done", False):
        issues.append("State has error but is not marked as done")
    
    # Check that if active_component is set, it should match the component in kfm_action
    if (state.get("active_component") is not None and 
        state.get("kfm_action") is not None and 
        state.get("kfm_action").get("component") is not None and
        state.get("active_component") != state.get("kfm_action").get("component")):
        issues.append(
            f"active_component ({state.get('active_component')}) doesn't match " +
            f"kfm_action.component ({state.get('kfm_action').get('component')})"
        )
    
    if issues:
        return ValidationResult(False, 
            f"State consistency issues: {'; '.join(issues)}", 
            {"issues": issues})
    
    return ValidationResult(True, "State consistency validated") 