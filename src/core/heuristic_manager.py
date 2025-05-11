from typing import Dict, Optional, Any, List, Tuple
import logging
import time
import collections

from .reflection_schemas import HeuristicUpdate, HeuristicParameterAdjustment
from .update_logger import log_update

logger = logging.getLogger(__name__)

class HeuristicManager:
    """
    Manages storage, retrieval, and dynamic updates of heuristic parameters.
    """
    DEFAULT_MIN_UPDATE_INTERVAL = 60.0 # Default interval in seconds
    DEFAULT_MAX_HISTORY = 10 # Default number of history versions to keep

    def __init__(self, 
                 min_update_interval_seconds: float = DEFAULT_MIN_UPDATE_INTERVAL,
                 max_history_size: int = DEFAULT_MAX_HISTORY):
        # Structure: {heuristic_id: {param_name: value, param_name: value, ...}}
        self._heuristics: Dict[str, Dict[str, Any]] = {}
        self._heuristic_versions: Dict[str, int] = {} # Track versions per heuristic ID
        self._last_update_time: Dict[str, float] = {} # Added for rate limiting
        self.min_update_interval_seconds = min_update_interval_seconds
        # History: {heuristic_id: deque([(version, params_dict), ...], maxlen=max_history_size)}
        self._history: Dict[str, collections.deque] = {}
        self.max_history_size = max_history_size
        logger.info(f"HeuristicManager initialized with min update interval: {self.min_update_interval_seconds}s, max history: {self.max_history_size}.")

    def register_heuristic(self, heuristic_id: str, parameters: Dict[str, Any], version: int = 1) -> bool:
        """
        Registers a new heuristic configuration or updates an existing one.
        Currently replaces all parameters for the given ID if version is newer.

        Args:
            heuristic_id: A unique identifier for the heuristic set.
            parameters: A dictionary of parameter names and their values.
            version: An integer version for this heuristic configuration.

        Returns:
            True if the heuristic was registered or updated, False otherwise.
        """
        if not heuristic_id or not parameters:
            logger.error("Heuristic ID and parameters cannot be empty for registration.")
            return False
        
        current_version = self._heuristic_versions.get(heuristic_id, 0)
        if version > current_version:
            params_copy = parameters.copy()
            self._heuristics[heuristic_id] = params_copy
            self._heuristic_versions[heuristic_id] = version
            # Reset history and add current state
            self._history[heuristic_id] = collections.deque(maxlen=self.max_history_size)
            self._history[heuristic_id].append((version, params_copy))
            self._last_update_time[heuristic_id] = time.time()
            logger.info(f"Heuristic '{heuristic_id}' registered/updated to version {version} with params: {parameters}")
            return True
        else:
            logger.warning(f"Skipped updating heuristic '{heuristic_id}'. Supplied version {version} is not newer than current version {current_version}.")
            return False

    def get_parameter(self, heuristic_id: str, parameter_name: str, default: Any = None) -> Any:
        """
        Retrieves a specific parameter value for a given heuristic ID.

        Args:
            heuristic_id: The ID of the heuristic set.
            parameter_name: The name of the parameter to retrieve.
            default: The value to return if the heuristic or parameter is not found.

        Returns:
            The parameter value if found, else the default.
        """
        heuristic_params = self._heuristics.get(heuristic_id)
        if heuristic_params is None:
            logger.warning(f"Heuristic ID '{heuristic_id}' not found. Cannot get parameter '{parameter_name}'. Returning default.")
            return default
        
        value = heuristic_params.get(parameter_name, default)
        if value is default and parameter_name not in heuristic_params:
             logger.warning(f"Parameter '{parameter_name}' not found for heuristic '{heuristic_id}'. Returning default.")
             
        return value

    def get_heuristic_version(self, heuristic_id: str) -> Optional[int]:
        """
        Retrieves the current version of a heuristic configuration.
        """
        return self._heuristic_versions.get(heuristic_id)

    def get_parameters(self, heuristic_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the complete parameter dictionary for a given heuristic ID.
        Returns a copy to prevent external modification.

        Args:
            heuristic_id: The ID of the heuristic set.

        Returns:
            A copy of the parameter dictionary if the heuristic exists, else None.
        """
        params = self._heuristics.get(heuristic_id)
        if params is not None:
            return params.copy() # Return a copy
        else:
            logger.warning(f"Heuristic ID '{heuristic_id}' not found. Cannot get parameters.")
            return None

    def apply_modification(self, modification: HeuristicUpdate) -> bool:
        """
        Applies parameter adjustments from a HeuristicUpdate object.
        Does not currently support updating `new_definition_code` or `is_active`.
        Includes rate limiting and logs the attempt.

        Args:
            modification: A HeuristicUpdate object detailing the parameter changes.

        Returns:
            True if at least one parameter was successfully updated, False otherwise.
        """
        heuristic_id = modification.heuristic_id
        if heuristic_id not in self._heuristics:
            logger.error(f"Cannot apply modification: Heuristic ID '{heuristic_id}' not found in registry.")
            return False
            
        # --- Rate Limiting Check ---
        current_time = time.time()
        last_update = self._last_update_time.get(heuristic_id, 0)
        if current_time - last_update < self.min_update_interval_seconds:
            logger.warning(
                f"Rate limit hit for heuristic '{heuristic_id}'. Last update was {current_time - last_update:.1f}s ago. "
                f"Minimum interval is {self.min_update_interval_seconds}s. Modification rejected."
            )
            return False
        # --- End Rate Limiting Check ---

        applied_count = 0
        update_successful = False # Flag to track overall success
        final_error_msg = None
        current_version = self._heuristic_versions.get(heuristic_id, 0)
        current_params = self._heuristics.get(heuristic_id, {}).copy() # Get a copy to potentially modify
        original_params_for_history = current_params.copy() # Store original state for history
        new_version = current_version + 1 # Tentative new version if successful
        change_description_for_log = modification.change_description

        try:
            if not modification.parameter_adjustments:
                final_error_msg = f"No parameter adjustments provided for heuristic '{heuristic_id}' in modification. No changes applied."
                logger.warning(final_error_msg)
                # If other fields like is_active were supported, we'd check them here.
                # update_successful remains False
            else:
                skipped_due_validation = 0
                skipped_due_type = 0
                skipped_due_missing = 0
                
                for adjustment in modification.parameter_adjustments:
                    param_name = adjustment.parameter_name
                    new_value = adjustment.new_value
                    
                    # --- Parameter-specific Validation --- 
                    validation_passed = True
                    if heuristic_id == "fallback_rules" and param_name == "confidence_threshold":
                        if not isinstance(new_value, (float, int)) or not (0.0 <= float(new_value) <= 1.0):
                            msg = f"Invalid value for '{param_name}' in heuristic '{heuristic_id}': '{new_value}'. Must be float between 0.0 and 1.0."
                            logger.error(msg)
                            validation_passed = False
                            skipped_due_validation += 1
                    # Add more parameter-specific validations here as needed
                        
                    if not validation_passed:
                        continue # Skip this adjustment if validation failed
                    # --- End Validation --- 
                        
                    # Basic check: Does the parameter exist? 
                    if param_name in current_params:
                        # Attempt type conversion if necessary (e.g., for threshold)
                        try:
                            original_type = type(current_params[param_name])
                            # Handle bool conversion specifically if needed
                            if original_type == bool and isinstance(new_value, str):
                                if new_value.lower() == 'true':
                                    validated_value = True
                                elif new_value.lower() == 'false':
                                    validated_value = False
                                else:
                                   raise ValueError(f"Cannot convert string '{new_value}' to bool for {param_name}")
                            else:
                               validated_value = original_type(new_value) 
                            current_params[param_name] = validated_value
                            logger.info(f"Updated heuristic '{heuristic_id}' parameter '{param_name}' to '{validated_value}' (type: {type(validated_value).__name__}). Reason: {adjustment.reasoning}")
                            applied_count += 1
                        except (ValueError, TypeError) as e:
                            logger.error(f"Type conversion error for heuristic '{heuristic_id}' parameter '{param_name}' with value '{new_value}'. Expected type compatible with {original_type.__name__}. Error: {e}")
                            skipped_due_type += 1
                    else:
                        logger.warning(f"Parameter '{param_name}' not found for heuristic '{heuristic_id}'. Cannot apply adjustment.")
                        skipped_due_missing += 1

                if applied_count > 0:
                    # --- History Update --- 
                    if heuristic_id not in self._history:
                        self._history[heuristic_id] = collections.deque(maxlen=self.max_history_size)
                    # Store the state *before* this modification attempt
                    self._history[heuristic_id].append((current_version, original_params_for_history))
                    # --- End History Update ---
                    
                    # Apply the changes to the main storage
                    self._heuristics[heuristic_id] = current_params # current_params holds the modified values
                    self._heuristic_versions[heuristic_id] = new_version
                    self._last_update_time[heuristic_id] = current_time # Update timestamp on success
                    logger.info(f"Applied {applied_count} parameter adjustments to heuristic '{heuristic_id}'. New version: {self._heuristic_versions[heuristic_id]}. Change Description: {modification.change_description}")
                    update_successful = True
                else:
                    final_error_msg = f"No valid parameter adjustments applied for heuristic '{heuristic_id}'. Skipped: {skipped_due_validation} (validation), {skipped_due_type} (type), {skipped_due_missing} (missing)."
                    logger.warning(final_error_msg)
                    # update_successful remains False

        except Exception as e:
            final_error_msg = f"Unexpected error applying modification to heuristic '{heuristic_id}': {e}"
            logger.exception(final_error_msg)
            # update_successful remains False
        
        # Log the update attempt regardless of outcome
        log_update(
            manager_type="HeuristicManager",
            item_id=heuristic_id,
            old_version=current_version,
            new_version=new_version, # Log intended new version
            change_info=modification.model_dump() if isinstance(modification, HeuristicUpdate) else repr(modification), 
            success=update_successful,
            error_message=final_error_msg
        )
        
        return update_successful # Return the final success status

    def get_history(self, heuristic_id: str) -> List[Tuple[int, Dict[str, Any]]]:
        """
        Retrieves the version history for a specific heuristic configuration.

        Args:
            heuristic_id: The ID of the heuristic.

        Returns:
            A list of (version, parameters_dict) tuples, oldest first.
            Returns an empty list if the heuristic ID or its history is not found.
        """
        history_deque = self._history.get(heuristic_id)
        if history_deque:
            # Return copies to prevent external modification
            return [(version, params.copy()) for version, params in history_deque]
        else:
            logger.warning(f"No history found for heuristic ID '{heuristic_id}'.")
            return []

    def rollback(self, heuristic_id: str, target_version: int) -> bool:
        """
        Rolls back a heuristic configuration to a specific historical version.

        Args:
            heuristic_id: The ID of the heuristic to roll back.
            target_version: The version number to restore.

        Returns:
            True if rollback was successful, False otherwise.
        """
        if heuristic_id not in self._heuristics:
            logger.error(f"Rollback failed: Heuristic ID '{heuristic_id}' not found.")
            return False

        history = self.get_history(heuristic_id)
        target_params = None
        for version, params in reversed(history): # Search from newest historical entry
            if version == target_version:
                target_params = params # Already a copy from get_history
                break
        
        # Check if target_version is the *current* version
        current_version = self._heuristic_versions.get(heuristic_id)
        if target_version == current_version:
             target_params = self._heuristics.get(heuristic_id) # Get current params

        if target_params is None:
            logger.error(f"Rollback failed: Version {target_version} not found in history for heuristic ID '{heuristic_id}'. Available history versions: {[v for v, p in history]}")
            return False

        # Apply the rollback
        current_time = time.time()
        old_version_before_rollback = self._heuristic_versions.get(heuristic_id)
        current_params_before_rollback = self._heuristics.get(heuristic_id)

        # Store current state in history before overwriting
        if old_version_before_rollback != target_version and current_params_before_rollback is not None:
             if heuristic_id not in self._history:
                 self._history[heuristic_id] = collections.deque(maxlen=self.max_history_size)
             self._history[heuristic_id].append((old_version_before_rollback, current_params_before_rollback.copy()))

        self._heuristics[heuristic_id] = target_params.copy() # Apply as a copy
        self._heuristic_versions[heuristic_id] = target_version
        self._last_update_time[heuristic_id] = current_time
        
        change_info = { "rollback_details": f"Rolled back from v{old_version_before_rollback} to v{target_version}"}
        logger.info(f"Heuristic '{heuristic_id}' successfully rolled back to version {target_version}.")

        # Log the rollback action
        log_update(
            manager_type="HeuristicManager",
            item_id=heuristic_id,
            old_version=old_version_before_rollback,
            new_version=target_version,
            change_info=change_info,
            success=True,
            error_message=None
        )
        return True

    def list_heuristics(self) -> Dict[str, Dict[str, Any]]:
        """
        Lists all registered heuristics, their versions, and parameters.
        """
        return { 
            hid: {
                'version': self._heuristic_versions.get(hid), 
                'parameters': self._heuristics.get(hid, {}).copy()
            } 
            for hid in self._heuristics.keys()
        }

# Global instance
_heuristic_manager_instance: Optional[HeuristicManager] = None

def get_global_heuristic_manager() -> HeuristicManager:
    """
    Provides a global singleton instance of the HeuristicManager.
    """
    global _heuristic_manager_instance
    if _heuristic_manager_instance is None:
        _heuristic_manager_instance = HeuristicManager()
        logger.info("Global HeuristicManager instance created.")
        # Example: Register default fallback threshold
        # _heuristic_manager_instance.register_heuristic(
        #     "planner_fallback_rules",
        #     {"confidence_threshold": 0.7}, 
        #     version=1
        # )
    return _heuristic_manager_instance

# Example Usage
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    manager = get_global_heuristic_manager() # Use global instance

    # Register initial heuristic parameters
    manager.register_heuristic("planner_scoring", {"accuracy_weight": 1.0, "latency_weight": -1.0}, version=1)
    manager.register_heuristic("fallback_rules", {"confidence_threshold": 0.7, "max_retries": 3}, version=1)

    print("\nRegistered Heuristics:")
    for hid, data in manager.list_heuristics().items():
        print(f"  ID: {hid}, Version: {data['version']}, Params: {data['parameters']}")

    # Get a parameter
    conf_thresh = manager.get_parameter("fallback_rules", "confidence_threshold", default=0.5)
    print(f"\nRetrieved fallback_rules confidence_threshold: {conf_thresh}")

    # Simulate a reflection output suggesting an update
    update_proposal_1 = HeuristicUpdate(
        heuristic_id="fallback_rules",
        parameter_adjustments=[
            HeuristicParameterAdjustment(parameter_name="confidence_threshold", new_value=0.75, reasoning="LLM planner seems reliable, increase threshold.")
        ],
        change_description="Adjust fallback threshold."
    )

    success_1 = manager.apply_modification(update_proposal_1)
    print(f"\nApplying first modification to fallback_rules: Success? {success_1}")
    time.sleep(0.1) # Short delay

    # Attempt a second update immediately (should be rate limited)
    update_proposal_2 = HeuristicUpdate(
        heuristic_id="fallback_rules",
        parameter_adjustments=[
            HeuristicParameterAdjustment(parameter_name="max_retries", new_value=2, reasoning="Reduce retries on failure.")
        ],
        change_description="Adjust max retries (rate limit test)."
    )
    success_2 = manager.apply_modification(update_proposal_2)
    print(f"\nApplying second modification immediately: Success? {success_2} (Expected False if rate limited)")

    conf_thresh_final = manager.get_parameter("fallback_rules", "confidence_threshold")
    retries_final = manager.get_parameter("fallback_rules", "max_retries")
    print(f"Retrieved fallback_rules params after attempts (v{manager.get_heuristic_version('fallback_rules')}): threshold={conf_thresh_final}, retries={retries_final}")

    # Test update with non-existent parameter
    bad_update = HeuristicUpdate(
        heuristic_id="fallback_rules",
        parameter_adjustments=[
            HeuristicParameterAdjustment(parameter_name="non_existent_param", new_value=100)
        ],
        change_description="Trying to update non-existent param."
    )
    success_bad = manager.apply_modification(bad_update)
    print(f"\nApplying bad modification: Success? {success_bad} (Expected False)")

    # Test validation failure (confidence > 1.0)
    invalid_conf_update = HeuristicUpdate(
        heuristic_id="fallback_rules",
        parameter_adjustments=[
            HeuristicParameterAdjustment(parameter_name="confidence_threshold", new_value=1.1)
        ],
        change_description="Testing invalid confidence threshold."
    )
    success_invalid_conf = manager.apply_modification(invalid_conf_update)
    print(f"\nApplying invalid confidence modification: Success? {success_invalid_conf} (Expected False)")
    print(f"Confidence threshold after invalid attempt: {manager.get_parameter('fallback_rules', 'confidence_threshold')}")

    # --- Test History and Rollback ---
    print("\n--- History and Rollback Test (Heuristics) ---")
    # Apply another valid update after waiting
    time.sleep(manager.min_update_interval_seconds + 0.1) 
    update_proposal_3 = HeuristicUpdate(
        heuristic_id="fallback_rules",
        parameter_adjustments=[
            HeuristicParameterAdjustment(parameter_name="confidence_threshold", new_value=0.6)
        ],
        change_description="Third update to fallback threshold."
    )
    success_3 = manager.apply_modification(update_proposal_3)
    print(f"Applying third modification: Success? {success_3}")
    print(f"Current version: {manager.get_heuristic_version('fallback_rules')}")
    print(f"Current params: {manager._heuristics.get('fallback_rules')}")

    history = manager.get_history("fallback_rules")
    print(f"\nHistory for fallback_rules: {[(v, p) for v, p in history]}")
    
    # Rollback to version 1 (the original registered version)
    rollback_success = manager.rollback("fallback_rules", 1)
    print(f"\nAttempting rollback to v1: Success? {rollback_success}")
    print(f"Version after rollback: {manager.get_heuristic_version('fallback_rules')}")
    print(f"Params after rollback: {manager._heuristics.get('fallback_rules')}")
    
    # Check history again after rollback
    history_after_rollback = manager.get_history("fallback_rules")
    print(f"History after rollback: {[(v, p) for v, p in history_after_rollback]}")
    # --- End History and Rollback Test ---

    print("\nEnd of HeuristicManager example usage.") 