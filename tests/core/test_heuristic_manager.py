import pytest
import time
import collections

# Add project root to path if tests are run from a different directory
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.heuristic_manager import HeuristicManager
from src.core.reflection_schemas import HeuristicUpdate, HeuristicParameterAdjustment

@pytest.fixture
def manager() -> HeuristicManager:
    """Provides a fresh HeuristicManager instance for each test."""
    return HeuristicManager(min_update_interval_seconds=0.1, max_history_size=3)

@pytest.fixture
def manager_long_interval() -> HeuristicManager:
    """Provides a HeuristicManager instance with a longer interval."""
    return HeuristicManager(min_update_interval_seconds=60, max_history_size=3)

# --- Test Data for Heuristics ---
HEURISTIC_ID_1 = "heuristic_one"
PARAMS_V1_H1 = {"threshold": 0.5, "mode": "strict"}
PARAMS_V2_H1 = {"threshold": 0.7, "mode": "strict", "new_param": True}
PARAMS_V3_H1 = {"threshold": 0.8, "mode": "lenient"}

HEURISTIC_ID_2 = "fallback_rules" # Special case for validation
PARAMS_V1_H2 = {"confidence_threshold": 0.7}
PARAMS_V2_H2_VALID = {"confidence_threshold": 0.9}
PARAMS_V2_H2_INVALID = {"confidence_threshold": 1.5} # Invalid value

def test_register_new_heuristic(manager):
    """Test registering a completely new heuristic."""
    assert manager.register_heuristic(HEURISTIC_ID_1, PARAMS_V1_H1, version=1)
    assert manager.get_parameters(HEURISTIC_ID_1) == PARAMS_V1_H1
    assert manager.get_heuristic_version(HEURISTIC_ID_1) == 1
    history = manager.get_history(HEURISTIC_ID_1)
    assert len(history) == 1
    assert history[0] == (1, PARAMS_V1_H1)

def test_register_heuristic_update_version(manager):
    """Test updating an existing heuristic with a newer version."""
    manager.register_heuristic(HEURISTIC_ID_1, PARAMS_V1_H1, version=1)
    assert manager.register_heuristic(HEURISTIC_ID_1, PARAMS_V2_H1, version=2)
    assert manager.get_parameters(HEURISTIC_ID_1) == PARAMS_V2_H1
    assert manager.get_heuristic_version(HEURISTIC_ID_1) == 2
    history = manager.get_history(HEURISTIC_ID_1)
    assert len(history) == 1 # Register resets history
    assert history[0] == (2, PARAMS_V2_H1)

def test_register_heuristic_same_version(manager):
    """Test attempting to register with the same version (should fail)."""
    manager.register_heuristic(HEURISTIC_ID_1, PARAMS_V1_H1, version=1)
    assert not manager.register_heuristic(HEURISTIC_ID_1, PARAMS_V2_H1, version=1)
    assert manager.get_parameters(HEURISTIC_ID_1) == PARAMS_V1_H1

def test_register_heuristic_older_version(manager):
    """Test attempting to register with an older version (should fail)."""
    manager.register_heuristic(HEURISTIC_ID_1, PARAMS_V2_H1, version=2)
    assert not manager.register_heuristic(HEURISTIC_ID_1, PARAMS_V1_H1, version=1)
    assert manager.get_parameters(HEURISTIC_ID_1) == PARAMS_V2_H1

def test_get_heuristic_not_found(manager):
    """Test getting a heuristic that hasn't been registered."""
    assert manager.get_parameters("non_existent_heuristic") is None
    assert manager.get_heuristic_version("non_existent_heuristic") is None

def test_apply_modification_success_single_param(manager):
    """Test applying a valid modification (single parameter adjustment)."""
    manager.register_heuristic(HEURISTIC_ID_1, PARAMS_V1_H1.copy(), version=1)
    time.sleep(manager.min_update_interval_seconds + 0.01) # Sleep after registration
    
    adj = HeuristicParameterAdjustment(parameter_name="threshold", new_value=0.75, reasoning="Test adjust")
    mod = HeuristicUpdate(heuristic_id=HEURISTIC_ID_1, parameter_adjustments=[adj], change_description="Update threshold")
    
    assert manager.apply_modification(mod)
    expected_params = PARAMS_V1_H1.copy()
    expected_params["threshold"] = 0.75
    assert manager.get_parameters(HEURISTIC_ID_1) == expected_params
    assert manager.get_heuristic_version(HEURISTIC_ID_1) == 2 # Version should increment
    history = manager.get_history(HEURISTIC_ID_1)
    assert len(history) == 2 
    assert history[0] == (1, PARAMS_V1_H1) # Original registration
    assert history[1] == (1, PARAMS_V1_H1) # State before modification

def test_apply_modification_add_new_param(manager):
    """Test applying modification that adds a new parameter (should be ignored)."""
    manager.register_heuristic(HEURISTIC_ID_1, PARAMS_V1_H1.copy(), version=1)
    time.sleep(manager.min_update_interval_seconds + 0.01) # Sleep after registration
    adj = HeuristicParameterAdjustment(parameter_name="new_key", new_value="new_val")
    mod = HeuristicUpdate(heuristic_id=HEURISTIC_ID_1, parameter_adjustments=[adj], change_description="Add new key")
    
    # Modification should fail because the parameter doesn't exist
    assert not manager.apply_modification(mod)
    # Parameters should remain unchanged
    assert manager.get_parameters(HEURISTIC_ID_1) == PARAMS_V1_H1 
    assert manager.get_heuristic_version(HEURISTIC_ID_1) == 1 # Version should not increment
    # Optionally, check logs for warning about missing parameter
    # caplog fixture would be needed for this test

def test_apply_modification_multiple_params(manager):
    """Test applying modification with multiple parameter adjustments."""
    manager.register_heuristic(HEURISTIC_ID_1, PARAMS_V1_H1.copy(), version=1)
    time.sleep(manager.min_update_interval_seconds + 0.01) # Sleep after registration
    adj1 = HeuristicParameterAdjustment(parameter_name="threshold", new_value=0.9)
    adj2 = HeuristicParameterAdjustment(parameter_name="mode", new_value="relaxed")
    mod = HeuristicUpdate(heuristic_id=HEURISTIC_ID_1, parameter_adjustments=[adj1, adj2], change_description="Update multiple")

    assert manager.apply_modification(mod)
    expected_params = {"threshold": 0.9, "mode": "relaxed"}
    assert manager.get_parameters(HEURISTIC_ID_1) == expected_params
    assert manager.get_heuristic_version(HEURISTIC_ID_1) == 2

def test_apply_modification_rate_limit(manager):
    """Test that heuristic modifications are rate limited."""
    manager.register_heuristic(HEURISTIC_ID_1, PARAMS_V1_H1.copy(), version=1)
    time.sleep(manager.min_update_interval_seconds + 0.01) # Sleep after registration
    adj1 = HeuristicParameterAdjustment(parameter_name="threshold", new_value=0.6)
    adj2 = HeuristicParameterAdjustment(parameter_name="threshold", new_value=0.8)
    # Need change_description for HeuristicUpdate validation
    mod1 = HeuristicUpdate(heuristic_id=HEURISTIC_ID_1, parameter_adjustments=[adj1], change_description="Update 1")
    mod2 = HeuristicUpdate(heuristic_id=HEURISTIC_ID_1, parameter_adjustments=[adj2], change_description="Update 2")

    assert manager.apply_modification(mod1)
    assert manager.get_heuristic_version(HEURISTIC_ID_1) == 2
    current_params = manager.get_parameters(HEURISTIC_ID_1)
    assert current_params["threshold"] == 0.6

    assert not manager.apply_modification(mod2) # Second should fail due to rate limit
    assert manager.get_parameters(HEURISTIC_ID_1) == current_params # Should not change
    assert manager.get_heuristic_version(HEURISTIC_ID_1) == 2

def test_apply_modification_after_rate_limit_interval(manager):
    """Test applying modification successfully after the rate limit interval."""
    manager.register_heuristic(HEURISTIC_ID_1, PARAMS_V1_H1.copy(), version=1)
    time.sleep(manager.min_update_interval_seconds + 0.01) # Sleep after registration
    adj1 = HeuristicParameterAdjustment(parameter_name="threshold", new_value=0.6)
    adj2 = HeuristicParameterAdjustment(parameter_name="threshold", new_value=0.8)
    # Need change_description
    mod1 = HeuristicUpdate(heuristic_id=HEURISTIC_ID_1, parameter_adjustments=[adj1], change_description="Update 1")
    mod2 = HeuristicUpdate(heuristic_id=HEURISTIC_ID_1, parameter_adjustments=[adj2], change_description="Update 2")

    assert manager.apply_modification(mod1)
    time.sleep(manager.min_update_interval_seconds + 0.05) # Increase sleep slightly
    assert manager.apply_modification(mod2)
    expected_params = PARAMS_V1_H1.copy()
    expected_params["threshold"] = 0.8
    assert manager.get_parameters(HEURISTIC_ID_1) == expected_params
    assert manager.get_heuristic_version(HEURISTIC_ID_1) == 3

def test_apply_modification_heuristic_not_found(manager):
    """Test applying modification to a non-existent heuristic ID."""
    adj = HeuristicParameterAdjustment(parameter_name="p", new_value=1)
    # Need change_description
    mod = HeuristicUpdate(heuristic_id="does_not_exist", parameter_adjustments=[adj], change_description="Try update non-existent")
    assert not manager.apply_modification(mod)

def test_apply_modification_no_adjustments(manager, caplog):
    """Test applying modification with no parameter_adjustments list (should log warning)."""
    manager.register_heuristic(HEURISTIC_ID_1, PARAMS_V1_H1.copy(), version=1)
    time.sleep(manager.min_update_interval_seconds + 0.01) # Sleep after registration
    mod = HeuristicUpdate(heuristic_id=HEURISTIC_ID_1, parameter_adjustments=None, change_description="No-op")
    
    assert not manager.apply_modification(mod) # Should not succeed if no adjustments
    assert manager.get_parameters(HEURISTIC_ID_1) == PARAMS_V1_H1
    assert manager.get_heuristic_version(HEURISTIC_ID_1) == 1
    assert "No parameter adjustments provided" in caplog.text

def test_apply_modification_empty_adjustments_list(manager, caplog):
    """Test applying modification with an empty parameter_adjustments list."""
    manager.register_heuristic(HEURISTIC_ID_1, PARAMS_V1_H1.copy(), version=1)
    time.sleep(manager.min_update_interval_seconds + 0.01) # Sleep after registration
    mod = HeuristicUpdate(heuristic_id=HEURISTIC_ID_1, parameter_adjustments=[], change_description="Empty list")

    assert not manager.apply_modification(mod) # Should not succeed if empty adjustments
    assert manager.get_parameters(HEURISTIC_ID_1) == PARAMS_V1_H1
    assert manager.get_heuristic_version(HEURISTIC_ID_1) == 1
    assert "No parameter adjustments provided" in caplog.text

# --- Tests for Specific Heuristic Parameter Validation ---
def test_apply_modification_fallback_rules_valid_threshold(manager):
    """Test valid confidence_threshold update for fallback_rules."""
    manager.register_heuristic(HEURISTIC_ID_2, PARAMS_V1_H2.copy(), version=1)
    time.sleep(manager.min_update_interval_seconds + 0.01) # Sleep after registration
    adj = HeuristicParameterAdjustment(parameter_name="confidence_threshold", new_value=0.85)
    # Need change_description
    mod = HeuristicUpdate(heuristic_id=HEURISTIC_ID_2, parameter_adjustments=[adj], change_description="Update fallback threshold valid")
    
    assert manager.apply_modification(mod)
    assert manager.get_parameters(HEURISTIC_ID_2)["confidence_threshold"] == 0.85
    assert manager.get_heuristic_version(HEURISTIC_ID_2) == 2

def test_apply_modification_fallback_rules_invalid_threshold_too_high(manager, caplog):
    """Test invalid confidence_threshold (too high) for fallback_rules."""
    manager.register_heuristic(HEURISTIC_ID_2, PARAMS_V1_H2.copy(), version=1)
    time.sleep(manager.min_update_interval_seconds + 0.01) # Sleep after registration
    adj = HeuristicParameterAdjustment(parameter_name="confidence_threshold", new_value=1.5)
    # Need change_description
    mod = HeuristicUpdate(heuristic_id=HEURISTIC_ID_2, parameter_adjustments=[adj], change_description="Update fallback threshold invalid high")
    
    assert not manager.apply_modification(mod)
    assert manager.get_parameters(HEURISTIC_ID_2)["confidence_threshold"] == PARAMS_V1_H2["confidence_threshold"]
    assert manager.get_heuristic_version(HEURISTIC_ID_2) == 1 # Version should not increment on failed validation
    assert "Invalid value for 'confidence_threshold'" in caplog.text

def test_apply_modification_fallback_rules_invalid_threshold_negative(manager, caplog):
    """Test invalid confidence_threshold (negative) for fallback_rules."""
    manager.register_heuristic(HEURISTIC_ID_2, PARAMS_V1_H2.copy(), version=1)
    time.sleep(manager.min_update_interval_seconds + 0.01) # Sleep after registration
    adj = HeuristicParameterAdjustment(parameter_name="confidence_threshold", new_value=-0.1)
    # Need change_description
    mod = HeuristicUpdate(heuristic_id=HEURISTIC_ID_2, parameter_adjustments=[adj], change_description="Update fallback threshold invalid negative")

    assert not manager.apply_modification(mod)
    assert manager.get_heuristic_version(HEURISTIC_ID_2) == 1
    assert "Invalid value for 'confidence_threshold'" in caplog.text

def test_apply_modification_fallback_rules_invalid_type(manager, caplog):
    """Test invalid confidence_threshold (wrong type) for fallback_rules."""
    manager.register_heuristic(HEURISTIC_ID_2, PARAMS_V1_H2.copy(), version=1)
    time.sleep(manager.min_update_interval_seconds + 0.01) # Sleep after registration
    adj = HeuristicParameterAdjustment(parameter_name="confidence_threshold", new_value="not_a_float")
    # Need change_description
    mod = HeuristicUpdate(heuristic_id=HEURISTIC_ID_2, parameter_adjustments=[adj], change_description="Update fallback threshold invalid type")

    assert not manager.apply_modification(mod)
    assert manager.get_heuristic_version(HEURISTIC_ID_2) == 1
    assert "Invalid value for 'confidence_threshold'" in caplog.text

# --- History and Rollback Tests (Similar to PromptManager) ---
def test_get_history_empty(manager):
    assert manager.get_history("no_history_heuristic") == []

def test_rollback_success(manager):
    manager.register_heuristic(HEURISTIC_ID_1, PARAMS_V1_H1, 1)
    time.sleep(manager.min_update_interval_seconds + 0.05) # Wait after registration
    success_v2 = manager.apply_modification(HeuristicUpdate(heuristic_id=HEURISTIC_ID_1, parameter_adjustments=[HeuristicParameterAdjustment(parameter_name="threshold", new_value=0.7)], change_description="v2"))
    assert success_v2, "Modification to v2 failed"
    assert manager.get_heuristic_version(HEURISTIC_ID_1) == 2
    time.sleep(manager.min_update_interval_seconds + 0.05) # Wait between modifications
    success_v3 = manager.apply_modification(HeuristicUpdate(heuristic_id=HEURISTIC_ID_1, parameter_adjustments=[HeuristicParameterAdjustment(parameter_name="threshold", new_value=0.9)], change_description="v3"))
    assert success_v3, "Modification to v3 failed"
    
    assert manager.get_heuristic_version(HEURISTIC_ID_1) == 3
    assert manager.get_parameters(HEURISTIC_ID_1)["threshold"] == 0.9

    assert manager.rollback(HEURISTIC_ID_1, 1) # Rollback to initial state
    assert manager.get_heuristic_version(HEURISTIC_ID_1) == 1
    assert manager.get_parameters(HEURISTIC_ID_1) == PARAMS_V1_H1
    history = manager.get_history(HEURISTIC_ID_1)
    history_versions = [v for v, p in history]
    # Register v1 -> hist [(1, P1)] state v1,P1
    # Apply v2 -> hist [(1,P1), (1,P1)] state v2,P2 {thr:0.7}
    # Apply v3 -> hist [(1,P1), (1,P1), (2,P2)] state v3,P3 {thr:0.9} -> deque drops (1,P1) -> [(1,P1),(2,P2)] state v3,P3
    # Rollback to v1 -> hist [(1,P1),(2,P2), (3,P3)] state v1,P1. (max_history=3)
    assert sorted(history_versions) == [1, 2, 3]

def test_rollback_to_current_version(manager):
    manager.register_heuristic(HEURISTIC_ID_1, PARAMS_V1_H1, 1)
    history_before = manager.get_history(HEURISTIC_ID_1)
    assert manager.rollback(HEURISTIC_ID_1, 1)
    assert manager.get_heuristic_version(HEURISTIC_ID_1) == 1
    assert manager.get_parameters(HEURISTIC_ID_1) == PARAMS_V1_H1
    history_after = manager.get_history(HEURISTIC_ID_1)
    assert history_after == history_before

def test_rollback_version_not_found(manager):
    manager.register_heuristic(HEURISTIC_ID_1, PARAMS_V1_H1, 1)
    assert not manager.rollback(HEURISTIC_ID_1, 99)
    assert manager.get_heuristic_version(HEURISTIC_ID_1) == 1

def test_rollback_heuristic_not_found(manager):
    assert not manager.rollback("does_not_exist_h", 1)

def test_history_limit(manager):
    manager.register_heuristic(HEURISTIC_ID_1, {"p":1}, 1) # Start with version 1
    time.sleep(manager.min_update_interval_seconds + 0.05)
    manager.apply_modification(HeuristicUpdate(heuristic_id=HEURISTIC_ID_1, parameter_adjustments=[HeuristicParameterAdjustment(parameter_name="p", new_value=2)], change_description="v2"))
    time.sleep(manager.min_update_interval_seconds + 0.05)
    manager.apply_modification(HeuristicUpdate(heuristic_id=HEURISTIC_ID_1, parameter_adjustments=[HeuristicParameterAdjustment(parameter_name="p", new_value=3)], change_description="v3"))
    time.sleep(manager.min_update_interval_seconds + 0.05)
    manager.apply_modification(HeuristicUpdate(heuristic_id=HEURISTIC_ID_1, parameter_adjustments=[HeuristicParameterAdjustment(parameter_name="p", new_value=4)], change_description="v4"))
    time.sleep(manager.min_update_interval_seconds + 0.05)
    manager.apply_modification(HeuristicUpdate(heuristic_id=HEURISTIC_ID_1, parameter_adjustments=[HeuristicParameterAdjustment(parameter_name="p", new_value=5)], change_description="v5"))

    assert manager.get_heuristic_version(HEURISTIC_ID_1) == 5 # 1->2, 2->3, 3->4, 4->5 
    history = manager.get_history(HEURISTIC_ID_1)
    # Max history 3. 
    # register v1 -> hist[(1,P1{p:1})] state v1,P1
    # apply v2 -> hist[(1,P1),(1,P1)] state v2, P2{p:2}
    # apply v3 -> hist[(1,P1),(1,P1),(2,P2)] state v3, P3{p:3} -> deque drops oldest (1,P1) -> [(1,P1),(2,P2)] state v3,P3
    # apply v4 -> hist[(1,P1),(2,P2),(3,P3)] state v4, P4{p:4} -> deque drops oldest (1,P1) -> [(2,P2),(3,P3)] state v4,P4
    # apply v5 -> hist[(2,P2),(3,P3),(4,P4)] state v5, P5{p:5} -> deque drops oldest (2,P2)
    # Expected versions in history: 2, 3, 4 (state *before* modifications resulting in versions 3, 4, 5)
    history_versions = sorted([v for v, p in history])
    assert len(history_versions) == 3
    assert history_versions == [2, 3, 4] # State *before* modifications resulting in versions 3,4,5 current. 