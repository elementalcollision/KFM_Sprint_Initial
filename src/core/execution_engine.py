from src.core.component_registry import ComponentRegistry
import time
from src.logger import setup_logger
from typing import Dict, Any, Optional, Tuple, TypedDict
import asyncio # Added for asyncio.iscoroutinefunction and get_running_loop

from src.state_types import KFMAgentState, ActionType # Added imports

class ExecutionResult(TypedDict, total=False):
    status: str  # e.g., "success", "error", "auto_reverted"
    output: Optional[Dict[str, Any]] # Main output from the component or action
    message: Optional[str] # Informational message, e.g., for auto-reversal
    details: Optional[str] # Error details
    error_type: Optional[str] # Type of error if status is "error"
    performance: Optional[Dict[str, float]] # e.g., {'latency': ..., 'accuracy': ...}

class ExecutionEngine:
    """Manages the application of KFM actions (setting the active component) 
    and executes tasks using the currently active component.
    It interacts with the ComponentRegistry to get component functions.
    """
    
    def __init__(self, component_registry: ComponentRegistry):
        """Initialize the ExecutionEngine.
        
        Args:
            component_registry (ComponentRegistry): Registry of available components.
        """
        if not isinstance(component_registry, ComponentRegistry):
            raise TypeError("component_registry must be an instance of ComponentRegistry")
        self._registry = component_registry
        self._active_component_key = self._registry.get_default_component_key() 
        if self._active_component_key is None:
            available_keys = list(self._registry.list_components().keys())
            if available_keys:
                self._active_component_key = available_keys[0]
                self.logger.info(f"No default component set, initialized active component to first available: {self._active_component_key}")
            else:
                self.logger.warning("No components available in registry during ExecutionEngine initialization.")
                self._active_component_key = None # Explicitly None if no components
        
        self.logger = setup_logger('ExecutionEngine')
        self.logger.info(f"ExecutionEngine initialized. Active component: {self._active_component_key}")
    
    def apply_kfm_action(self, action: dict) -> bool:
        """Applies a KFM action (marry, fuck, kill) received from the planner.

        - 'marry' and 'fuck' actions set the specified component as the active default.
        - 'kill' actions are logged; specific deactivation logic might depend on whether
          a component name is provided and if it matches the active component.

        Args:
            action: Dictionary containing 'action' (str: 'marry'|'fuck'|'kill') 
                    and 'component' (Optional[str]) keys.
        
        Returns:
            bool: True if the action was successfully applied or recognized, False otherwise.
        """
        if not isinstance(action, dict) or 'action' not in action:
            self.logger.error(f"Invalid action format received (missing 'action' key): {action}")
            return False
            
        action_type = action['action']
        # Component can be None, especially for a generic 'kill' action
        component_name = action.get('component') 

        self.logger.info(f"Applying KFM action: Type='{action_type}', Component='{component_name if component_name else 'N/A'}'")

        previous_active_component = self._active_component_key

        if action_type == ActionType.MARRY.value or action_type == 'adjust_kfm': # Use ActionType.MARRY.value
            if not component_name:
                self.logger.error(f"Cannot apply '{action_type}' action: Component name is missing.")
                return False
            if component_name in self._registry.list_components():
                self._registry.set_default_component(component_name) # Set in registry
                self._active_component_key = component_name # Also update local active key
                self.logger.info(f"Successfully applied '{action_type}' action. Set active component to '{component_name}'. Previous: '{previous_active_component}'")
                return True
            else:
                self.logger.error(f"Cannot apply '{action_type}' action: Component '{component_name}' not found in registry.")
                return False
        elif action_type == ActionType.FUCK.value: # Use ActionType.FUCK.value
            if not component_name:
                self.logger.error(f"Cannot apply 'fuck' action: Component name is missing.")
                return False
            if component_name in self._registry.list_components():
                self._registry.set_default_component(component_name) # Set in registry
                self._active_component_key = component_name # Also update local active key
                self.logger.warning(f"KFM Action FUCK: Temporarily set active component to '{component_name}'. This is a compromise. Previous: '{previous_active_component}'")
                return True
            else:
                self.logger.error(f"Cannot apply 'fuck' action: Component '{component_name}' not found in registry.")
                return False
        elif action_type == ActionType.KILL.value: # Use ActionType.KILL.value
            # For 'kill', we might just log it or potentially deactivate a specific component if named.
            # If component_name is provided and matches active, we could set active_component to None.
            # For now, primarily logging.
            if component_name:
                self.logger.info(f"'kill' action received for component '{component_name}'. Current active: '{self._active_component_key}'")
                if component_name == self._active_component_key:
                    self.logger.warning(f"'kill' action targets the current active component '{component_name}'. Deactivation logic here if needed.")
                    # self._active_component_key = None # Example deactivation - decide if this is desired engine behavior
            else:
                self.logger.info("Generic 'kill' action received. No specific component targeted for deactivation by ExecutionEngine.")
            return True # Recognized the action
        elif action_type == ActionType.NO_ACTION.value: # Handle NO_ACTION explicitly
            self.logger.info(f"'{ActionType.NO_ACTION.value}' action received. No change to active component '{self._active_component_key}'.")
            return True
        else:
            self.logger.warning(f"Unsupported action type '{action_type}' received. No changes made.")
            return False
    
    async def execute(self, action_type: ActionType, target_component: Optional[str], params: Dict, agent_state: KFMAgentState) -> ExecutionResult:
        """
        Processes a KFM command: applies the KFM action (potentially changing the active component)
        and then executes a task using the determined active component.
        """
        self.logger.info(f"Executing KFM command: Action='{action_type.value}', TargetComponent='{target_component}'")

        # 1. Apply KFM Action (sets self._active_component_key)
        kfm_action_for_engine = {"action": action_type.value, "component": target_component}
        apply_success = self.apply_kfm_action(kfm_action_for_engine)

        # For Marry/Fuck, if apply_kfm_action fails (e.g., component not found), it's an error.
        # NO_ACTION and KILL are generally considered successful applications at this stage.
        if not apply_success and action_type in [ActionType.MARRY, ActionType.FUCK]:
            error_msg = f"Failed to apply KFM action '{action_type.value}' for component '{target_component}'."
            self.logger.error(error_msg + " Details: Component not found or invalid action.")
            return ExecutionResult(
                status="error",
                output={},
                message=error_msg,
                details="Component not found or invalid KFM action application.",
                performance={'latency': 0.0, 'accuracy': 0.0}
            )

        # 2. Execute Task with the (newly) active component
        active_component_to_run = self.get_active_component_key()
        
        if active_component_to_run is None:
             self.logger.error("Cannot execute task: No active component set or determined after KFM action.")
             return ExecutionResult(status="error", output={"error": "No active component for task execution"}, performance={'latency': 0.0, 'accuracy': 0.0})
            
        activation_type_info = agent_state.get("activation_type", "unknown")
        self.logger.info(f"Executing task with input (keys): {list(params.keys())} on active component: {active_component_to_run} (activated via: {activation_type_info})")
        self.logger.debug(f"Task input (full): {params}")
        
        component_func = self._registry.get_component(active_component_to_run)
        
        if component_func is None:
            self.logger.error(f"Cannot execute task: Active component '{active_component_to_run}' function not found in registry.")
            return ExecutionResult(status="error", output={"error": f"Component function for '{active_component_to_run}' not found"}, performance={'latency': 0.0, 'accuracy': 0.0})

        start_time_exec = time.time()
        try:
            # Assuming component_func is synchronous as per current KFM design.
            # If component_func can be async, this needs more sophisticated handling.
            # For now, run synchronous component functions in an executor to be awaitable.
            if asyncio.iscoroutinefunction(component_func):
                 result_data, component_accuracy = await component_func(params)
            else:
                 loop = asyncio.get_running_loop()
                 # component_func typically returns (result_dict, accuracy_float)
                 raw_result_tuple = await loop.run_in_executor(None, component_func, params)
                 result_data, component_accuracy = raw_result_tuple if isinstance(raw_result_tuple, tuple) and len(raw_result_tuple) == 2 else (raw_result_tuple, None)


            latency = time.time() - start_time_exec
            performance_metrics = {'latency': latency, 'accuracy': component_accuracy if component_accuracy is not None else 0.0}
            
            self.logger.info(f"Task execution on '{active_component_to_run}' completed in {latency:.4f}s. Accuracy: {component_accuracy}")
            self.logger.debug(f"Result: {result_data}, Performance: {performance_metrics}")
            
            return ExecutionResult(
                status="success",
                output=result_data,
                performance=performance_metrics
            )
        except Exception as e:
            latency = time.time() - start_time_exec
            self.logger.exception(f"Error during task execution with component '{active_component_to_run}': {e}", exc_info=True)
            return ExecutionResult(
                status="error",
                output={"error": str(e)},
                details=str(e),
                error_type=type(e).__name__,
                performance={'latency': latency, 'accuracy': 0.0}
            )

    def get_active_component_key(self) -> Optional[str]:
        """Returns the key of the currently active component."""
        return self._active_component_key