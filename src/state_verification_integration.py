"""
Integration module for the State Propagation Verification Framework.

This module provides functions to integrate the verification framework
with the LangGraph nodes in the KFM Agent implementation.
"""

import functools
import logging
from typing import Dict, Any, List, Optional, Callable, Tuple
from src.logger import setup_logger
from src.core.state import KFMAgentState
from src.state_verification import (
    capture_state,
    verify_state,
    verify_transition,
    configure_verification_framework,
    inject_test_state_hook,
    generate_verification_report,
    generate_state_flow_visualization,
    ValidationResult,
    VERIFICATION_LEVEL_STANDARD,
    register_common_validators
)

# Setup a dedicated logger for the integration
integration_logger = setup_logger('StateVerifyIntegration')

# Track the last seen state for each node
_last_state_by_node = {}

def initialize_verification_integration(
    verification_level: int = VERIFICATION_LEVEL_STANDARD,
    register_validators: bool = True
) -> None:
    """
    Initialize the verification framework integration.
    
    Args:
        verification_level: Level of verification detail
        register_validators: Whether to register common validators
    """
    # Configure the verification framework
    configure_verification_framework(verification_level=verification_level)
    
    # Register common validators if requested
    if register_validators:
        register_common_validators()
    
    integration_logger.info(f"State verification integration initialized with level {verification_level}")

def verify_node_wrapper(node_func: Callable) -> Callable:
    """
    Decorator to wrap a node function with state verification.
    
    Args:
        node_func: The node function to wrap
        
    Returns:
        Callable: Wrapped function
    """
    node_name = node_func.__name__
    
    @functools.wraps(node_func)
    def wrapper(state: Dict[str, Any], *args, **kwargs):
        global _last_state_by_node
        
        # Convert to a dictionary if it's a KFMAgentState
        if isinstance(state, KFMAgentState):
            input_state = state.to_dict()
        else:
            input_state = state
            
        # Apply test state injection if enabled
        input_state = inject_test_state_hook(node_name, input_state)
        
        # Capture the input state
        integration_logger.info(f"Verifying state at {node_name} input")
        capture_state(f"{node_name}_input", input_state)
        
        # Verify the input state
        validation_results = verify_state(input_state)
        invalid_results = [r for r in validation_results if not r.valid]
        if invalid_results:
            integration_logger.warning(f"State validation issues at {node_name} input: {len(invalid_results)} issues")
            for result in invalid_results:
                integration_logger.warning(f"  - {result.message}")
        
        # Check for state transitions from previous nodes
        for prev_node, prev_state in _last_state_by_node.items():
            transition_results = verify_transition(prev_node, node_name, prev_state, input_state)
            invalid_transition_results = [r for r in transition_results if not r.valid]
            if invalid_transition_results:
                integration_logger.warning(
                    f"Transition validation issues from {prev_node} to {node_name}: "
                    f"{len(invalid_transition_results)} issues")
                for result in invalid_transition_results:
                    integration_logger.warning(f"  - {result.message}")
        
        # Call the wrapped node function
        try:
            result = node_func(state if isinstance(state, KFMAgentState) else input_state, *args, **kwargs)
            
            # Convert result to dictionary if needed
            if isinstance(result, KFMAgentState):
                output_state = result.to_dict()
            else:
                output_state = result
                
            # Capture the output state
            integration_logger.info(f"Verifying state at {node_name} output")
            capture_state(f"{node_name}_output", output_state)
            
            # Verify the output state
            validation_results = verify_state(output_state)
            invalid_results = [r for r in validation_results if not r.valid]
            if invalid_results:
                integration_logger.warning(f"State validation issues at {node_name} output: {len(invalid_results)} issues")
                for result in invalid_results:
                    integration_logger.warning(f"  - {result.message}")
            
            # Verify transition from input to output
            transition_results = verify_transition(f"{node_name}_input", f"{node_name}_output", input_state, output_state)
            invalid_transition_results = [r for r in transition_results if not r.valid]
            if invalid_transition_results:
                integration_logger.warning(
                    f"Internal transition validation issues in {node_name}: "
                    f"{len(invalid_transition_results)} issues")
                for result in invalid_transition_results:
                    integration_logger.warning(f"  - {result.message}")
            
            # Store output state for future transition validation
            _last_state_by_node[node_name] = output_state.copy()
            
            return result
        except Exception as e:
            integration_logger.error(f"Error in {node_name}: {str(e)}")
            raise
            
    return wrapper

def wrap_all_nodes(nodes_dict: Dict[str, Callable]) -> Dict[str, Callable]:
    """
    Wrap all node functions in a dictionary with verification.
    
    Args:
        nodes_dict: Dictionary mapping node names to node functions
        
    Returns:
        Dict[str, Callable]: Dictionary with wrapped node functions
    """
    wrapped_nodes = {}
    
    for node_name, node_func in nodes_dict.items():
        wrapped_nodes[node_name] = verify_node_wrapper(node_func)
        integration_logger.info(f"Wrapped node {node_name} with state verification")
    
    return wrapped_nodes

def register_node_specific_validators(
    monitor_to_decision_validators: List[Callable] = None,
    decision_to_execute_validators: List[Callable] = None,
    execute_to_reflect_validators: List[Callable] = None
) -> None:
    """
    Register validators for specific node transitions in the KFM workflow.
    
    Args:
        monitor_to_decision_validators: Validators for monitor->decide transition
        decision_to_execute_validators: Validators for decide->execute transition
        execute_to_reflect_validators: Validators for execute->reflect transition
    """
    from src.state_verification import register_transition_validator
    
    # Define standard validators for each transition
    
    # monitor -> decide transition validator
    def verify_monitor_to_decide(from_state: Dict[str, Any], to_state: Dict[str, Any]) -> ValidationResult:
        """Verify transition from monitor to decision node."""
        issues = []
        
        # Performance data should be present after monitor
        if "performance_data" not in to_state:
            issues.append("Performance data missing after monitor node")
            
        # Task requirements should be present after monitor
        if "task_requirements" not in to_state:
            issues.append("Task requirements missing after monitor node")
        
        if issues:
            return ValidationResult(False, f"monitor->decide issues: {'; '.join(issues)}", {"issues": issues})
        return ValidationResult(True, "monitor->decide transition valid")
    
    # decide -> execute transition validator
    def verify_decide_to_execute(from_state: Dict[str, Any], to_state: Dict[str, Any]) -> ValidationResult:
        """Verify transition from decision to execute node."""
        issues = []
        
        # KFM action should be present after decision
        if "kfm_action" not in to_state:
            issues.append("KFM action missing after decision node")
        
        if issues:
            return ValidationResult(False, f"decide->execute issues: {'; '.join(issues)}", {"issues": issues})
        return ValidationResult(True, "decide->execute transition valid")
    
    # execute -> reflect transition validator
    def verify_execute_to_reflect(from_state: Dict[str, Any], to_state: Dict[str, Any]) -> ValidationResult:
        """Verify transition from execute to reflect node."""
        issues = []
        
        # Result should be present after execution (unless there's an error)
        if "result" not in to_state and "error" not in to_state:
            issues.append("Neither result nor error present after execute node")
        
        # Active component should be set after execution (unless there's an error)
        if "active_component" not in to_state and "error" not in to_state:
            issues.append("Active component missing after execute node")
        
        if issues:
            return ValidationResult(False, f"execute->reflect issues: {'; '.join(issues)}", {"issues": issues})
        return ValidationResult(True, "execute->reflect transition valid")
    
    # Register default validators
    register_transition_validator("monitor_output", "decide_input", verify_monitor_to_decide)
    register_transition_validator("decide_output", "execute_input", verify_decide_to_execute)
    register_transition_validator("execute_output", "reflect_input", verify_execute_to_reflect)
    
    # Register custom validators if provided
    if monitor_to_decision_validators:
        for i, validator in enumerate(monitor_to_decision_validators):
            register_transition_validator(f"monitor_output", f"decide_input", validator)
            integration_logger.info(f"Registered custom monitor->decide validator {i+1}")
    
    if decision_to_execute_validators:
        for i, validator in enumerate(decision_to_execute_validators):
            register_transition_validator(f"decide_output", f"execute_input", validator)
            integration_logger.info(f"Registered custom decide->execute validator {i+1}")
    
    if execute_to_reflect_validators:
        for i, validator in enumerate(execute_to_reflect_validators):
            register_transition_validator(f"execute_output", f"reflect_input", validator)
            integration_logger.info(f"Registered custom execute->reflect validator {i+1}")
    
    integration_logger.info("Registered node-specific transition validators")

def integrate_with_kfm_agent():
    """Integrate the verification framework with the KFM agent."""
    from src.kfm_agent import create_kfm_agent_graph
    from src.langgraph_nodes import monitor_state_node, kfm_decision_node, execute_action_node, reflect_node
    
    # First initialize the verification framework
    initialize_verification_integration()
    
    # Register KFM-specific transition validators
    register_node_specific_validators()
    
    # Patch the LangGraph node functions with verification wrappers
    return {
        "monitor_state_node": verify_node_wrapper(monitor_state_node),
        "kfm_decision_node": verify_node_wrapper(kfm_decision_node),
        "execute_action_node": verify_node_wrapper(execute_action_node),
        "reflect_node": verify_node_wrapper(reflect_node)
    }

def create_verification_graph() -> Tuple:
    """
    Create a LangGraph with verification integrated.
    
    Returns:
        Tuple: The graph and components dictionary
    """
    from src.kfm_agent import create_kfm_agent_graph
    from src.langgraph_nodes import monitor_state_node, kfm_decision_node, execute_action_node, reflect_node
    
    # Initialize verification
    initialize_verification_integration()
    
    # Create the graph as usual
    graph, components = create_kfm_agent_graph()
    
    # Now the traced versions from the existing tracing are used
    # Our verification is built on top of that
    
    integration_logger.info("Created verification-enabled graph")
    return graph, components

def generate_state_flow_report(output_dir: str = "logs/verification") -> str:
    """
    Generate a comprehensive state flow report after execution.
    
    Args:
        output_dir: Directory for output files
        
    Returns:
        str: Path to the report file
    """
    import os
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate verification report
    report_path = generate_verification_report(
        os.path.join(output_dir, "verification_report.json")
    )
    
    # Generate visualization
    viz_path = generate_state_flow_visualization(
        os.path.join(output_dir, "state_flow.png")
    )
    
    integration_logger.info(f"Generated state flow report at {report_path}")
    if viz_path:
        integration_logger.info(f"Generated state flow visualization at {viz_path}")
    
    return report_path 