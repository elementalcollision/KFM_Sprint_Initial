import unittest
from unittest.mock import patch, MagicMock, call
import json
import os
import time
import datetime
from typing import Dict, Any

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.recovery import (
    RecoveryMode,
    RecoveryPolicy,
    RecoveryManager,
    resume_execution_from_node,
    verify_safe_resumption,
    create_fallback_state,
    with_recovery
)

class MockLangGraphApp:
    """Mock LangGraph application for testing recovery mechanisms."""
    
    def __init__(self, nodes=None, node_functions=None):
        """
        Initialize with mock nodes and functions.
        
        Args:
            nodes: List of node names
            node_functions: Dict mapping node names to functions
        """
        self.nodes = nodes or ["node1", "node2", "node3"]
        self.node_functions = node_functions or {}
        
        # Create default node functions if not provided
        for node in self.nodes:
            if node not in self.node_functions:
                self.node_functions[node] = lambda state: state
        
        # Create mock graph
        self.graph = MagicMock()
        self.graph.nodes = self.nodes
        self.graph.get_node = lambda name: {"fn": self.node_functions.get(name, lambda state: state)}

class MockStateHistoryTracker:
    """Mock state history tracker for testing."""
    
    def __init__(self):
        self.history = []
    
    def add_state(self, node_name, state, is_input=False, metadata=None):
        self.history.append({
            "node_name": node_name,
            "state": state,
            "is_input": is_input,
            "metadata": metadata or {}
        })
    
    def get_history(self):
        return self.history

class TestRecovery(unittest.TestCase):
    """Test recovery mechanisms."""
    
    def setUp(self):
        # Create temp directory for checkpoints
        os.makedirs("logs/checkpoints", exist_ok=True)
    
    @patch("src.recovery.get_state_history_tracker")
    def test_recovery_manager_initialization(self, mock_get_tracker):
        """Test RecoveryManager initialization."""
        manager = RecoveryManager()
        
        self.assertEqual(manager.checkpoints, {})
        self.assertEqual(manager.retry_counters, {})
        self.assertEqual(manager.recovery_policies, {})
        self.assertIsInstance(manager.default_policy, RecoveryPolicy)
        self.assertEqual(manager.default_policy.mode, RecoveryMode.ABORT)
    
    def test_recovery_policy_defaults(self):
        """Test RecoveryPolicy default values."""
        policy = RecoveryPolicy()
        
        self.assertEqual(policy.mode, RecoveryMode.ABORT)
        self.assertEqual(policy.max_retries, 3)
        self.assertEqual(policy.backoff_factor, 1.5)
        self.assertIsNone(policy.rollback_checkpoint_id)
        self.assertEqual(policy.error_categories, [])
        self.assertIsNone(policy.fallback_function)
        self.assertIsNone(policy.custom_handler)
    
    @patch("src.recovery.create_state_checkpoint")
    def test_create_checkpoint(self, mock_create_checkpoint):
        """Test creating a checkpoint."""
        mock_create_checkpoint.return_value = "checkpoint-123"
        
        manager = RecoveryManager()
        state = {"key": "value"}
        checkpoint_id = manager.create_checkpoint(state, "Test Checkpoint")
        
        self.assertEqual(checkpoint_id, "checkpoint-123")
        self.assertIn("checkpoint-123", manager.checkpoints)
        self.assertEqual(manager.checkpoints["checkpoint-123"]["label"], "Test Checkpoint")
        self.assertEqual(len(manager._undo_stack), 1)
    
    @patch("src.recovery.get_state_snapshot")
    def test_rollback_to_checkpoint(self, mock_get_snapshot):
        """Test rolling back to a checkpoint."""
        mock_get_snapshot.return_value = {
            "state": {"key": "checkpoint_value"},
            "metadata": {"label": "Test Checkpoint"}
        }
        
        manager = RecoveryManager()
        manager.checkpoints = {"checkpoint-123": {"label": "Test Checkpoint"}}
        manager._undo_stack = [("checkpoint-123", {"key": "checkpoint_value"})]
        
        state = manager.rollback_to_checkpoint("checkpoint-123")
        
        self.assertEqual(state, {"key": "checkpoint_value"})
        self.assertEqual(len(manager._redo_stack), 1)
    
    @patch("src.recovery.get_state_snapshot")
    def test_rollback_nonexistent_checkpoint(self, mock_get_snapshot):
        """Test rolling back to a non-existent checkpoint."""
        mock_get_snapshot.return_value = None
        
        manager = RecoveryManager()
        
        with self.assertRaises(ValueError):
            manager.rollback_to_checkpoint("nonexistent-id")
    
    def test_undo_redo(self):
        """Test undo and redo operations."""
        manager = RecoveryManager()
        
        # Create some checkpoints
        manager._undo_stack = [
            ("checkpoint-1", {"step": 1}),
            ("checkpoint-2", {"step": 2}),
            ("checkpoint-3", {"step": 3})
        ]
        
        # Test undo
        state = manager.undo()
        self.assertEqual(state, {"step": 2})
        self.assertEqual(len(manager._undo_stack), 2)
        self.assertEqual(len(manager._redo_stack), 1)
        
        # Test redo
        state = manager.redo()
        self.assertEqual(state, {"step": 3})
        self.assertEqual(len(manager._undo_stack), 3)
        self.assertEqual(len(manager._redo_stack), 0)
    
    def test_retry_mechanism(self):
        """Test retry counter and delay mechanisms."""
        manager = RecoveryManager()
        
        # Set policy with custom retry values
        policy = RecoveryPolicy(mode=RecoveryMode.RETRY, max_retries=2, backoff_factor=2.0)
        manager.add_policy("test_node", policy)
        
        # Initial state
        self.assertTrue(manager.can_retry("test_node"))
        
        # First retry
        manager.increment_retry_count("test_node")
        self.assertEqual(manager.retry_counters["test_node"], 1)
        self.assertTrue(manager.can_retry("test_node"))
        self.assertEqual(manager.get_retry_delay("test_node"), 2.0)
        
        # Second retry
        manager.increment_retry_count("test_node")
        self.assertEqual(manager.retry_counters["test_node"], 2)
        self.assertFalse(manager.can_retry("test_node"))
        self.assertEqual(manager.get_retry_delay("test_node"), 4.0)
        
        # Reset retry counter
        manager.reset_retry_count("test_node")
        self.assertEqual(manager.retry_counters["test_node"], 0)
        self.assertTrue(manager.can_retry("test_node"))
    
    @patch("src.recovery.get_state_history_tracker")
    @patch("src.recovery.capture_error_context")
    def test_handle_error(self, mock_capture_error, mock_get_tracker):
        """Test error handling with different recovery modes."""
        # Return the original error to avoid issues with formatted_message
        mock_capture_error.side_effect = lambda error, **kwargs: error
        
        manager = RecoveryManager()
        
        # Test ABORT mode (default)
        error = ValueError("Test error")
        state = {"data": "value"}
        recovery_mode, updated_state = manager.handle_error(error, state, "node1")
        
        self.assertEqual(recovery_mode, RecoveryMode.ABORT)
        self.assertEqual(updated_state["error_type"], "ValueError")
        self.assertIn("recovery_attempted", updated_state)
        
        # Test RETRY mode
        retry_policy = RecoveryPolicy(mode=RecoveryMode.RETRY, max_retries=1)
        manager.add_policy("retry_node", retry_policy)
        
        recovery_mode, updated_state = manager.handle_error(error, state, "retry_node")
        
        self.assertEqual(recovery_mode, RecoveryMode.RETRY)
        self.assertEqual(manager.retry_counters["retry_node"], 1)
        
        # Test SKIP mode
        skip_policy = RecoveryPolicy(mode=RecoveryMode.SKIP)
        manager.add_policy("skip_node", skip_policy)
        
        recovery_mode, updated_state = manager.handle_error(error, state, "skip_node")
        
        self.assertEqual(recovery_mode, RecoveryMode.SKIP)
        
        # Test SUBSTITUTE mode
        def fallback_func(state, error, node_name):
            state = state.copy()
            state["fallback_applied"] = True
            return state
            
        substitute_policy = RecoveryPolicy(
            mode=RecoveryMode.SUBSTITUTE, 
            fallback_function=fallback_func
        )
        manager.add_policy("substitute_node", substitute_policy)
        
        recovery_mode, updated_state = manager.handle_error(error, state, "substitute_node")
        
        self.assertEqual(recovery_mode, RecoveryMode.SUBSTITUTE)
        self.assertTrue(updated_state["fallback_applied"])
    
    @patch("src.recovery.get_state_history_tracker")
    def test_resume_execution_from_node(self, mock_get_tracker):
        """Test resuming execution from a specific node."""
        # Create a mock tracker
        mock_tracker = MockStateHistoryTracker()
        mock_get_tracker.return_value = mock_tracker
        
        # Create test node functions
        def node1_func(state):
            state = state.copy()
            state["node1_executed"] = True
            return state
            
        def node2_func(state):
            state = state.copy()
            state["node2_executed"] = True
            return state
            
        def node3_func(state):
            state = state.copy()
            state["node3_executed"] = True
            return state
        
        # Create mock app
        app = MockLangGraphApp(
            nodes=["node1", "node2", "node3"],
            node_functions={
                "node1": node1_func,
                "node2": node2_func,
                "node3": node3_func
            }
        )
        
        # Test resuming from node2
        initial_state = {"initial": True}
        result_state = resume_execution_from_node(app, initial_state, "node2")
        
        # Verify execution
        self.assertFalse("node1_executed" in result_state)
        self.assertTrue(result_state["node2_executed"])
        self.assertTrue(result_state["node3_executed"])
        
        # Verify tracing
        history = mock_tracker.history
        self.assertEqual(len(history), 2)  # One entry per successful node
        self.assertEqual(history[0]["node_name"], "node2")
        self.assertEqual(history[1]["node_name"], "node3")
    
    def test_safe_resumption_verification(self):
        """Test verification of safe resumption conditions."""
        # Valid state
        valid_state = {"required1": "value", "required2": "value"}
        self.assertTrue(verify_safe_resumption(valid_state, ["required1", "required2"]))
        
        # Missing key
        invalid_state = {"required1": "value"}
        self.assertFalse(verify_safe_resumption(invalid_state, ["required1", "required2"]))
        
        # Partial execution
        partial_state = {
            "required1": "value", 
            "required2": "value",
            "_recovery": {"partial_execution": True}
        }
        self.assertFalse(verify_safe_resumption(partial_state, ["required1", "required2"]))
    
    def test_create_fallback_state(self):
        """Test creation of fallback state."""
        original_state = {"data": "value"}
        
        # Test validation node fallback
        validate_fallback = create_fallback_state(original_state, "validate_input")
        self.assertIn("_recovery", validate_fallback)
        self.assertIn("validation_results", validate_fallback)
        self.assertFalse(validate_fallback["validation_results"]["valid"])
        
        # Test process node fallback
        process_fallback = create_fallback_state(original_state, "process_data")
        self.assertTrue(process_fallback["processing_complete"])
        
        # Test execute node fallback
        execute_fallback = create_fallback_state(original_state, "execute_action")
        self.assertTrue(execute_fallback["execution_complete"])
        self.assertIn("result", execute_fallback)
    
    @patch("src.recovery.get_state_history_tracker")
    def test_with_recovery(self, mock_get_tracker):
        """Test executing a graph with recovery mechanisms."""
        # Create a mock tracker
        mock_tracker = MockStateHistoryTracker()
        mock_get_tracker.return_value = mock_tracker
        
        # Create test node functions
        def node1_func(state):
            state = state.copy()
            state["node1_executed"] = True
            return state
            
        def node2_func(state):
            if state.get("should_fail"):
                raise ValueError("Test failure")
            state = state.copy()
            state["node2_executed"] = True
            return state
            
        def node3_func(state):
            state = state.copy()
            state["node3_executed"] = True
            return state
        
        # Create mock app
        app = MockLangGraphApp(
            nodes=["node1", "node2", "node3"],
            node_functions={
                "node1": node1_func,
                "node2": node2_func,
                "node3": node3_func
            }
        )
        
        # Set recovery policies
        policies = {
            "node2": RecoveryPolicy(mode=RecoveryMode.SKIP)
        }
        
        # Test normal execution
        initial_state = {"initial": True}
        result_state = with_recovery(app, initial_state, policies)
        
        # Verify execution
        self.assertTrue(result_state["node1_executed"])
        self.assertTrue(result_state["node2_executed"])
        self.assertTrue(result_state["node3_executed"])
        
        # Test execution with error and SKIP policy
        failing_state = {"initial": True, "should_fail": True}
        result_state = with_recovery(app, failing_state, policies)
        
        # Verify execution with skip
        self.assertTrue(result_state["node1_executed"])
        self.assertFalse("node2_executed" in result_state)
        self.assertTrue(result_state["node3_executed"])
        self.assertIn("error", result_state)
        self.assertEqual(result_state["recovery_attempted"], "SKIP")

if __name__ == "__main__":
    unittest.main() 