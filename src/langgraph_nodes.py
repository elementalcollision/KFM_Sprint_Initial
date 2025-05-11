# src/langgraph_nodes.py
from typing import Tuple, Dict, Any, Optional, Union, Literal, cast
from src.state_types import KFMAgentState, ActionType
# Import core classes needed by nodes
from src.core.state_monitor import StateMonitor
from src.core.kfm_planner_llm import KFMPlannerLlm
from src.core.kfm_planner import KFMPlanner
from src.core.execution_engine import ExecutionEngine, ExecutionResult
from src.logger import setup_logger
from src.tracing import trace_node
from src.exceptions import (
    LLMAuthenticationError, LLMAPIError, LLMNetworkError, LLMTimeoutError, 
    LLMConnectionError, LLMRateLimitError, LLMServerError, LLMServiceUnavailableError,
    LLMInvalidRequestError, LLMClientError
)
import os
import json
import datetime
import traceback
import time
import uuid
import httpx
from dotenv import load_dotenv
import copy
import asyncio # Added for running async snapshot calls
import logging

# Import for Reversibility System
from src.core.reversibility.snapshot_service import SnapshotService # Added

# Import advanced error handling components
from src.retry_strategy import (
    retry_on_network_errors, retry_on_rate_limit, retry_on_server_errors,
    retry_all_api_errors, _circuit_breaker, get_retry_metrics
)
from src.error_classifier import classify_error
from src.error_recovery import (
    TokenBucketRateLimiter, RequestQueueManager, NetworkConnectionManager, 
    ServiceHealthMonitor, ErrorRecoveryStrategies
)
from src.llm_logging import (
    create_request_context, create_timer, calculate_performance_metrics,
    log_request, log_response, log_api_error
)
from src.core.prompt_manager import get_global_prompt_manager
from src.core.heuristic_manager import get_global_heuristic_manager

# Try to import Google Generative AI
try:
    import google.generativeai as genai
    from google.generativeai.types import GenerationConfig, HarmCategory, HarmBlockThreshold
except ImportError:
    # Create a mock module for genai with necessary classes
    class MockHarmCategory:
        HARM_CATEGORY_HATE_SPEECH = "HARM_CATEGORY_HATE_SPEECH"
        HARM_CATEGORY_DANGEROUS_CONTENT = "HARM_CATEGORY_DANGEROUS_CONTENT"
        HARM_CATEGORY_SEXUALLY_EXPLICIT = "HARM_CATEGORY_SEXUALLY_EXPLICIT"
        HARM_CATEGORY_HARASSMENT = "HARM_CATEGORY_HARASSMENT"
    
    class MockHarmBlockThreshold:
        BLOCK_MEDIUM_AND_ABOVE = "BLOCK_MEDIUM_AND_ABOVE"
        BLOCK_ONLY_HIGH = "BLOCK_ONLY_HIGH"
        BLOCK_NONE = "BLOCK_NONE"
    
    class MockGenerationConfig:
        def __init__(self, temperature=0.7, top_p=0.95, top_k=40, max_output_tokens=1024, **kwargs):
            self.temperature = temperature
            self.top_p = top_p
            self.top_k = top_k
            self.max_output_tokens = max_output_tokens
            for key, value in kwargs.items():
                setattr(self, key, value)
    
    class MockGenerativeModel:
        def __init__(self, model_name="gemini-pro", **kwargs):
            self.model_name = model_name
            
        def generate_content(self, prompt, generation_config=None, safety_settings=None, **kwargs):
            class MockResponse:
                def __init__(self, prompt):
                    self.text = f"This is a mock response for: {prompt[:30]}..."
            return MockResponse(prompt)
    
    # Create mock genai module with necessary components
    class MockGenAI:
        def __init__(self):
            self.HarmCategory = MockHarmCategory
            self.HarmBlockThreshold = MockHarmBlockThreshold
            self.GenerationConfig = MockGenerationConfig
            
        def configure(self, api_key=None, **kwargs):
            pass
            
        def GenerativeModel(self, model_name="gemini-pro", **kwargs):
            return MockGenerativeModel(model_name, **kwargs)
    
    # Create the mock module
    genai = MockGenAI()
    HarmCategory = MockHarmCategory
    HarmBlockThreshold = MockHarmBlockThreshold
    GenerationConfig = MockGenerationConfig

# Setup loggers for nodes
monitor_logger = setup_logger('MonitorNode')
decision_logger = setup_logger('DecisionNode')
execution_logger = setup_logger('ExecutionNode')
reflect_logger = setup_logger('ReflectionNode')
fallback_logger = setup_logger('FallbackNode') # Added for fallback_node

# Additional logs for reflection
reflection_log = setup_logger('ReflectionLog', level='INFO', console=True, file=True)

# Dedicated logger for semantic state details
SEMANTIC_STATE_LOGGER = setup_logger(
    'SemanticStateLogger', 
    level='INFO', 
    console=False,  # Typically don't want these detailed JSON logs in console
    file=True, 
    filename="semantic_state_details.log" # Specific filename
)

# Constants for error severity levels
ERROR_SEVERITY = {
    "INFO": 1,       # Informational, no impact on execution
    "WARNING": 2,    # Warning, may impact execution quality but not critical
    "ERROR": 3,      # Error, impacts execution but recoverable
    "CRITICAL": 4    # Critical, execution cannot continue
}

# Define error categories by phase
ERROR_CATEGORIES = {
    "kfm_action": "Error applying KFM action",
    "component_retrieval": "Error retrieving active component",
    "task_execution": "Error executing task",
    "component_error": "Component reported error", 
    "unexpected": "Unexpected error during execution"
}

# Define Heuristic ID and Parameter Name for fallback threshold
FALLBACK_RULES_ID = "planner_fallback_rules"
CONFIDENCE_THRESHOLD_PARAM = "confidence_threshold"
DEFAULT_CONFIDENCE_THRESHOLD = 0.7 # Define default value

# Register the default fallback threshold at module load time
_heuristic_manager_lg_nodes = get_global_heuristic_manager()
_heuristic_manager_lg_nodes.register_heuristic(
    FALLBACK_RULES_ID,
    {CONFIDENCE_THRESHOLD_PARAM: DEFAULT_CONFIDENCE_THRESHOLD},
    version=1
)

# --- Helper function for logging semantic state ---
def log_semantic_state_details(
    state: KFMAgentState,
    event_tag: str,
    logger: logging.Logger = SEMANTIC_STATE_LOGGER, # Default to the new semantic logger
    calculated_metrics: Optional[Dict[str, Any]] = None # New parameter
):
    """Logs critical semantic details from KFMAgentState for transparency."""
    if not state:
        # Use a general logger if state is None, as specific loggers might not be contextually appropriate
        logging.warning(f"Attempted to log semantic state for '{event_tag}' but state is None.") # logging.warning, not logger.warning
        return

    details_to_log = {
        "event_tag": event_tag,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "run_id": state.get("run_id"),
        "original_correlation_id": state.get("original_correlation_id"),
        "input_data": state.get("input"),
        "task_name": state.get("task_name"),
        "performance_data": state.get("performance_data"),
        "current_task_requirements": state.get("current_task_requirements") or state.get("task_requirements"),
        "kfm_action": state.get("kfm_action"),
        "active_component": state.get("active_component"),
        "activation_type": state.get("activation_type"),
        "result": state.get("result"),
        "execution_performance": state.get("execution_performance"),
        "error": state.get("error"),
        "reflection_output": state.get("reflection_output"),
        "done": state.get("done", False) 
    }

    if calculated_metrics:
        details_to_log["calculated_metrics"] = calculated_metrics

    try:
        logger.info(json.dumps(details_to_log, default=str)) # Use default=str for safety
    except TypeError as e:
        logger.error(f"Error serializing semantic state details for '{event_tag}': {e}", exc_info=True)
        try:
            fallback_log_message = {k: str(v) for k, v in details_to_log.items()}
            logger.info(json.dumps(fallback_log_message, default=str))
        except Exception as fallback_e:
            # For critical failures, log with a more general logger if the passed one is problematic
            logging.critical(f"CRITICAL: Failed to serialize semantic state even with fallback for '{event_tag}': {fallback_e}", exc_info=True)
            logging.info(f"RAW_FALLBACK_LOG for '{event_tag}': {str(details_to_log)}") # Use logging.info

# --- Conditional Routing Logic ---

# CONFIDENCE_THRESHOLD = 0.7 # Revert to original value - REMOVED, now managed by HeuristicManager

def should_fallback(state: KFMAgentState) -> Literal["fallback", "execute"]:
    """Determines routing based on KFM decision confidence."""
    kfm_decision = state.get('kfm_action')
    
    # Get the current confidence threshold from the HeuristicManager
    confidence_threshold = get_global_heuristic_manager().get_parameter(
        heuristic_id=FALLBACK_RULES_ID, 
        parameter_name=CONFIDENCE_THRESHOLD_PARAM, 
        default=DEFAULT_CONFIDENCE_THRESHOLD
    )
    
    log_props_base = {
        "event_type": "should_fallback_check",
        "task_name": state.get('task_name'),
        "kfm_action_type": kfm_decision.get('action') if kfm_decision and isinstance(kfm_decision, dict) else None,
        "kfm_confidence": kfm_decision.get('confidence') if kfm_decision and isinstance(kfm_decision, dict) else None,
        "kfm_error_info": kfm_decision.get('error_info') if kfm_decision and isinstance(kfm_decision, dict) else None # Log error_info
    }

    if not kfm_decision or not isinstance(kfm_decision, dict):
        decision_logger.error(
            "Fallback triggered: kfm_action missing or invalid in state.",
            extra={"props": {**log_props_base, "reason": "kfm_action_missing_or_invalid"}}
        )
        return "fallback"
        
    confidence = kfm_decision.get('confidence')
    action = kfm_decision.get('action')
    
    if confidence is None:
        decision_logger.warning(
            f"Fallback triggered: Confidence missing in KFM decision for action '{action}'.",
            extra={"props": {**log_props_base, "reason": "confidence_missing"}}
        )
        return "fallback"

    if confidence < confidence_threshold:
        decision_logger.warning(
            f"Fallback triggered: Confidence ({confidence:.2f}) below threshold ({confidence_threshold}) for action '{action}'.",
            extra={"props": {**log_props_base, "reason": "confidence_below_threshold", "threshold": confidence_threshold}}
        )
        return "fallback"
    
    if kfm_decision.get('error_info'):
         decision_logger.warning(
            f"KFM decision for action '{action}' contains error_info. Evaluating for fallback.",
             extra={"props": {**log_props_base, "reason": "kfm_decision_has_error_info"}}
         )
         # Policy: If there's any error_info from the planner, trigger fallback regardless of confidence for safety.
         # This ensures a human or a more robust rule-based system reviews it.
         decision_logger.warning(
            f"Fallback triggered: KFM action for '{action}' has error_info present.",
            extra={"props": {**log_props_base, "reason": "error_info_present_triggers_fallback"}}
         )
         return "fallback" 
            
    decision_logger.info(
        f"Proceeding to execute: Confidence ({confidence:.2f}) meets threshold ({confidence_threshold}) for action '{action}'.",
        extra={"props": {**log_props_base, "outcome": "execute", "threshold": confidence_threshold}}
    )
    return "execute"

# Define Prompt ID for reflection prompt
REFLECTION_PROMPT_BASE_ID = "reflection_prompt_base_v1"

# Define the base template content
_REFLECTION_PROMPT_BASE_TEMPLATE_CONTENT = """# KFM Agent Reflection Analysis

## Context
You are analyzing a Knowledge Flow Management (KFM) decision made by an AI agent. The agent follows a "Keep-Marry-Kill" framework for managing AI components:
- KEEP: Continue using the component as is
- MARRY: Enhance or integrate the component with others
- KILL: Remove or replace the component
- FUCK: Temporarily use a component that partially meets requirements as a compromise.

## Decision Details
- KFM Action: {action_type_upper}
- Component Affected: '{component}'
- Activation Method: '{current_activation_type_upper}' (Indicates how '{active_component}' became active)
- Reason Given for KFM Action: "{reason}"
- Active Component Used for Execution: '{active_component}'
- Performance Metrics (of '{active_component}' during execution):
  - Latency: {latency}
  - Accuracy: {accuracy}
- Execution Results: {result}

## Reflection Questions
1. Was the {action_type_upper} decision appropriate given the performance metrics, requirements, and the activation method ('{current_activation_type_upper}')?
2. How effective was the execution of this decision using component '{active_component}'?
3. What were the specific strengths of this decision and execution?
4. What could be improved in future similar scenarios?
5. Are there any patterns or insights to be gained for future KFM decisions?

## Output Format Requirements
Structure your response using these exact Markdown headings:
```
# Reflection on {action_type_title} Decision for Component '{component}'

## Decision Analysis
[Your analysis of whether the decision was appropriate]

## Execution Assessment
[Your assessment of the execution effectiveness]
- Latency: {latency}
- Accuracy: {accuracy}

## Strengths
- [Specific strength 1]
- [Specific strength 2]
- [Specific strength 3]

## Areas for Improvement
- [Specific improvement 1]
- [Specific improvement 2]

## Patterns and Insights
[Analysis of patterns and insights]

## Recommendation
[Concrete recommendation for future actions]
```

## Guidelines
- Be specific and objective in your analysis
- Base your assessment on the performance metrics and execution results
- Provide concrete, actionable recommendations
- Consider both short-term outcomes and long-term implications
- Keep your total response under 500 words
"""

# Register the base reflection prompt at module load time
_prompt_manager_lg_nodes = get_global_prompt_manager()
_prompt_manager_lg_nodes.register_prompt(REFLECTION_PROMPT_BASE_ID, _REFLECTION_PROMPT_BASE_TEMPLATE_CONTENT, version=1)

def format_error_info(
    error_type: str,
    message: str,
    category: str = "GENERAL",
    severity: int = ERROR_SEVERITY["ERROR"],
    traceback_info: str = None,
    recoverable: bool = True,
    details: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Format error information consistently for logging and state updates.
    
    Args:
        error_type: The type or class of error
        message: The error message
        category: Error category for classification
        severity: Error severity level (0-4)
        traceback_info: Optional stack trace
        recoverable: Whether the error is potentially recoverable
        details: Additional structured details about the error
        
    Returns:
        Dict with formatted error information
    """
    error_info = {
        "type": error_type,
        "message": message,
        "category": category,
        "severity": severity,
        "timestamp": datetime.datetime.now().isoformat(),
        "recoverable": recoverable
    }
    
    if traceback_info:
        error_info["traceback"] = traceback_info
        
    if details:
        error_info["details"] = details
        
    return error_info

@trace_node
async def monitor_state_node(state: KFMAgentState, state_monitor: StateMonitor, snapshot_service: SnapshotService) -> KFMAgentState:
    """Monitors the agent's state and logs relevant information."""
    log_semantic_state_details(state, "monitor_state_node_entry")
    try:
        monitor_logger.info("Monitoring state...", extra={"props": {"run_id": state.get('run_id')}})
        start_time = time.perf_counter()
        current_state_copy = cast(Dict[str, Any], state.copy())
        current_state_copy["last_snapshot_ids"] = current_state_copy.get("last_snapshot_ids", {})

        original_correlation_id = current_state_copy.get("original_correlation_id", str(uuid.uuid4()))
        if "original_correlation_id" not in current_state_copy: 
            current_state_copy["original_correlation_id"] = original_correlation_id
            monitor_logger.warning(f"MonitorNode: original_correlation_id not set, generated: {original_correlation_id}")
        
        run_id = current_state_copy.get("run_id", original_correlation_id)
        if "run_id" not in current_state_copy: 
            current_state_copy["run_id"] = run_id
            monitor_logger.warning(f"MonitorNode: run_id not set, generated: {run_id}")
        
        monitor_logger.info(f"MonitorNode: run_id={run_id}, original_correlation_id={original_correlation_id}")

        try:
            snapshot_id = await snapshot_service.take_snapshot(
                trigger=f"monitor_entry_run_{run_id}",
                kfm_agent_state=current_state_copy,
                additional_metadata={
                    "original_correlation_id": original_correlation_id, "run_id": run_id,
                    "node": "monitor_state_node", "step": "entry"
                }
            )
            if snapshot_id:
                current_state_copy["last_snapshot_ids"]["monitor_entry"] = snapshot_id
                monitor_logger.info(f"Monitor entry snapshot taken: {snapshot_id}")
            else:
                monitor_logger.warning("Monitor entry snapshot call returned None.")
                current_state_copy["error"] = format_error_info("SnapshotError", "Failed to take monitor entry snapshot (returned None).")
        except Exception as e:
            monitor_logger.error(f"Failed to take monitor entry snapshot: {e}", exc_info=True)
            current_state_copy["error"] = format_error_info("SnapshotError", f"Failed to take monitor entry snapshot: {str(e)}", traceback_info=traceback.format_exc())

        if current_state_copy.get("error"):
            monitor_logger.warning(f"MonitorNode: Error detected before core logic: {current_state_copy['error']}. Skipping monitor logic.")
            duration = time.perf_counter() - start_time
            monitor_logger.info(f"--- Exiting Monitor State Node early due to error (Duration: {duration:.4f}s) ---")
            return current_state_copy

        all_component_details = state_monitor.component_registry.get_all_component_details()
        current_state_copy['all_components_details'] = all_component_details
        monitor_logger.info(f"All component details fetched: {json.dumps(all_component_details, indent=2)}")

        current_task_requirements = state_monitor.get_task_requirements(current_state_copy.get('task_name'))
        current_state_copy['current_task_requirements'] = current_task_requirements
        monitor_logger.info(f"Current task requirements for '{current_state_copy.get('task_name')}': {current_task_requirements}")
        
        # The active_component should already be in the state or decided by the planner.
        # Monitor node just observes and logs it.
        active_component_in_state = current_state_copy.get('active_component')
        if active_component_in_state:
            monitor_logger.info(f"Observed active component in state: {active_component_in_state}")
        else:
            monitor_logger.warning("No active_component found in current state. Planner will need to decide.")

        current_state_copy['error'] = None 
        current_state_copy['done'] = False
        
        duration = time.perf_counter() - start_time
        monitor_logger.info(f"--- Exiting Monitor State Node (Duration: {duration:.4f}s) ---")
        return current_state_copy
    finally:
        # Ensure state is returned
        # log_semantic_state_details(state, "monitor_state_node_exit") # Not strictly necessary if state isn't modified here
        pass

@trace_node
async def kfm_decision_node(state: KFMAgentState, kfm_planner: KFMPlannerLlm, snapshot_service: SnapshotService) -> KFMAgentState:
    """Makes a KFM decision based on the current state."""
    log_semantic_state_details(state, "kfm_decision_node_entry")
    
    updated_state = cast(KFMAgentState, copy.deepcopy(dict(state))) # Ensure it's a mutable copy and treated as KFMAgentState
    current_task_name = updated_state.get('task_name', "Unknown Task")
    decision_logger.info("--- Entering KFM Decision Node ---")
    start_time = time.perf_counter()
    current_state_copy = cast(Dict[str, Any], state.copy())
    current_state_copy["last_snapshot_ids"] = current_state_copy.get("last_snapshot_ids", {})

    correlation_id = current_state_copy.get("original_correlation_id", "unknown_correlation_id")
    run_id = current_state_copy.get("run_id", correlation_id)
    decision_logger.info(f"[corr:{correlation_id}, run:{run_id}] Starting KFM decision phase.")

    try:
        snapshot_id = await snapshot_service.take_snapshot(
            trigger=f"decision_entry_corr_{correlation_id}_run_{run_id}",
            kfm_agent_state=current_state_copy,
            additional_metadata={
                "original_correlation_id": correlation_id, "run_id": run_id,
                "node": "kfm_decision_node", "step": "entry"
            }
        )
        if snapshot_id:
            current_state_copy["last_snapshot_ids"]["decision_entry"] = snapshot_id
            decision_logger.info(f"[corr:{correlation_id}, run:{run_id}] Decision entry snapshot: {snapshot_id}")
        else:
            decision_logger.warning(f"[corr:{correlation_id}, run:{run_id}] Decision entry snapshot call returned None.")
    except Exception as e_snap:
        decision_logger.error(f"[corr:{correlation_id}, run:{run_id}] Failed to take decision_entry snapshot: {e_snap}", exc_info=True)
        current_state_copy["error"] = format_error_info("SnapshotError", f"Failed: decision_entry snapshot: {str(e_snap)}", traceback_info=traceback.format_exc())

    if current_state_copy.get("error") or current_state_copy.get("done"):
        decision_logger.warning(f"[corr:{correlation_id}, run:{run_id}] Skipping planner due to error/done: {current_state_copy.get('error')}")
        if not current_state_copy.get("kfm_action"): # Ensure some action if none decided
             current_state_copy["kfm_action"] = {"action": "No Action", "reasoning": "Error or done before planner", "confidence": 0.0, "error_info": current_state_copy.get('error')}
        duration = time.perf_counter() - start_time
        decision_logger.info(f"--- Exiting KFM Decision Node early (Duration: {duration:.4f}s) ---")
        return current_state_copy

    try:
        kfm_action_result = await kfm_planner.decide_kfm_action(current_state_copy)
        current_state_copy["kfm_action"] = kfm_action_result
        decision_logger.info(f"[corr:{correlation_id}, run:{run_id}] Planner decision: {kfm_action_result.get('action')} for {kfm_action_result.get('component')}")
    except Exception as e_planner:
        decision_logger.error(f"[corr:{correlation_id}, run:{run_id}] Error during KFM planner execution: {e_planner}", exc_info=True)
        error_info = format_error_info("PlannerError", f"KFM Planner failed: {str(e_planner)}", traceback_info=traceback.format_exc())
        current_state_copy["error"] = error_info
        current_state_copy["kfm_action"] = {"action": "No Action", "reasoning": "Planner failed", "confidence": 0.0, "error_info": error_info}
        # Fallback will be triggered by should_fallback due to error_info
    
    kfm_action_details = current_state_copy.get("kfm_action", {"action": "Unknown"})
    snap_metadata_post_planner = {
        "original_correlation_id": correlation_id, "run_id": run_id,
        "node": "kfm_decision_node", "step": "post_planner",
        "kfm_action_details": kfm_action_details
    }
    trigger_event_detail = f"decision_post_planner_corr_{correlation_id}_run_{run_id}"
    if kfm_action_details.get("action") == "Fuck":
        snap_metadata_post_planner["is_fuck_action_pre_snapshot"] = True
        trigger_event_detail = f"decision_post_planner_pre_fuck_corr_{correlation_id}_run_{run_id}"
        decision_logger.info(f"[corr:{correlation_id}, run:{run_id}] Tagging snapshot as pre-Fuck action.")

    try:
        snapshot_id = await snapshot_service.take_snapshot(
            trigger=trigger_event_detail,
            kfm_agent_state=current_state_copy,
            additional_metadata=snap_metadata_post_planner
        )
        if snapshot_id:
            current_state_copy["last_snapshot_ids"]["decision_post_planner"] = snapshot_id
            decision_logger.info(f"[corr:{correlation_id}, run:{run_id}] Post-planner snapshot: {snapshot_id}")
            if kfm_action_details.get("action") == "Fuck":
                current_state_copy["last_snapshot_ids"]["decision_post_planner_pre_fuck"] = snapshot_id
        else:
            decision_logger.warning(f"[corr:{correlation_id}, run:{run_id}] Post-planner snapshot call returned None.")
    except Exception as e_snap_post:
        decision_logger.error(f"[corr:{correlation_id}, run:{run_id}] Failed: post-planner snapshot: {e_snap_post}", exc_info=True)

    duration = time.perf_counter() - start_time
    decision_logger.info(f"--- Exiting KFM Decision Node (Duration: {duration:.4f}s) ---")

    # Log final decision details here
    decision_logger.info(
        f"Final KFM decision for task '{current_task_name}': Action='{kfm_action_details.get('action')}', Component='{kfm_action_details.get('component')}'",
        extra={"props": {"kfm_decision": kfm_action_details, "run_id": updated_state.get('run_id')}}
    )
    updated_state['kfm_action'] = kfm_action_details
    log_semantic_state_details(updated_state, "kfm_decision_node_exit_with_decision")
    return updated_state

@trace_node
async def execute_action_node(state: KFMAgentState, execution_engine: ExecutionEngine, snapshot_service: SnapshotService) -> KFMAgentState:
    """Executes the KFM action using the ExecutionEngine."""
    log_semantic_state_details(state, "execute_action_node_entry")
    start_time = time.perf_counter() # Ensure start_time is defined here
    
    updated_state = cast(KFMAgentState, copy.deepcopy(dict(state)))
    kfm_action = updated_state.get('kfm_action')

    # Initialize variables that will be used in success/error paths
    action_type_enum: Optional[ActionType] = None
    target_component_name: Optional[str] = None
    execution_succeeded = False # Flag to track success for logging

    if not kfm_action or not isinstance(kfm_action, dict) or not kfm_action.get("action"):
        execution_logger.error(f"[corr:{updated_state.get('original_correlation_id', 'unknown_corr')}, run:{updated_state.get('run_id', 'unknown_run')}] No valid KFM action. Skipping execution.")
        updated_state["error"] = format_error_info("ExecutionError", "No valid KFM action to execute.")
        updated_state["done"] = True
        log_semantic_state_details(updated_state, "execute_action_node_exit_no_action") # Log for this specific exit
        # duration = time.perf_counter() - start_time # Duration logging is in finally
        # execution_logger.info(f"--- Exiting Execute Action Node early (Duration: {duration:.4f}s) ---")
        return updated_state

    kfm_action_type_str = kfm_action.get("action")
    target_component_name = kfm_action.get("component")
    action_params = kfm_action.get("params", {})

    if kfm_action_type_str:
        try:
            action_type_enum = ActionType(kfm_action_type_str)
        except ValueError:
            execution_logger.warning(f"Invalid action type string: {kfm_action_type_str}, defaulting to NO_ACTION.")
            action_type_enum = ActionType.NO_ACTION
            updated_state["error"] = format_error_info("InvalidActionTypeError", f"Invalid action type: {kfm_action_type_str}")
            # Potentially log and return if this is critical enough for an early exit
            # log_semantic_state_details(updated_state, "execute_action_node_exit_invalid_action_type")
            # return updated_state

    pre_execution_snapshot_id: Optional[str] = None
    try:
        snapshot_id = await snapshot_service.take_snapshot(
            trigger=f"execute_pre_action_corr_{updated_state.get('original_correlation_id', 'unknown_corr')}_run_{updated_state.get('run_id', 'unknown_run')}",
            kfm_agent_state=updated_state,
            additional_metadata={
                "original_correlation_id": updated_state.get('original_correlation_id'), "run_id": updated_state.get('run_id'),
                "node": "execute_action_node", "step": "pre_execution",
                "intended_action": kfm_action_type_str, "target_component": target_component_name
            }
        )
        if snapshot_id:
            pre_execution_snapshot_id = snapshot_id # Keep for auto-reversal
            updated_state["last_snapshot_ids"]["execute_pre_action"] = snapshot_id
            updated_state["last_pre_execution_snapshot_id"] = snapshot_id
            execution_logger.info(f"[corr:{updated_state.get('original_correlation_id', 'unknown_corr')}, run:{updated_state.get('run_id', 'unknown_run')}] Pre-execution snapshot: {snapshot_id}")
        else:
            execution_logger.warning(f"[corr:{updated_state.get('original_correlation_id', 'unknown_corr')}, run:{updated_state.get('run_id', 'unknown_run')}] Pre-execution snapshot call returned None.")
    except Exception as snap_ex:
        execution_logger.error(f"[corr:{updated_state.get('original_correlation_id', 'unknown_corr')}, run:{updated_state.get('run_id', 'unknown_run')}] Failed: pre-execution snapshot: {snap_ex}", exc_info=True)

    try:
        execution_result_obj: ExecutionResult = await execution_engine.execute(
            action_type=action_type_enum,
            target_component=target_component_name,
            params=action_params,
            agent_state=updated_state
        )
        
        if execution_result_obj.status == "success":
            updated_state['result'] = execution_result_obj.result
            updated_state['execution_performance'] = execution_result_obj.performance
            updated_state['active_component'] = target_component_name 
            updated_state['error'] = None 
            execution_succeeded = True # Mark as success

            # Calculate Task Requirement Satisfaction
            satisfaction_indicator_str = "NotApplicable"
            num_reqs_checked = 0
            num_reqs_met = 0
            num_reqs_unmet = 0
            num_reqs_perf_missing = 0

            exec_perf = updated_state.get("execution_performance")
            task_reqs = updated_state.get("current_task_requirements")

            if isinstance(task_reqs, dict) and task_reqs: # We have requirements
                num_reqs_checked = len(task_reqs)
                if isinstance(exec_perf, dict) and exec_perf: # And we have performance data
                    for req_key, req_value in task_reqs.items():
                        if req_key in exec_perf:
                            perf_value = exec_perf[req_key]
                            # Simple direct comparison for now. 
                            # TODO: Enhance with type-specific or range comparisons if req_value format allows.
                            if perf_value == req_value:
                                num_reqs_met += 1
                            else:
                                # Could add more detail here, e.g. actual vs expected if values are simple
                                num_reqs_unmet += 1
                        else:
                            num_reqs_perf_missing += 1
                    
                    if num_reqs_checked > 0:
                        if num_reqs_met == num_reqs_checked:
                            satisfaction_indicator_str = f"MetAll ({num_reqs_met}/{num_reqs_checked})"
                        elif num_reqs_met > 0:
                            satisfaction_indicator_str = f"MetSome ({num_reqs_met}/{num_reqs_checked})"
                        else: # No requirements met, but all were checked (had perf data or perf data was missing)
                             satisfaction_indicator_str = f"MetNone ({num_reqs_met}/{num_reqs_checked})"
                        
                        details_parts = []
                        if num_reqs_unmet > 0:
                            details_parts.append(f"Unmet:{num_reqs_unmet}")
                        if num_reqs_perf_missing > 0:
                            details_parts.append(f"PerfMissing:{num_reqs_perf_missing}")
                        if details_parts:
                            satisfaction_indicator_str += f" [Details: {', '.join(details_parts)}]"
                    else: # No requirements were actually checked (e.g. task_reqs was empty after all)
                        satisfaction_indicator_str = "PerfDataAvailable_NoTrackedReqs"
                else: # Have requirements, but no performance data dictionary
                    satisfaction_indicator_str = f"ReqsDefined ({num_reqs_checked})_NoPerfData"
            elif isinstance(exec_perf, dict) and exec_perf: # No requirements, but have performance data
                satisfaction_indicator_str = "PerfDataAvailable_NoReqsDefined"
            else: # Neither requirements nor performance data (or not dicts)
                satisfaction_indicator_str = "NoReqsOrPerfData"

            current_calc_metrics = {"task_requirement_satisfaction": satisfaction_indicator_str}

            execution_logger.info(
                f"Execution completed successfully for action '{action_type_enum.value if action_type_enum else 'Unknown Action'}' on component '{target_component_name}'",
                extra={"props": {"result_summary": updated_state['result'].get("summary") if updated_state['result'] else None, 
                               "performance": updated_state['execution_performance'], 
                               "satisfaction": satisfaction_indicator_str, # Log it here too for node-specific log
                               "run_id": updated_state.get('run_id')}}
            )
            log_semantic_state_details(updated_state, "execute_action_node_exit_success", calculated_metrics=current_calc_metrics)
        else:
            # Handle non-success status from execution_result_obj that isn't an exception
            error_message = f"Execution reported non-success status: {execution_result_obj.status}. Details: {execution_result_obj.result}"
            error_info_val = format_error_info("ExecutionReportedFailure", error_message)
            updated_state['error'] = error_info_val
            updated_state['result'] = execution_result_obj.result # Still store result if any
            updated_state['execution_performance'] = execution_result_obj.performance # And performance
            execution_logger.error(error_message, extra={"props": {"error_details": error_info_val, "run_id": updated_state.get('run_id')}})
            log_semantic_state_details(updated_state, "execute_action_node_exit_reported_failure")

        return updated_state

    except Exception as e_general:
        error_message_exc = f"Exception during execution: {str(e_general)}"
        error_info_exc = format_error_info(
            error_type=type(e_general).__name__, 
            message=error_message_exc,
            traceback_info=traceback.format_exc(),
            details={"action_type": action_type_enum.value if action_type_enum else "Unknown", "component": target_component_name}
        )
        updated_state['error'] = error_info_exc
        updated_state['result'] = None 
        updated_state['execution_performance'] = None 
        execution_logger.error(
            f"Error during execution of action '{action_type_enum.value if action_type_enum else 'Unknown Action'}' on component '{target_component_name}': {error_message_exc}",
            exc_info=True,
            extra={"props": {"error_details": error_info_exc, "run_id": updated_state.get('run_id')}}
        )
        # Auto-reversal logic for "Fuck" action (if it's still here and relevant)
        if kfm_action_type_str == "Fuck" and pre_execution_snapshot_id and snapshot_service: # Check snapshot_service
            # ... (existing auto-reversal logic, ensure it uses updated_state and returns it) ...
            # If auto-reversal happens, it will return its own state. We need a log before that.
            log_semantic_state_details(updated_state, "execute_action_node_attempt_auto_reversal") 
            # The auto-reversal logic should then log its own exit state before returning.
            # For now, assume auto-reversal logic has its own return and doesn't fall through here.
            # If it *does* fall through or modifies updated_state further, that state would be logged by the generic error log below.
            pass # Placeholder if auto-reversal returns directly

        log_semantic_state_details(updated_state, "execute_action_node_exit_exception")
        return updated_state
    finally:
        # This block executes regardless of success or failure, but state should be returned from try/except
        if not updated_state.get("auto_reverted_from_snapshot"): # if not auto_reverted
            if execution_succeeded: # Check our flag
                 updated_state["done"] = True 
            # Else if error, done might be True or False based on recoverability - this is complex.
            # Current logic: if it wasn't auto-reverted, it's done with this path. Parent graph logic handles overall done.
            # For execute_action_node itself, if it didn't auto-revert, it has completed its attempt.
            updated_state["done"] = True # Simplification: executor node marks its step as done.

        # Post-execution snapshot logic (if not auto-reverted)
        if not updated_state.get("auto_reverted_from_snapshot") and snapshot_service: # Check snapshot_service
            try:
                snapshot_id = await snapshot_service.take_snapshot(
                    trigger=f"execute_post_action_corr_{updated_state.get('original_correlation_id', 'unknown_corr')}_run_{updated_state.get('run_id', 'unknown_run')}",
                    kfm_agent_state=updated_state,
                    additional_metadata={
                        "original_correlation_id": updated_state.get('original_correlation_id'), "run_id": updated_state.get('run_id'),
                        "node": "execute_action_node", "step": "post_execution",
                        "executed_action": kfm_action_type_str, "target_component": target_component_name,
                        "action_successful": execution_succeeded
                    }
                )
                if snapshot_id:
                    updated_state["last_snapshot_ids"]["execute_post_action"] = snapshot_id
                    execution_logger.info(f"[corr:{updated_state.get('original_correlation_id', 'unknown_corr')}, run:{updated_state.get('run_id', 'unknown_run')}] Post-execution snapshot: {snapshot_id}")
                else:
                    execution_logger.warning(f"[corr:{updated_state.get('original_correlation_id', 'unknown_corr')}, run:{updated_state.get('run_id', 'unknown_run')}] Post-execution snapshot call returned None.")
            except Exception as e_snap_post_exec:
                execution_logger.error(f"Failed post-execution snapshot: {e_snap_post_exec}", exc_info=True, extra={"props": {"run_id": updated_state.get('run_id')}})
        
        duration = time.perf_counter() - start_time
        execution_logger.info(f"--- Exiting Execute Action Node (Duration: {duration:.4f}s) ---", extra={"props": {"run_id": updated_state.get('run_id')}})
        # DO NOT return state from finally if it's already returned in try/except, to avoid issues.

@trace_node
async def reflect_node(state: KFMAgentState, snapshot_service: SnapshotService) -> KFMAgentState:
    """Node for reflecting on the KFM decision and execution outcome."""
    log_semantic_state_details(state, "reflect_node_entry")
    start_time = time.perf_counter() # Add for duration logging
    updated_state = cast(KFMAgentState, copy.deepcopy(dict(state)))
    
    # ... (Existing reflection logic to produce reflection_text) ...
    # Example: reflection_text = "Reflection complete."
    # updated_state['reflection_output'] = reflection_text 
    
    # Placeholder for actual reflection logic which should populate updated_state['reflection_output']
    if not updated_state.get('reflection_output'): # If not set by actual logic
        kfm_action = updated_state.get('kfm_action', {})
        action_type = kfm_action.get('action', 'Unknown Action')
        component = kfm_action.get('component', 'Unknown Component')
        updated_state['reflection_output'] = f"Placeholder reflection for {action_type} on {component}."
    
    # ... (Snapshot logic if any, using updated_state) ...

    duration = time.perf_counter() - start_time
    reflect_logger.info(f"--- Exiting Reflect Node (Duration: {duration:.4f}s) ---", extra={"props": {"run_id": updated_state.get('run_id')}})
    log_semantic_state_details(updated_state, "reflect_node_exit") # Log final state of node
    return updated_state

@trace_node
async def fallback_node(state: KFMAgentState, kfm_planner_original: KFMPlanner, snapshot_service: SnapshotService) -> KFMAgentState:
    """Handles fallback logic when KFM decision confidence is low or errors occur."""
    log_semantic_state_details(state, "fallback_node_entry")
    start_time = time.perf_counter() # Add for duration logging
    updated_state = cast(KFMAgentState, copy.deepcopy(dict(state)))
    
    # ... (Existing fallback logic, which modifies updated_state with a new kfm_action or error) ...
    # Example:
    # updated_state['kfm_action'] = {"action": "No Action", "component": "System", "reasoning": "Fallback due to previous error/low confidence", "confidence": 1.0}
    # updated_state['error'] = updated_state.get('error', "Fallback initiated.") # Preserve or set error

    # Placeholder for actual fallback logic
    if not updated_state.get('kfm_action') or updated_state.get('kfm_action', {}).get('action') != ActionType.NO_ACTION.value:
        updated_state['kfm_action'] = {
            "action": ActionType.NO_ACTION.value,
            "component": "FallbackSystem",
            "reasoning": "Fallback triggered, default NO_ACTION applied.",
            "confidence": 1.0
        }
        updated_state['error'] = updated_state.get('error', "Fallback initiated; NO_ACTION set.")

    # ... (Snapshot logic if any, using updated_state) ...

    duration = time.perf_counter() - start_time
    fallback_logger.info(f"--- Exiting Fallback Node (Duration: {duration:.4f}s) ---", extra={"props": {"run_id": updated_state.get('run_id')}})
    log_semantic_state_details(updated_state, "fallback_node_exit") # Log final state of node
    return updated_state