from typing import Dict, Optional, Literal, List, Tuple, Any
import logging
import time # Added
import collections # Added

from .reflection_schemas import PromptModification # Assuming reflection_schemas.py is in src/core
from .update_logger import log_update # Added

logger = logging.getLogger(__name__)

class PromptManager:
    """
    Manages storage, retrieval, and dynamic updates of prompt templates.
    """
    DEFAULT_MIN_UPDATE_INTERVAL = 60.0 # Default interval in seconds
    DEFAULT_MAX_HISTORY = 10 # Default number of history versions to keep

    def __init__(self, 
                 min_update_interval_seconds: float = DEFAULT_MIN_UPDATE_INTERVAL,
                 max_history_size: int = DEFAULT_MAX_HISTORY):
        self._prompts: Dict[str, str] = {}
        self._prompt_versions: Dict[str, int] = {} # Current version
        self._last_update_time: Dict[str, float] = {} 
        self.min_update_interval_seconds = min_update_interval_seconds
        # History: {prompt_id: deque([(version, template), ...], maxlen=max_history_size)}
        self._history: Dict[str, collections.deque] = {}
        self.max_history_size = max_history_size
        logger.info(f"PromptManager initialized with min update interval: {self.min_update_interval_seconds}s, max history: {self.max_history_size}.")

    def register_prompt(self, prompt_id: str, template: str, version: int = 1) -> bool:
        """
        Registers a new prompt template or updates an existing one if the new version is higher.

        Args:
            prompt_id: A unique identifier for the prompt.
            template: The string content of the prompt template.
            version: An integer version for the prompt.

        Returns:
            True if the prompt was registered or updated, False otherwise (e.g., lower version).
        """
        if not prompt_id or not template:
            logger.error("Prompt ID and template content cannot be empty for registration.")
            return False
        
        current_version = self._prompt_versions.get(prompt_id, 0)
        if version > current_version:
            self._prompts[prompt_id] = template
            self._prompt_versions[prompt_id] = version
            # Reset history when registering/updating explicitly
            self._history[prompt_id] = collections.deque(maxlen=self.max_history_size)
            # Add the newly registered version as the first entry in its history
            self._history[prompt_id].append((version, template))
            self._last_update_time[prompt_id] = time.time() # Set initial update time
            logger.info(f"Prompt '{prompt_id}' registered/updated to version {version}. History reset.")
            return True
        else:
            logger.warning(f"Skipped updating prompt '{prompt_id}'. Supplied version {version} is not newer than current version {current_version}.")
            return False

    def get_prompt(self, prompt_id: str) -> Optional[str]:
        """
        Retrieves a prompt template by its ID.

        Args:
            prompt_id: The ID of the prompt to retrieve.

        Returns:
            The prompt template string if found, else None.
        """
        prompt = self._prompts.get(prompt_id)
        if prompt is None:
            logger.warning(f"Prompt with ID '{prompt_id}' not found.")
        return prompt

    def get_prompt_version(self, prompt_id: str) -> Optional[int]:
        """
        Retrieves the current version of a prompt.

        Args:
            prompt_id: The ID of the prompt.

        Returns:
            The version number if the prompt exists, else None.
        """
        return self._prompt_versions.get(prompt_id)

    def apply_modification(self, modification: PromptModification) -> bool:
        """
        Applies a PromptModification to a registered prompt.
        Currently supports full template replacement. Segment modification is a TODO.
        Includes rate limiting to prevent rapid updates.

        Args:
            modification: A PromptModification object detailing the changes.

        Returns:
            True if the modification was successfully applied, False otherwise.
        """
        prompt_id = modification.prompt_id
        if prompt_id not in self._prompts:
            logger.error(f"Cannot apply modification: Prompt ID '{prompt_id}' not found in registry.")
            return False

        # --- Rate Limiting Check ---
        current_time = time.time()
        last_update = self._last_update_time.get(prompt_id, 0)
        if current_time - last_update < self.min_update_interval_seconds:
            logger.warning(
                f"Rate limit hit for prompt '{prompt_id}'. Last update was {current_time - last_update:.1f}s ago. "
                f"Minimum interval is {self.min_update_interval_seconds}s. Modification rejected."
            )
            return False
        # --- End Rate Limiting Check ---

        current_version = self._prompt_versions.get(prompt_id, 0)
        current_template = self._prompts.get(prompt_id)
        new_version = current_version + 1
        success = False
        error_msg = None
        final_error_msg = None
        update_successful = False

        try:
            if modification.new_full_template is not None:
                # --- History Update --- 
                if current_template is not None:
                    if prompt_id not in self._history:
                        self._history[prompt_id] = collections.deque(maxlen=self.max_history_size)
                    self._history[prompt_id].append((current_version, current_template))
                # --- End History Update ---
                
                self._prompts[prompt_id] = modification.new_full_template
                self._prompt_versions[prompt_id] = new_version
                self._last_update_time[prompt_id] = current_time # Update timestamp on success
                logger.info(f"Prompt '{prompt_id}' updated via full template replacement to version {new_version}. Change: {modification.change_description}")
                success = True
                # TODO: Implement segment_modifications if needed
                # elif modification.segment_modifications:
                #     logger.warning(f"Segment modifications for prompt '{prompt_id}' are not yet implemented.")
                #     return False # Keep success as False
            elif modification.segment_modifications:
                error_msg = f"Segment modifications for prompt '{prompt_id}' are not yet implemented. No changes applied."
                logger.warning(error_msg)
                # Keep success as False
            else:
                # This case should be caught by PromptModification Pydantic model validator
                error_msg = f"Invalid PromptModification for '{prompt_id}': No update action specified."
                logger.error(error_msg)
                # Keep success as False
        except Exception as e:
            final_error_msg = f"Unexpected error applying modification to prompt '{prompt_id}': {e}"
            logger.exception(final_error_msg)
            update_successful = False

        # Log the update attempt regardless of outcome
        # Note: We log intended new_version even if update failed, to record the attempt.
        log_update(
            manager_type="PromptManager",
            item_id=prompt_id,
            old_version=current_version,
            new_version=new_version,
            change_info=modification.model_dump() if isinstance(modification, PromptModification) else repr(modification),
            success=update_successful,
            error_message=final_error_msg
        )
        
        # Return True if we got past the initial checks (rate limit, not found)
        # and no *unexpected* exception occurred during processing.
        # Even if only warnings were logged (e.g., unimplemented segments), 
        # the modification attempt was still processed.
        return final_error_msg is None or "not yet implemented" in final_error_msg

    def get_history(self, prompt_id: str) -> List[Tuple[int, str]]:
        """
        Retrieves the version history for a specific prompt.

        Args:
            prompt_id: The ID of the prompt.

        Returns:
            A list of (version, template_string) tuples, oldest first.
            Returns an empty list if the prompt ID or its history is not found.
        """
        history_deque = self._history.get(prompt_id)
        if history_deque:
            # Return copies to prevent external modification
            return [(version, template) for version, template in history_deque]
        else:
            logger.warning(f"No history found for prompt ID '{prompt_id}'.")
            return []

    def rollback(self, prompt_id: str, target_version: int) -> bool:
        """
        Rolls back a prompt to a specific historical version.

        Args:
            prompt_id: The ID of the prompt to roll back.
            target_version: The version number to restore.

        Returns:
            True if rollback was successful, False otherwise.
        """
        if prompt_id not in self._prompts:
            logger.error(f"Rollback failed: Prompt ID '{prompt_id}' not found.")
            return False

        history = self.get_history(prompt_id)
        target_template = None
        for version, template in reversed(history): # Search from newest historical entry
            if version == target_version:
                target_template = template
                break
        
        # Also check if target_version is the *current* version (no rollback needed, but maybe desired)
        current_version = self._prompt_versions.get(prompt_id)
        if target_version == current_version:
             target_template = self._prompts.get(prompt_id)

        if target_template is None:
            logger.error(f"Rollback failed: Version {target_version} not found in history for prompt ID '{prompt_id}'. Available history versions: {[v for v, t in history]}")
            return False

        # Apply the rollback
        current_time = time.time()
        old_version_before_rollback = self._prompt_versions.get(prompt_id)
        current_template_before_rollback = self._prompts.get(prompt_id)

        # Store current state in history before overwriting with rollback state
        if old_version_before_rollback != target_version and current_template_before_rollback is not None: # Don't store if rolling back to current
             if prompt_id not in self._history:
                 self._history[prompt_id] = collections.deque(maxlen=self.max_history_size)
             self._history[prompt_id].append((old_version_before_rollback, current_template_before_rollback))

        self._prompts[prompt_id] = target_template
        self._prompt_versions[prompt_id] = target_version # Set version to the target historical version
        self._last_update_time[prompt_id] = current_time
        
        change_info = { "rollback_details": f"Rolled back from v{old_version_before_rollback} to v{target_version}"}
        logger.info(f"Prompt '{prompt_id}' successfully rolled back to version {target_version}.")

        # Log the rollback action
        log_update(
            manager_type="PromptManager",
            item_id=prompt_id,
            old_version=old_version_before_rollback, # Version before rollback
            new_version=target_version,            # Version after rollback
            change_info=change_info,
            success=True,
            error_message=None
        )
        return True

    def list_prompts(self) -> Dict[str, Dict[str, any]]:
        """
        Lists all registered prompts and their versions.
        """
        return {pid: {'version': self._prompt_versions.get(pid), 'template_preview': self._prompts.get(pid, '')[:100] + '...'} for pid in self._prompts.keys()}

# Global instance
_prompt_manager_instance: Optional[PromptManager] = None

def get_global_prompt_manager() -> PromptManager:
    """
    Provides a global singleton instance of the PromptManager.
    """
    global _prompt_manager_instance
    if _prompt_manager_instance is None:
        _prompt_manager_instance = PromptManager()
        # Optionally, register some core system prompts here if they are static and known at startup
        # Example:
        # _prompt_manager_instance.register_prompt(
        #     "system_error_fallback", 
        #     "An unexpected error occurred. Please try again later.", 
        #     version=1
        # )
        logger.info("Global PromptManager instance created.")
    return _prompt_manager_instance

# Example Usage (for testing or demonstration)
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    manager = PromptManager()

    # Register initial prompts
    manager.register_prompt("kfm_planner_main", "This is the main KFM planner prompt v1. Task: {task_name}", version=1)
    manager.register_prompt("reflection_eval", "Reflection prompt for LLM v1. Context: {context}", version=1)

    print("\nRegistered Prompts:")
    for pid, data in manager.list_prompts().items():
        print(f"  ID: {pid}, Version: {data['version']}, Preview: {data['template_preview']}")

    # Get a prompt
    main_planner_prompt_v1 = manager.get_prompt("kfm_planner_main")
    print(f"\nRetrieved kfm_planner_main (v{manager.get_prompt_version('kfm_planner_main')}): {main_planner_prompt_v1}")

    # Simulate a reflection output suggesting an update
    update_proposal_1 = PromptModification(
        prompt_id="kfm_planner_main",
        new_full_template="This is the main KFM planner prompt v2 (updated!). Task: {task_name}, Params: {params}",
        change_description="Updated to include params and clarify version."
    )

    success_1 = manager.apply_modification(update_proposal_1)
    print(f"\nApplying first modification to kfm_planner_main: Success? {success_1}")
    time.sleep(0.1) # Short delay

    # Attempt a second update immediately (should be rate limited if interval > 0.1)
    update_proposal_2 = PromptModification(
        prompt_id="kfm_planner_main",
        new_full_template="This is the main KFM planner prompt v3 (rate limit test). Task: {task_name}",
        change_description="Attempting rapid update."
    )
    success_2 = manager.apply_modification(update_proposal_2)
    print(f"\nApplying second modification immediately: Success? {success_2} (Expected False if rate limited)")

    main_planner_prompt_v_final = manager.get_prompt("kfm_planner_main")
    print(f"Retrieved kfm_planner_main after attempts (v{manager.get_prompt_version('kfm_planner_main')}): {main_planner_prompt_v_final}")

    # --- Test History and Rollback ---
    print("\n--- History and Rollback Test ---")
    # Apply another valid update after waiting
    time.sleep(manager.min_update_interval_seconds + 0.1) # Ensure rate limit passed if interval > 0
    update_proposal_3 = PromptModification(
        prompt_id="kfm_planner_main",
        new_full_template="This is the main KFM planner prompt v3. Task: {task_name}",
        change_description="Third update."
    )
    success_3 = manager.apply_modification(update_proposal_3)
    print(f"Applying third modification: Success? {success_3}")
    print(f"Current version: {manager.get_prompt_version('kfm_planner_main')}")
    print(f"Current template: {manager.get_prompt('kfm_planner_main')}")

    history_kfm = manager.get_history("kfm_planner_main")
    print(f"\nHistory for kfm_planner_main (should contain v1, v2): {[(v, t[:30] + '...') for v, t in history_kfm]}")
    
    # Rollback to version 1 (the original registered version)
    rollback_success = manager.rollback("kfm_planner_main", 1)
    print(f"\nAttempting rollback to v1: Success? {rollback_success}")
    print(f"Version after rollback: {manager.get_prompt_version('kfm_planner_main')}")
    print(f"Template after rollback: {manager.get_prompt('kfm_planner_main')}")
    
    # Check history again after rollback (should now contain v3 as well)
    history_kfm_after_rollback = manager.get_history("kfm_planner_main")
    print(f"History after rollback (should contain v1, v2, v3): {[(v, t[:30] + '...') for v, t in history_kfm_after_rollback]}")

    # Attempt to rollback to non-existent version
    rollback_fail = manager.rollback("kfm_planner_main", 99)
    print(f"\nAttempting rollback to v99: Success? {rollback_fail} (Expected False)")
    # --- End History and Rollback Test ---

    # Attempt to register with an older version
    manager.register_prompt("kfm_planner_main", "This is an old v0.5 prompt.", version=0)
    
    print("\nFinal Registered Prompts:")
    for pid, data in manager.list_prompts().items():
        print(f"  ID: {pid}, Version: {data['version']}, Preview: {data['template_preview']}")

    # Test applying modification to non-existent prompt
    non_existent_update = PromptModification(
        prompt_id="does_not_exist",
        new_full_template="some template",
        change_description="testing non-existent"
    )
    success_ne = manager.apply_modification(non_existent_update)
    print(f"\nApplying modification to does_not_exist: Success? {success_ne}")

    # Test segment modification (currently not implemented, will log a warning)
    # For this test to pass Pydantic validation for PromptModification,
    # segment_modifications should be a list of PromptModificationSegment instances.
    # Here, we construct it minimally to test the apply_modification path.
    # In a real scenario, these would be proper PromptModificationSegment objects.
    print(f"\nAttempting segment modification for reflection_eval (expecting 'not implemented' warning)...")
    try:
        # This construction is simplified and might not pass strict Pydantic validation 
        # if PromptModificationSegment has required fields not met by simple dicts.
        # However, our goal is to test the branch in apply_modification.
        # A robust test would use correctly instantiated PromptModificationSegment objects.
        
        # Create a PromptModification object that would trigger the segment modification path
        # by providing segment_modifications and no new_full_template.
        # The actual content of segment_modifications items isn't critical for this path test,
        # as long as the list itself is not None and not empty.
        segment_update_attempt = PromptModification(
            prompt_id="reflection_eval",
            # segment_modifications=[PromptModificationSegment(segment_id="s1", new_content="c1")], # Proper way
            segment_modifications=[{"segment_id": "test_seg", "new_content": "new val", "modification_action": "replace"}], # Simplified for this demo
            change_description="Attempt to update segment."
        )
        # Ensure new_full_template is None if Pydantic doesn't auto-set it in this constructor case
        segment_update_attempt.new_full_template = None

        success_seg = manager.apply_modification(segment_update_attempt)
        print(f"Applying segment modification to reflection_eval: Success? {success_seg} (Expected False, with warning)")
    except Exception as e:
        print(f"Error during segment modification test: {e}. This might be due to Pydantic validation of simplified segment_modifications.")

    print("\nEnd of PromptManager example usage.")

# pass # End of example usage - Removed as it's now within the if __name__ block 