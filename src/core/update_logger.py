import json
import logging
import os
from datetime import datetime
from typing import Any, Dict

# Configure logger for this module
logger = logging.getLogger(__name__)

# Define the log file path (consider making this configurable)
LOGS_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'logs') # Assumes src/core structure
UPDATES_LOG_FILE = os.path.join(LOGS_DIR, 'updates.jsonl')

# Ensure logs directory exists
os.makedirs(LOGS_DIR, exist_ok=True)

def log_update(
    manager_type: str, 
    item_id: str, 
    old_version: int, 
    new_version: int, 
    change_info: Any,
    success: bool = True,
    error_message: str = None
) -> None:
    """
    Logs an update attempt (successful or failed) to a structured JSONL file.

    Args:
        manager_type: Type of manager ('PromptManager' or 'HeuristicManager').
        item_id: The ID of the prompt or heuristic being updated.
        old_version: The version before the update attempt.
        new_version: The version after a successful update (or intended version on failure).
        change_info: Details about the change (e.g., modification object, description).
        success: Boolean indicating if the update operation was successful.
        error_message: Optional error message if the update failed.
    """
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "manager_type": manager_type,
        "item_id": item_id,
        "old_version": old_version,
        "new_version": new_version,
        "change_info": change_info,
        "success": success,
        "error_message": error_message
    }

    try:
        with open(UPDATES_LOG_FILE, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    except IOError as e:
        logger.error(f"Failed to write to update log file '{UPDATES_LOG_FILE}': {e}")
    except Exception as e:
        logger.error(f"Unexpected error writing to update log: {e}", exc_info=True)

# Example Usage (for testing)
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    logger.info(f"Testing update logger. Log file: {UPDATES_LOG_FILE}")

    # Simulate successful prompt update
    log_update(
        manager_type="PromptManager",
        item_id="kfm_planner_main",
        old_version=1,
        new_version=2,
        change_info={"change_description": "Updated template"},
        success=True
    )

    # Simulate failed heuristic update
    log_update(
        manager_type="HeuristicManager",
        item_id="fallback_rules",
        old_version=3,
        new_version=4, # Intended version
        change_info={"parameter_adjustments": [{"parameter_name": "confidence_threshold", "new_value": 1.5}]}, # Example change info
        success=False,
        error_message="Validation failed: confidence_threshold must be between 0.0 and 1.0"
    )
    
    logger.info("Test log entries written (check the log file).") 