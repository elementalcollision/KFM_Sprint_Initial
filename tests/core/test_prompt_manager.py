import pytest
import time
import collections

# Add project root to path if tests are run from a different directory
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.prompt_manager import PromptManager
from src.core.reflection_schemas import PromptModification, PromptModificationSegment # Import schema


@pytest.fixture
def manager() -> PromptManager:
    """Provides a fresh PromptManager instance for each test."""
    # Use a short rate limit interval for testing
    return PromptManager(min_update_interval_seconds=0.1, max_history_size=3)

@pytest.fixture
def manager_long_interval() -> PromptManager:
    """Provides a PromptManager instance with a longer interval."""
    return PromptManager(min_update_interval_seconds=60, max_history_size=3)

def test_register_new_prompt(manager):
    """Test registering a completely new prompt."""
    prompt_id = "prompt1"
    template = "Template v1 for {var}"
    assert manager.register_prompt(prompt_id, template, version=1)
    assert manager.get_prompt(prompt_id) == template
    assert manager.get_prompt_version(prompt_id) == 1
    history = manager.get_history(prompt_id)
    assert len(history) == 1
    assert history[0] == (1, template)

def test_register_prompt_update_version(manager):
    """Test updating an existing prompt with a newer version."""
    prompt_id = "prompt1"
    template1 = "Template v1"
    template2 = "Template v2"
    manager.register_prompt(prompt_id, template1, version=1)
    assert manager.register_prompt(prompt_id, template2, version=2)
    assert manager.get_prompt(prompt_id) == template2
    assert manager.get_prompt_version(prompt_id) == 2
    # History should be reset on register/update
    history = manager.get_history(prompt_id)
    assert len(history) == 1
    assert history[0] == (2, template2)

def test_register_prompt_same_version(manager):
    """Test attempting to register with the same version (should fail)."""
    prompt_id = "prompt1"
    template1 = "Template v1"
    manager.register_prompt(prompt_id, template1, version=1)
    assert not manager.register_prompt(prompt_id, "Template v1 again", version=1)
    assert manager.get_prompt(prompt_id) == template1 # Should remain unchanged
    assert manager.get_prompt_version(prompt_id) == 1

def test_register_prompt_older_version(manager):
    """Test attempting to register with an older version (should fail)."""
    prompt_id = "prompt1"
    template2 = "Template v2"
    manager.register_prompt(prompt_id, template2, version=2)
    assert not manager.register_prompt(prompt_id, "Template v1 old", version=1)
    assert manager.get_prompt(prompt_id) == template2 # Should remain unchanged
    assert manager.get_prompt_version(prompt_id) == 2

def test_get_prompt_not_found(manager):
    """Test getting a prompt that hasn't been registered."""
    assert manager.get_prompt("non_existent_prompt") is None
    assert manager.get_prompt_version("non_existent_prompt") is None

def test_apply_modification_success(manager):
    """Test applying a valid modification (full template)."""
    prompt_id = "prompt_to_modify"
    template_v1 = "Version 1 template"
    template_v2 = "Version 2 template"
    manager.register_prompt(prompt_id, template_v1, version=1)
    time.sleep(manager.min_update_interval_seconds + 0.01) # Sleep after registration

    mod = PromptModification(
        prompt_id=prompt_id,
        new_full_template=template_v2,
        change_description="Test update"
    )
    assert manager.apply_modification(mod)
    assert manager.get_prompt(prompt_id) == template_v2
    assert manager.get_prompt_version(prompt_id) == 2 # Version should increment
    # Add a small sleep after registration before the first modification attempt
    time.sleep(0.01) 
    history = manager.get_history(prompt_id)
    assert len(history) == 2 # Original v1 + pre-update v1 state
    assert history[0] == (1, template_v1) # Original registration state
    assert history[1] == (1, template_v1) # State before modification was applied

def test_apply_modification_rate_limit(manager):
    """Test that modifications are rate limited."""
    prompt_id = "prompt_rate_limit"
    template_v1 = "RL v1"
    template_v2 = "RL v2"
    template_v3 = "RL v3"
    manager.register_prompt(prompt_id, template_v1, version=1)
    time.sleep(manager.min_update_interval_seconds + 0.01) # Sleep after registration

    mod1 = PromptModification(prompt_id=prompt_id, new_full_template=template_v2, change_description="Update 1")
    mod2 = PromptModification(prompt_id=prompt_id, new_full_template=template_v3, change_description="Update 2")

    assert manager.apply_modification(mod1) # First update should succeed
    assert manager.get_prompt_version(prompt_id) == 2
    # No sleep here - expect rate limit
    assert not manager.apply_modification(mod2) # Second should fail due to rate limit
    assert manager.get_prompt(prompt_id) == template_v2 # Template should not have changed
    assert manager.get_prompt_version(prompt_id) == 2 # Version should not have changed

def test_apply_modification_after_rate_limit_interval(manager):
    """Test applying modification successfully after the rate limit interval."""
    prompt_id = "prompt_rate_limit_wait"
    template_v1 = "RLW v1"
    template_v2 = "RLW v2"
    template_v3 = "RLW v3"
    manager.register_prompt(prompt_id, template_v1, version=1)
    time.sleep(manager.min_update_interval_seconds + 0.01) # Sleep after registration

    mod1 = PromptModification(prompt_id=prompt_id, new_full_template=template_v2, change_description="Update 1")
    mod2 = PromptModification(prompt_id=prompt_id, new_full_template=template_v3, change_description="Update 2")

    assert manager.apply_modification(mod1)
    assert manager.get_prompt_version(prompt_id) == 2
    time.sleep(manager.min_update_interval_seconds + 0.05) # Increase sleep slightly for safety
    assert manager.apply_modification(mod2) # Second should now succeed
    assert manager.get_prompt(prompt_id) == template_v3
    assert manager.get_prompt_version(prompt_id) == 3

def test_apply_modification_prompt_not_found(manager):
    """Test applying modification to a non-existent prompt ID."""
    mod = PromptModification(
        prompt_id="does_not_exist", 
        new_full_template="some template", 
        change_description="Test non-existent"
    )
    assert not manager.apply_modification(mod)

def test_apply_modification_segment_not_implemented(manager, caplog):
    """Test applying modification with segment changes (should log warning)."""
    prompt_id = "prompt_seg_test"
    template_v1 = "Segment test v1"
    manager.register_prompt(prompt_id, template_v1, version=1)
    time.sleep(manager.min_update_interval_seconds + 0.01) # Sleep after registration
    
    # Construct valid modification for segments
    segments = [PromptModificationSegment(segment_id="s1", new_content="c1")]
    mod = PromptModification(
        prompt_id=prompt_id,
        segment_modifications=segments,
        change_description="Test segments"
    )
    
    assert manager.apply_modification(mod)
    assert manager.get_prompt(prompt_id) == template_v1 # Should remain unchanged
    assert manager.get_prompt_version(prompt_id) == 1
    # Check the specific warning about segments being unimplemented
    # This might still fail if rate limit hits first, but let's make the check specific
    segment_warning_found = any(
        f"Segment modifications for prompt '{prompt_id}' are not yet implemented" in record.message
        for record in caplog.records if record.levelname == 'WARNING'
    )
    assert segment_warning_found, f"Expected segment implementation warning not found in logs: {caplog.text}"

def test_get_history_empty(manager):
    """Test getting history for a non-existent prompt."""
    assert manager.get_history("no_history_prompt") == []

def test_rollback_success(manager):
    """Test successfully rolling back to a previous version."""
    prompt_id = "prompt_rollback"
    t1, v1 = "Template v1", 1
    t2, v2 = "Template v2", 2
    t3, v3 = "Template v3", 3
    manager.register_prompt(prompt_id, t1, version=v1)
    time.sleep(manager.min_update_interval_seconds + 0.05) # Wait after registration
    success_v2 = manager.apply_modification(PromptModification(prompt_id=prompt_id, new_full_template=t2, change_description="v2"))
    assert success_v2, "Modification to v2 failed"
    assert manager.get_prompt_version(prompt_id) == v2
    time.sleep(manager.min_update_interval_seconds + 0.05) # Wait between modifications
    success_v3 = manager.apply_modification(PromptModification(prompt_id=prompt_id, new_full_template=t3, change_description="v3"))
    assert success_v3, "Modification to v3 failed"

    assert manager.get_prompt_version(prompt_id) == v3
    assert manager.get_prompt(prompt_id) == t3

    # Rollback to v1 (original registered state)
    assert manager.rollback(prompt_id, v1)
    assert manager.get_prompt_version(prompt_id) == v1
    assert manager.get_prompt(prompt_id) == t1
    history = manager.get_history(prompt_id)
    # History should now contain original v1, pre-v2 state (v1), pre-v3 state (v2), pre-rollback state(v3)
    # Due to max_history_size=3, the oldest (original v1) might be pushed out
    # Let's check the versions present
    history_versions = [v for v, t in history]
    assert v1 in history_versions # Should contain the state we rolled back from (v1) - wait, does it add the rolled back state?
    assert v2 in history_versions # Should contain state before v3 update
    assert v3 in history_versions # Should contain state before rollback
    # Rerun test_apply_modification_success history check mentally:
    # register(v1) -> history [(1,t1)]
    # apply_mod(v2) -> history [(1,t1), (1,t1)], current v2,t2
    # apply_mod(v3) -> history [(1,t1), (1,t1), (2,t2)], current v3,t3 -> deque drops oldest (1,t1) -> history [(1,t1),(2,t2)] NO, deque keeps newest
    # Apply V2: state v1,t1. History append (1, t1). Set state v2,t2. History: [(1,t1)]
    # Apply V3: state v2,t2. History append (2, t2). Set state v3,t3. History: [(1,t1), (2,t2)]
    # Rollback to V1: state v3,t3. History append(3, t3). Set state v1,t1. History: [(1,t1), (2,t2), (3,t3)]
    # Correct expected history versions after rollback to v1:
    assert sorted(history_versions) == [1, 2, 3] 

def test_rollback_to_current_version(manager):
    """Test rolling back to the current version (should succeed but do nothing)."""
    prompt_id = "prompt_rollback_current"
    t1, v1 = "Template v1", 1
    manager.register_prompt(prompt_id, t1, version=v1)
    history_before = manager.get_history(prompt_id)
    assert manager.rollback(prompt_id, v1)
    assert manager.get_prompt_version(prompt_id) == v1
    assert manager.get_prompt(prompt_id) == t1
    history_after = manager.get_history(prompt_id)
    # Rolling back to current version should not add to history
    assert history_after == history_before

def test_rollback_version_not_found(manager):
    """Test attempting to roll back to a version not in history."""
    prompt_id = "prompt_rollback_fail"
    t1, v1 = "Template v1", 1
    manager.register_prompt(prompt_id, t1, version=v1)
    assert not manager.rollback(prompt_id, 99) # Version 99 doesn't exist
    assert manager.get_prompt_version(prompt_id) == v1 # Should remain unchanged

def test_rollback_prompt_not_found(manager):
    """Test attempting to roll back a non-existent prompt ID."""
    assert not manager.rollback("does_not_exist", 1)

def test_history_limit(manager):
    """Test that history size is limited by max_history_size."""
    prompt_id = "prompt_history_limit"
    manager.register_prompt(prompt_id, "v1", 1)
    time.sleep(manager.min_update_interval_seconds + 0.05)
    manager.apply_modification(PromptModification(prompt_id=prompt_id, new_full_template="v2", change_description="v2"))
    time.sleep(manager.min_update_interval_seconds + 0.05)
    manager.apply_modification(PromptModification(prompt_id=prompt_id, new_full_template="v3", change_description="v3"))
    time.sleep(manager.min_update_interval_seconds + 0.05)
    manager.apply_modification(PromptModification(prompt_id=prompt_id, new_full_template="v4", change_description="v4"))
    
    assert manager.get_prompt_version(prompt_id) == 4
    history = manager.get_history(prompt_id)
    # max_history_size is 3. 
    # Register v1 -> hist [(1,v1)]
    # Apply v2 -> hist [(1,v1), (1,v1)] state v2
    # Apply v3 -> hist [(1,v1), (1,v1), (2,v2)] state v3
    # Apply v4 -> hist [(1,v1), (2,v2), (3,v3)] state v4 (deque drops oldest (1,v1))
    # Correct expected versions: 1, 2, 3 (state *before* modifications)
    history_versions = [v for v, t in history]
    assert len(history_versions) == 3
    assert sorted(history_versions) == [1, 2, 3] 