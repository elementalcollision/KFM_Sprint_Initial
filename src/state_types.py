from typing import TypedDict, Dict, Any, List, Optional, Union
from enum import Enum # Import Enum

class ActionType(Enum):
    KILL = "Kill"
    FUCK = "Fuck"
    MARRY = "Marry"
    NO_ACTION = "No Action"

# Defines the structure for KFM actions (Kill, Fuck, Marry)
class KFMDecision(TypedDict, total=False):
    action: str  # e.g., "Kill", "Fuck", "Marry", "No Action"
    component: str
    reasoning: Optional[str]
    confidence: Optional[float]
    error_info: Optional[Dict[str, Any]] # To store any error details from the planner

class KFMAgentState(TypedDict, total=False):
    """State definition for the KFM Agent LangGraph.
    
    This TypedDict defines the structure of the state that flows
    between nodes in the LangGraph implementation.
    """
    # Input data
    input: Dict[str, Any]  # The input data to process
    task_name: str  # Name of the current task
    
    # Performance and requirements data
    performance_data: Dict[str, Dict[str, float]]  # Component performance metrics
    task_requirements: Dict[str, float]  # Requirements for the current task
    
    # KFM decision
    kfm_action: Optional[Dict[str, str]]  # The KFM action to apply
    
    # Execution results
    active_component: Optional[str]  # Name of the active component
    activation_type: Optional[str] # How the active_component was chosen/activated (e.g., "planner_decision", "heuristic_override", "initial_default")
    result: Optional[Dict[str, Any]]  # Result from executing the task
    execution_performance: Optional[Dict[str, float]]  # Performance of the execution
    
    # Tracing and IDs
    original_correlation_id: Optional[str] # Unique ID for the entire interaction/request chain
    run_id: Optional[str] # Unique ID for a specific execution run of the graph
    last_snapshot_ids: Optional[Dict[str, str]] # IDs of the last snapshots taken in key nodes
    last_pre_execution_snapshot_id: Optional[str] # Specific snapshot ID for auto-reversal
    auto_reverted_from_snapshot: Optional[str] # ID of snapshot used for auto-reversal
    
    # Control flow
    error: Optional[str]  # Error message if something went wrong
    done: bool  # Whether the workflow is complete

    # Reflection
    reflection_output: Optional[str] # Output from the reflection step

    # Component and system details
    all_components_details: Optional[Dict[str, List[Dict[str, Any]]]] # Details about all available components
    current_task_requirements: Optional[Dict[str, Any]] # More detailed/structured task requirements 