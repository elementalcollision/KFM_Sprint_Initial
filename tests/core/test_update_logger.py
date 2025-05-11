import pytest
import json
import os
from datetime import datetime

# Add project root to path if tests are run from a different directory
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.update_logger import log_update, UPDATES_LOG_FILE

@pytest.fixture(autouse=True)
def cleanup_log_file():
    """Ensures the log file is clean before and after each test."""
    if os.path.exists(UPDATES_LOG_FILE):
        os.remove(UPDATES_LOG_FILE)
    yield # Run the test
    if os.path.exists(UPDATES_LOG_FILE):
        os.remove(UPDATES_LOG_FILE)

def read_log_lines():
    """Helper to read all lines from the log file."""
    if not os.path.exists(UPDATES_LOG_FILE):
        return []
    with open(UPDATES_LOG_FILE, 'r') as f:
        return [json.loads(line) for line in f]

def test_log_successful_prompt_update():
    """Test logging a successful prompt update."""
    manager_type = "PromptManager"
    item_id = "prompt_abc"
    old_version = 1
    new_version = 2
    change_info = {"new_full_template": "New template content", "change_description": "Updated via test"}
    
    log_update(manager_type, item_id, old_version, new_version, change_info, success=True)
    
    logs = read_log_lines()
    assert len(logs) == 1
    log_entry = logs[0]
    
    assert log_entry["timestamp"]
    assert log_entry["manager_type"] == manager_type
    assert log_entry["item_id"] == item_id
    assert log_entry["old_version"] == old_version
    assert log_entry["new_version"] == new_version
    assert log_entry["change_info"] == change_info
    assert log_entry["success"] is True
    assert log_entry["error_message"] is None

def test_log_failed_heuristic_update():
    """Test logging a failed heuristic update with an error message."""
    manager_type = "HeuristicManager"
    item_id = "heuristic_xyz"
    old_version = 3
    new_version = 3 # Version doesn't change on failure usually
    change_info = {"parameter_adjustments": [{"parameter_name": "threshold", "new_value": 0.9}]}
    error_message = "Validation failed: Threshold too high"
    
    log_update(manager_type, item_id, old_version, new_version, change_info, success=False, error_message=error_message)
    
    logs = read_log_lines()
    assert len(logs) == 1
    log_entry = logs[0]
    
    assert log_entry["timestamp"]
    assert log_entry["manager_type"] == manager_type
    assert log_entry["item_id"] == item_id
    assert log_entry["old_version"] == old_version
    assert log_entry["new_version"] == new_version
    assert log_entry["change_info"] == change_info
    assert log_entry["success"] is False
    assert log_entry["error_message"] == error_message

def test_log_multiple_entries():
    """Test that multiple log entries are appended correctly."""
    log_update("PromptManager", "prompt1", 0, 1, {"desc": "init"}, True)
    log_update("HeuristicManager", "heur1", 1, 1, {"desc": "failed attempt"}, False, "Rate limited")
    log_update("PromptManager", "prompt1", 1, 2, {"desc": "second update"}, True)
    
    logs = read_log_lines()
    assert len(logs) == 3
    assert logs[0]["item_id"] == "prompt1"
    assert logs[0]["new_version"] == 1
    assert logs[1]["item_id"] == "heur1"
    assert logs[1]["success"] is False
    assert logs[2]["item_id"] == "prompt1"
    assert logs[2]["new_version"] == 2

def test_log_timestamp_format():
    """Test the timestamp format briefly."""
    log_update("PromptManager", "ts_test", 1, 2, {}, True)
    logs = read_log_lines()
    assert len(logs) == 1
    timestamp_str = logs[0]["timestamp"]
    # Example: 2023-10-27T10:30:00.123456
    try:
        datetime.fromisoformat(timestamp_str)
    except ValueError:
        pytest.fail(f"Timestamp {timestamp_str} is not in expected ISO format.")

# Test that the log file is created in the correct directory
# Assuming UPDATES_LOG_FILE points to logs/updates.jsonl relative to src/core
# The path manipulation for sys.path might affect this if not careful, but UPDATES_LOG_FILE itself is robust.
def test_log_file_creation_path():
    """Test that the log file is created in the specified logs directory."""
    log_dir = os.path.dirname(UPDATES_LOG_FILE)
    assert os.path.basename(log_dir) == "logs" 
    # Check if the parent of 'logs' is the project root (KFM_Sprint1 in this case)
    # This is a bit fragile as it assumes a specific structure based on __file__
    project_root_marker = 'src' # A directory that should be in the project root alongside 'logs'
    assert project_root_marker in os.listdir(os.path.dirname(log_dir))
    
    log_update("TestManager", "test_id", 0, 1, {}, True)
    assert os.path.exists(UPDATES_LOG_FILE)
    assert os.path.isfile(UPDATES_LOG_FILE) 