"""
Recovery mechanisms for graph execution.

This module provides tools for handling error conditions during graph execution, including:
1. State rollback capability
2. Node retry mechanisms
3. Graceful failure modes
4. Partial graph execution resumption

These mechanisms enable robust execution even in the presence of transient errors
or unexpected conditions.
"""

import os
import time
import json
import logging
import traceback
import datetime
from typing import Dict, Any, List, Tuple, Optional, Callable, Union
from enum import Enum, auto
from dataclasses import dataclass, field

# Import existing capabilities for state management
from src.tracing import (
    get_state_history_tracker,
    save_state_snapshot,
    get_state_snapshot,
    trace_node,
    get_trace_history
)

from src.error_context import (
    EnhancedError, 
    capture_error_context,
    with_enhanced_error
)

from src.debugging import (
    create_state_checkpoint,
    compare_with_checkpoint,
    diff_states
)

# Set up logging
from src.logger import setup_logger
recovery_logger = setup_logger('recovery')

# Constants
MAX_RETRY_ATTEMPTS = 3
DEFAULT_BACKOFF_FACTOR = 1.5
CHECKPOINT_DIR = "logs/checkpoints"

# Ensure checkpoint directory exists
os.makedirs(CHECKPOINT_DIR, exist_ok=True)

class RecoveryMode(Enum):
    """Enum defining the different recovery modes available."""
    ABORT = auto()  # Stop execution on error
    RETRY = auto()  # Retry failed node
    ROLLBACK = auto()  # Rollback to last checkpoint
    SKIP = auto()  # Skip the failed node
    SUBSTITUTE = auto()  # Use a substitute value and continue
    PARTIAL = auto()  # Continue with partial execution

@dataclass
class RecoveryPolicy:
    """
    Define a policy for recovering from errors during execution.
    
    Attributes:
        mode: The recovery mode to use
        max_retries: Maximum number of retry attempts for a node
        backoff_factor: Factor to multiply delay between retries (for exponential backoff)
        rollback_checkpoint_id: Checkpoint ID to roll back to (if mode is ROLLBACK)
        error_categories: List of error categories this policy applies to
        fallback_function: Function to call for substitute values (if mode is SUBSTITUTE)
        custom_handler: Custom function to handle the error
    """
    mode: RecoveryMode = RecoveryMode.ABORT
    max_retries: int = MAX_RETRY_ATTEMPTS
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR
    rollback_checkpoint_id: Optional[str] = None
    error_categories: List[str] = field(default_factory=list)
    fallback_function: Optional[Callable] = None
    custom_handler: Optional[Callable] = None

class RecoveryManager:
    """
    Manages recovery mechanisms for graph execution.
    
    This class provides:
    - Checkpoint management for rollback
    - Retry mechanism with backoff
    - Error tracking and handling
    - Recovery policy enforcement
    """
    
    def __init__(self):
        """Initialize the recovery manager."""
        self.checkpoints = {}  # Dict mapping checkpoint IDs to metadata
        self.retry_counters = {}  # Dict tracking retry attempts per node
        self.recovery_policies = {}  # Dict mapping node names to recovery policies
        self.default_policy = RecoveryPolicy()
        self._undo_stack = []  # Stack of states for undo operations
        self._redo_stack = []  # Stack of states for redo operations
        recovery_logger.info("RecoveryManager initialized")
    
    def set_default_policy(self, policy: RecoveryPolicy) -> None:
        """
        Set the default recovery policy.
        
        Args:
            policy: The recovery policy to use as default
        """
        self.default_policy = policy
        recovery_logger.info(f"Default recovery policy set to {policy.mode.name}")
    
    def add_policy(self, node_name: str, policy: RecoveryPolicy) -> None:
        """
        Add a node-specific recovery policy.
        
        Args:
            node_name: Name of the node to apply the policy to
            policy: Recovery policy to apply
        """
        self.recovery_policies[node_name] = policy
        recovery_logger.info(f"Recovery policy {policy.mode.name} added for node {node_name}")
    
    def get_policy(self, node_name: str) -> RecoveryPolicy:
        """
        Get the recovery policy for a node.
        
        Args:
            node_name: Name of the node
            
        Returns:
            The recovery policy to apply for this node
        """
        return self.recovery_policies.get(node_name, self.default_policy)
    
    def create_checkpoint(self, state: Dict[str, Any], label: str) -> str:
        """
        Create a checkpoint that can be used for rollback.
        
        Args:
            state: The state to checkpoint
            label: A descriptive label for the checkpoint
            
        Returns:
            The checkpoint ID
        """
        # Leverage existing checkpoint capability
        checkpoint_id = create_state_checkpoint(
            state=state,
            label=label,
            category="recovery_checkpoint",
            description=f"Recovery checkpoint: {label}"
        )
        
        # Track in internal mapping with additional metadata
        self.checkpoints[checkpoint_id] = {
            "label": label,
            "timestamp": datetime.datetime.now().isoformat(),
            "created_by": "recovery_manager"
        }
        
        recovery_logger.info(f"Created recovery checkpoint '{label}' with ID {checkpoint_id}")
        
        # Store in undo stack
        self._undo_stack.append((checkpoint_id, state.copy()))
        # Clear redo stack when new checkpoint is created
        self._redo_stack.clear()
        
        return checkpoint_id
    
    def rollback_to_checkpoint(self, checkpoint_id: str) -> Dict[str, Any]:
        """
        Rollback state to a previously created checkpoint.
        
        Args:
            checkpoint_id: The ID of the checkpoint to roll back to
            
        Returns:
            The rolled-back state
            
        Raises:
            ValueError: If the checkpoint does not exist
        """
        # Get checkpoint data from the state history tracker
        checkpoint_data = get_state_snapshot(checkpoint_id)
        if not checkpoint_data:
            error_msg = f"Checkpoint with ID {checkpoint_id} not found for rollback"
            recovery_logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Get state and metadata
        checkpoint_state = checkpoint_data["state"]
        checkpoint_meta = checkpoint_data["metadata"]
        
        recovery_logger.info(f"Rolling back to checkpoint '{checkpoint_meta['label']}' ({checkpoint_id})")
        
        # Create a new checkpoint for the current state before rolling back
        current_state = {}  # This should be provided by the caller, but as a fallback we'll use empty dict
        for item in reversed(self._undo_stack):
            # Get the most recent state for redo if needed
            if item[0] != checkpoint_id:
                current_state = item[1]
                break
                
        # Add to redo stack
        current_time = datetime.datetime.now().isoformat()
        redo_checkpoint_id = f"redo_{current_time}"
        self._redo_stack.append((redo_checkpoint_id, current_state))
        
        return checkpoint_state
    
    def undo(self) -> Optional[Dict[str, Any]]:
        """
        Undo to the previous state checkpoint.
        
        Returns:
            The previous state or None if no previous state exists
        """
        if len(self._undo_stack) <= 1:
            recovery_logger.warning("No previous state available to undo")
            return None
        
        # Get the current state from the last checkpoint
        current_checkpoint_id, current_state = self._undo_stack.pop()
        
        # Add to redo stack
        self._redo_stack.append((current_checkpoint_id, current_state))
        
        # Get the previous state
        prev_checkpoint_id, prev_state = self._undo_stack[-1]
        
        recovery_logger.info(f"Undo to checkpoint ID {prev_checkpoint_id}")
        
        return prev_state
    
    def redo(self) -> Optional[Dict[str, Any]]:
        """
        Redo to the next state checkpoint.
        
        Returns:
            The next state or None if no next state exists
        """
        if not self._redo_stack:
            recovery_logger.warning("No next state available to redo")
            return None
        
        # Get the next state from the redo stack
        next_checkpoint_id, next_state = self._redo_stack.pop()
        
        # Add to undo stack
        self._undo_stack.append((next_checkpoint_id, next_state))
        
        recovery_logger.info(f"Redo to checkpoint ID {next_checkpoint_id}")
        
        return next_state
    
    def reset_retry_count(self, node_name: str) -> None:
        """
        Reset the retry counter for a node.
        
        Args:
            node_name: Name of the node to reset
        """
        if node_name in self.retry_counters:
            self.retry_counters[node_name] = 0
            recovery_logger.debug(f"Reset retry counter for node {node_name}")
    
    def can_retry(self, node_name: str) -> bool:
        """
        Check if a node can be retried.
        
        Args:
            node_name: Name of the node
            
        Returns:
            True if the node can be retried, False otherwise
        """
        policy = self.get_policy(node_name)
        current_retries = self.retry_counters.get(node_name, 0)
        return current_retries < policy.max_retries
    
    def get_retry_delay(self, node_name: str) -> float:
        """
        Get the delay before next retry based on backoff policy.
        
        Args:
            node_name: Name of the node
            
        Returns:
            Delay in seconds before next retry
        """
        policy = self.get_policy(node_name)
        current_retries = self.retry_counters.get(node_name, 0)
        
        # Calculate delay with exponential backoff
        delay = policy.backoff_factor ** current_retries
        recovery_logger.debug(f"Retry delay for node {node_name}: {delay:.2f}s")
        return delay
    
    def increment_retry_count(self, node_name: str) -> int:
        """
        Increment the retry counter for a node.
        
        Args:
            node_name: Name of the node
            
        Returns:
            New retry count
        """
        current_retries = self.retry_counters.get(node_name, 0)
        self.retry_counters[node_name] = current_retries + 1
        new_count = self.retry_counters[node_name]
        recovery_logger.debug(f"Incremented retry counter for {node_name} to {new_count}")
        return new_count
    
    def handle_error(self, error: Exception, state: Dict[str, Any], node_name: str) -> Tuple[RecoveryMode, Dict[str, Any]]:
        """
        Handle an error that occurred during node execution.
        
        Args:
            error: The exception that occurred
            state: The current state
            node_name: Name of the node where the error occurred
            
        Returns:
            Tuple of (recovery mode, updated state)
        """
        # Get policy for this node
        policy = self.get_policy(node_name)
        
        # Capture enhanced error context
        enhanced_error = capture_error_context(
            error=error,
            state=state,
            node_name=node_name,
            category=self._detect_error_category(error),
            severity="ERROR"
        )
        
        # Create a copy of the state with error information
        updated_state = state.copy()
        updated_state["error_type"] = type(error).__name__
        updated_state["error_message"] = str(error)
        updated_state["error_node"] = node_name
        updated_state["recovery_attempted"] = policy.mode.name
        updated_state["error"] = str(error)
        
        # Log the error using a safe method to get the error message
        error_message = str(enhanced_error) if enhanced_error else str(error)
        if hasattr(enhanced_error, 'formatted_message'):
            try:
                error_message = enhanced_error.formatted_message()
            except:
                # Fall back to string representation if formatted_message fails
                pass
        
        recovery_logger.error(f"Error in node {node_name}: {error_message}")
        
        # Get error suggestions if available
        suggestions = []
        if isinstance(enhanced_error, EnhancedError):
            suggestions = self.get_error_suggestions(enhanced_error)
        elif hasattr(enhanced_error, 'get_suggestions'):
            try:
                suggestions = enhanced_error.get_suggestions()
            except:
                pass
        
        if suggestions:
            recovery_logger.info("Suggestions for resolving the error:")
            for i, suggestion in enumerate(suggestions, 1):
                recovery_logger.info(f"  {i}. {suggestion}")
        
        # Check if there's a custom handler
        if policy.custom_handler:
            try:
                recovery_mode, updated_state = policy.custom_handler(error, state, node_name)
                if isinstance(recovery_mode, RecoveryMode):
                    recovery_logger.info(f"Using custom handler recovery mode: {recovery_mode.name}")
                    return recovery_mode, updated_state
            except Exception as handler_error:
                recovery_logger.error(f"Error in custom handler: {handler_error}")
        
        # Check if error matches any of the error categories for this policy
        if policy.error_categories and hasattr(enhanced_error, 'category'):
            # Check if category matches directly
            if enhanced_error.category in policy.error_categories:
                recovery_logger.info(f"Error category {enhanced_error.category} matches policy")
                return policy.mode, updated_state
            
            # Check for error message patterns that indicate a specific category
            error_msg = str(error).lower()
            for category in policy.error_categories:
                # Simple pattern matching for categories in error message
                if category.lower() in error_msg:
                    recovery_logger.info(f"Error message contains category {category}")
                    return policy.mode, updated_state
        
        # Apply policy based on mode
        if policy.mode == RecoveryMode.RETRY:
            # Check if we can retry
            if self.can_retry(node_name):
                retry_count = self.increment_retry_count(node_name)
                retry_delay = self.get_retry_delay(node_name)
                
                recovery_logger.info(f"Retrying node {node_name} (attempt {retry_count}/{policy.max_retries}, delay: {retry_delay}s)")
                
                # Sleep for backoff delay
                time.sleep(retry_delay)
                
                return RecoveryMode.RETRY, updated_state
            else:
                recovery_logger.warning(f"Max retries ({policy.max_retries}) exceeded for node {node_name}")
                return RecoveryMode.ABORT, updated_state
                
        elif policy.mode == RecoveryMode.ROLLBACK:
            # Check if we have a checkpoint to roll back to
            checkpoint_id = policy.rollback_checkpoint_id
            if checkpoint_id:
                try:
                    recovery_logger.info(f"Rolling back to checkpoint {checkpoint_id}")
                    rollback_state = self.rollback_to_checkpoint(checkpoint_id)
                    # Add error information to rollback state
                    rollback_state["error_type"] = updated_state["error_type"]
                    rollback_state["error_message"] = updated_state["error_message"]
                    rollback_state["error_node"] = updated_state["error_node"]
                    rollback_state["recovery_attempted"] = updated_state["recovery_attempted"]
                    rollback_state["error"] = updated_state["error"]
                    return RecoveryMode.ROLLBACK, rollback_state
                except Exception as rollback_error:
                    recovery_logger.error(f"Error during rollback: {rollback_error}")
                    return RecoveryMode.ABORT, updated_state
            else:
                recovery_logger.warning("No checkpoint ID specified for rollback")
                return RecoveryMode.ABORT, updated_state
                
        elif policy.mode == RecoveryMode.SKIP:
            recovery_logger.info(f"Skipping node {node_name} due to error")
            return RecoveryMode.SKIP, updated_state
            
        elif policy.mode == RecoveryMode.SUBSTITUTE:
            # Check if we have a fallback function
            if policy.fallback_function:
                try:
                    recovery_logger.info(f"Using fallback function for node {node_name}")
                    fallback_state = policy.fallback_function(state, node_name, error)
                    # Add error information to fallback state
                    fallback_state["error_type"] = updated_state["error_type"]
                    fallback_state["error_message"] = updated_state["error_message"]
                    fallback_state["error_node"] = updated_state["error_node"]
                    fallback_state["recovery_attempted"] = updated_state["recovery_attempted"]
                    fallback_state["error"] = updated_state["error"]
                    return RecoveryMode.SUBSTITUTE, fallback_state
                except Exception as fallback_error:
                    recovery_logger.error(f"Error in fallback function: {fallback_error}")
                    return RecoveryMode.ABORT, updated_state
            else:
                # Create generic fallback state
                recovery_logger.info(f"Creating generic fallback state for node {node_name}")
                fallback_state = create_fallback_state(state, node_name)
                # Add error information to fallback state
                fallback_state["error_type"] = updated_state["error_type"]
                fallback_state["error_message"] = updated_state["error_message"]
                fallback_state["error_node"] = updated_state["error_node"]
                fallback_state["recovery_attempted"] = updated_state["recovery_attempted"]
                fallback_state["error"] = updated_state["error"]
                return RecoveryMode.SUBSTITUTE, fallback_state
        
        # Default to ABORT
        recovery_logger.info(f"Using default recovery mode: {policy.mode.name}")
        return policy.mode, updated_state
    
    def get_error_suggestions(self, error: EnhancedError) -> List[str]:
        """
        Get suggestions for resolving an error.
        
        Args:
            error: The enhanced error
            
        Returns:
            List of suggestions
        """
        try:
            # Try to use the suggestions engine
            from src.suggestions import get_suggestions
            suggestions_result = get_suggestions(error)
            return suggestions_result.get("suggestions", [])
        except ImportError:
            # Fall back to basic suggestions
            from src.error_context import get_error_suggestions
            suggestions_result = get_error_suggestions(error)
            return suggestions_result.get("suggestions", [])
        except Exception as e:
            recovery_logger.error(f"Error getting suggestions: {e}")
            return []
    
    def _detect_error_category(self, error: Exception) -> str:
        """
        Detect the category of an error based on its type and content.
        
        Args:
            error: The exception to categorize
            
        Returns:
            Error category
        """
        error_type = type(error).__name__
        error_msg = str(error).lower()
        
        # Check for network/API related errors
        if error_type in ["ConnectionError", "HTTPError", "Timeout", "TimeoutError"] or \
           any(kw in error_msg for kw in ["api", "connection", "timeout", "network"]):
            return "API_INTEGRATION"
        
        # Check for state validation errors
        if error_type in ["KeyError", "TypeError", "ValueError", "ValidationError"] or \
           any(kw in error_msg for kw in ["missing", "required", "schema", "type", "format"]):
            return "STATE_VALIDATION"
        
        # Check for permission errors
        if error_type in ["PermissionError", "AccessDenied"] or \
           any(kw in error_msg for kw in ["permission", "access", "denied", "unauthorized"]):
            return "PERMISSION"
        
        # Check for resource errors
        if error_type in ["MemoryError", "DiskError"] or \
           any(kw in error_msg for kw in ["memory", "disk", "resource", "limit"]):
            return "RESOURCE"
        
        # Default to GRAPH_EXECUTION
        return "GRAPH_EXECUTION"

def resume_execution_from_node(app, state: Dict[str, Any], node_name: str) -> Dict[str, Any]:
    """
    Resume execution of a graph from a specific node.
    
    Args:
        app: The LangGraph app
        state: The current state
        node_name: Name of the node to resume from
        
    Returns:
        Updated state after execution
        
    Raises:
        ValueError: If the node is not found
    """
    nodes = list(app.graph.nodes)
    
    if node_name not in nodes:
        raise ValueError(f"Node '{node_name}' not found in graph")
    
    # Find the index of the starting node
    start_index = nodes.index(node_name)
    
    recovery_logger.info(f"Resuming execution from node {node_name} (index {start_index + 1}/{len(nodes)})")
    
    # Create a checkpoint before resuming
    recovery_manager = RecoveryManager()
    checkpoint_id = recovery_manager.create_checkpoint(
        state=state,
        label=f"Resume from {node_name}"
    )
    
    # Execute each node from the starting point
    current_state = state.copy()
    for i in range(start_index, len(nodes)):
        current_node = nodes[i]
        
        recovery_logger.info(f"Executing node {i+1}/{len(nodes)}: {current_node}")
        
        try:
            # Get the node function
            node_func = app.graph.get_node(current_node)["fn"]
            
            # Execute the node
            node_state_before = current_state.copy()
            current_state = node_func(current_state)
            
            # Log state changes using the tracing system's state history tracker
            tracker = get_state_history_tracker()
            if tracker:
                tracker.add_state(
                    node_name=current_node,
                    state=current_state,
                    is_input=False,
                    metadata={
                        "success": True,
                        "resumed_execution": True,
                        "duration": 0.0,  # We don't have timing info here
                    }
                )
            
        except Exception as e:
            recovery_logger.error(f"Error executing node {current_node}: {str(e)}")
            
            # Log error in trace history using the state history tracker
            tracker = get_state_history_tracker()
            if tracker:
                tracker.add_state(
                    node_name=current_node,
                    state=current_state,
                    is_input=True,  # This was the input state that caused the error
                    metadata={
                        "success": False,
                        "resumed_execution": True,
                        "error": str(e),
                        "duration": 0.0,  # We don't have timing info here
                    }
                )
            
            # Get recovery policy
            policy = recovery_manager.get_policy(current_node)
            
            # Handle error based on policy
            recovery_mode, updated_state = recovery_manager.handle_error(
                error=e,
                state=current_state,
                node_name=current_node
            )
            
            # Update current state
            current_state = updated_state
            
            # Add error and recovery information for test verification
            if "error_type" not in current_state:
                current_state["error_type"] = type(e).__name__
            if "error" not in current_state:
                current_state["error"] = str(e)
            current_state["recovery_attempted"] = recovery_mode.name
            
            # Based on recovery mode, decide whether to continue
            if recovery_mode == RecoveryMode.ABORT:
                recovery_logger.warning("Aborting execution due to error")
                break
            elif recovery_mode == RecoveryMode.RETRY:
                # Retry is handled in handle_error, just re-execute the same node
                i -= 1
                continue
            # For other modes, continue to next node
    
    # Return the final state
    return current_state

def verify_safe_resumption(state: Dict[str, Any], required_keys: List[str]) -> bool:
    """
    Verify that a state is safe for resumption.
    
    Args:
        state: The state to verify
        required_keys: List of keys that must be present for safe resumption
        
    Returns:
        True if the state is safe for resumption, False otherwise
    """
    # Check required keys exist in state
    missing_keys = [key for key in required_keys if key not in state]
    if missing_keys:
        recovery_logger.warning(f"State missing required keys for safe resumption: {', '.join(missing_keys)}")
        return False
    
    # Check for incomplete state
    if state.get("_recovery", {}).get("partial_execution"):
        recovery_logger.warning("State marked as partial execution, may not be safe for resumption")
        return False
    
    return True

def create_fallback_state(state: Dict[str, Any], node_name: str) -> Dict[str, Any]:
    """
    Create a fallback state for a node with default values.
    
    Args:
        state: The original state
        node_name: Name of the node
        
    Returns:
        A fallback state with safe defaults
    """
    fallback_state = state.copy()
    
    # Add fallback marker
    fallback_state["_recovery"] = {
        "fallback_applied": True,
        "node_name": node_name,
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    # Common fallback patterns based on node name patterns
    if "validate" in node_name.lower():
        fallback_state["validation_results"] = {"valid": False, "errors": ["Using fallback validation"]}
    elif "process" in node_name.lower():
        fallback_state["processing_complete"] = True
    elif "execute" in node_name.lower():
        fallback_state["execution_complete"] = True
        fallback_state["result"] = {"fallback": True, "message": "Default fallback result"}
    
    recovery_logger.info(f"Created fallback state for node {node_name}")
    
    return fallback_state

@with_enhanced_error(category="RECOVERY", severity="ERROR")
def with_recovery(app, initial_state: Dict[str, Any], 
                policies: Optional[Dict[str, RecoveryPolicy]] = None,
                default_policy: Optional[RecoveryPolicy] = None) -> Dict[str, Any]:
    """
    Execute a graph with recovery mechanisms.
    
    Args:
        app: The LangGraph app
        initial_state: Initial state for execution
        policies: Dict mapping node names to recovery policies
        default_policy: Default recovery policy
        
    Returns:
        Final state after execution
    """
    # Initialize recovery manager
    recovery_manager = RecoveryManager()
    
    # Set policies
    if default_policy:
        recovery_manager.set_default_policy(default_policy)
    if policies:
        for node_name, policy in policies.items():
            recovery_manager.add_policy(node_name, policy)
    
    # Create initial checkpoint
    initial_checkpoint_id = recovery_manager.create_checkpoint(
        state=initial_state,
        label="Execution Start"
    )
    
    # Get nodes
    nodes = list(app.graph.nodes)
    recovery_logger.info(f"Starting execution with recovery for {len(nodes)} nodes")
    
    # Execute each node with recovery
    current_state = initial_state.copy()
    for i, node_name in enumerate(nodes):
        recovery_logger.info(f"Executing node {i+1}/{len(nodes)}: {node_name}")
        
        # Reset retry counter for this node
        recovery_manager.reset_retry_count(node_name)
        
        # Create checkpoint before node execution
        pre_node_checkpoint_id = recovery_manager.create_checkpoint(
            state=current_state,
            label=f"Before {node_name}"
        )
        
        # Execute node with retry logic
        retry_count = 0
        max_retries = recovery_manager.get_policy(node_name).max_retries
        executed = False
        
        while not executed and retry_count <= max_retries:
            try:
                # Get the node function
                node_func = app.graph.get_node(node_name)["fn"]
                
                # Execute the node
                node_state_before = current_state.copy()
                current_state = node_func(current_state)
                
                # Log state changes using the tracing system
                tracker = get_state_history_tracker()
                if tracker:
                    tracker.add_state(
                        node_name=node_name,
                        state=current_state,
                        is_input=False,
                        metadata={
                            "success": True,
                            "retry_count": retry_count,
                            "duration": 0.0,  # We don't have timing info here
                        }
                    )
                
                executed = True
                
            except Exception as e:
                retry_count += 1
                recovery_logger.warning(f"Error in node {node_name} (attempt {retry_count}): {str(e)}")
                
                # Log error in trace history using the state history tracker
                tracker = get_state_history_tracker()
                if tracker:
                    tracker.add_state(
                        node_name=node_name,
                        state=node_state_before,  # Use the input state
                        is_input=True,
                        metadata={
                            "success": False,
                            "error": str(e),
                            "retry_count": retry_count,
                            "duration": 0.0,  # We don't have timing info here
                        }
                    )
                
                # Handle error based on policy
                recovery_mode, updated_state = recovery_manager.handle_error(
                    error=e,
                    state=current_state,
                    node_name=node_name
                )
                
                # Update current state
                current_state = updated_state
                
                # Add error and recovery information for test verification
                if "error_type" not in current_state:
                    current_state["error_type"] = type(e).__name__
                if "error" not in current_state:
                    current_state["error"] = str(e)
                current_state["recovery_attempted"] = recovery_mode.name
                
                # Based on recovery mode, decide whether to retry or continue
                if recovery_mode == RecoveryMode.RETRY and retry_count <= max_retries:
                    continue
                elif recovery_mode == RecoveryMode.ABORT:
                    recovery_logger.warning("Aborting execution due to error")
                    return current_state
                else:
                    # For other modes, mark as executed and continue to next node
                    executed = True
        
        # Create post-node checkpoint
        post_node_checkpoint_id = recovery_manager.create_checkpoint(
            state=current_state,
            label=f"After {node_name}"
        )
    
    # Create final checkpoint
    final_checkpoint_id = recovery_manager.create_checkpoint(
        state=current_state,
        label="Execution Complete"
    )
    
    recovery_logger.info("Execution with recovery completed successfully")
    
    return current_state 