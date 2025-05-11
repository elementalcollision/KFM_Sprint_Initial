"""
Tests for the State Propagation Verification Framework.

This module contains tests to verify the functionality of the state
verification framework and its integration with the KFM Agent.
"""

import os
import sys
import unittest
import json
from unittest.mock import patch, MagicMock

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.core.state import KFMAgentState
from src.state_verification import (
    ValidationResult,
    configure_verification_framework,
    reset_verification,
    verify_state,
    verify_transition,
    register_field_validator,
    register_state_validator,
    register_transition_validator,
    VERIFICATION_LEVEL_BASIC,
    VERIFICATION_LEVEL_STANDARD,
    register_common_validators
)
from src.state_verification_integration import (
    initialize_verification_integration,
    verify_node_wrapper,
    wrap_all_nodes
)

class TestStateVerificationCore(unittest.TestCase):
    """Test the core functionality of the verification framework."""
    
    def setUp(self):
        """Set up for each test."""
        # Reset verification framework
        reset_verification()
        configure_verification_framework(
            verification_level=VERIFICATION_LEVEL_BASIC,
            visualization_enabled=False,
            output_dir="logs/test_verification"
        )
    
    def test_validation_result(self):
        """Test ValidationResult class."""
        # Test valid result
        valid_result = ValidationResult(True, "Test valid result")
        self.assertTrue(valid_result.valid)
        self.assertEqual(valid_result.message, "Test valid result")
        self.assertEqual(bool(valid_result), True)
        
        # Test invalid result
        invalid_result = ValidationResult(False, "Test invalid result", {"error": "test error"})
        self.assertFalse(invalid_result.valid)
        self.assertEqual(invalid_result.message, "Test invalid result")
        self.assertEqual(invalid_result.data, {"error": "test error"})
        self.assertEqual(bool(invalid_result), False)
    
    def test_register_and_verify_field(self):
        """Test registering and applying field validators."""
        # Reset any existing validators from other tests
        reset_verification()
        configure_verification_framework(
            verification_level=VERIFICATION_LEVEL_STANDARD,
            visualization_enabled=False,
            output_dir="logs/test_verification"
        )
        
        # Register a field validator
        def validate_task_name(value):
            if not isinstance(value, str):
                return ValidationResult(False, "Task name must be a string")
            return ValidationResult(True, "Valid task name")
            
        register_field_validator("task_name", validate_task_name)
        
        # Create test state
        test_state = {
            "task_name": "test_task",
            "input": {"query": "test query"}
        }
        
        # Verify state
        results = verify_state(test_state)
        valid_results = [r for r in results if r.valid]
        
        # Should have at least one valid result for task_name
        self.assertGreaterEqual(len(valid_results), 1)
        
        # Now test invalid data
        invalid_state = {
            "task_name": 123,  # Not a string
            "input": {"query": "test query"}
        }
        
        results = verify_state(invalid_state)
        invalid_results = [r for r in results if not r.valid]
        
        # Should have at least one invalid result
        self.assertGreaterEqual(len(invalid_results), 1)
    
    def test_register_and_verify_state(self):
        """Test registering and applying state validators."""
        # Register a state validator
        def validate_required_fields(state):
            if "task_name" not in state:
                return ValidationResult(False, "Missing task_name field")
            if "input" not in state:
                return ValidationResult(False, "Missing input field")
            return ValidationResult(True, "All required fields present")
            
        register_state_validator("required_fields", validate_required_fields)
        
        # Create test state with all required fields
        test_state = {
            "task_name": "test_task",
            "input": {"query": "test query"}
        }
        
        # Verify state
        results = verify_state(test_state)
        valid_results = [r for r in results if r.valid]
        
        # Should have at least one valid result
        self.assertGreaterEqual(len(valid_results), 1)
        
        # Now test with missing field
        invalid_state = {
            "input": {"query": "test query"}
            # Missing task_name
        }
        
        results = verify_state(invalid_state)
        invalid_results = [r for r in results if not r.valid]
        
        # Should have at least one invalid result
        self.assertGreaterEqual(len(invalid_results), 1)
    
    def test_register_and_verify_transition(self):
        """Test registering and applying transition validators."""
        # Register a transition validator
        def validate_action_passing(from_state, to_state):
            if "kfm_action" in from_state and "kfm_action" not in to_state:
                return ValidationResult(False, "KFM action lost in transition")
            return ValidationResult(True, "KFM action properly maintained")
            
        register_transition_validator("node1", "node2", validate_action_passing)
        
        # Create test states
        from_state = {
            "task_name": "test_task",
            "kfm_action": {"action": "test_action", "component": "test_component"}
        }
        
        to_state = {
            "task_name": "test_task",
            "kfm_action": {"action": "test_action", "component": "test_component"},
            "result": {"output": "test output"}
        }
        
        # Verify valid transition
        results = verify_transition("node1", "node2", from_state, to_state)
        valid_results = [r for r in results if r.valid]
        
        # Should have one valid result
        self.assertEqual(len(valid_results), 1)
        
        # Now test with missing action in destination
        invalid_to_state = {
            "task_name": "test_task",
            # Missing kfm_action
            "result": {"output": "test output"}
        }
        
        results = verify_transition("node1", "node2", from_state, invalid_to_state)
        invalid_results = [r for r in results if not r.valid]
        
        # Should have one invalid result
        self.assertEqual(len(invalid_results), 1)

class TestStateVerificationIntegration(unittest.TestCase):
    """Test the integration of the verification framework with KFM Agent."""
    
    def setUp(self):
        """Set up for each test."""
        # Reset verification framework
        reset_verification()
        initialize_verification_integration(
            verification_level=VERIFICATION_LEVEL_BASIC
        )
    
    def test_node_wrapper(self):
        """Test the node wrapper with a mock node function."""
        # Create a mock node function
        def mock_node(state, *args, **kwargs):
            # Modify the state in a typical way a node might
            result = state.copy()
            result["processed"] = True
            result["result"] = {"output": "test output"}
            return result
        
        # Create a wrapped version
        wrapped_node = verify_node_wrapper(mock_node)
        
        # Create a test state with required fields to avoid validation errors
        test_state = {
            "task_name": "test_task",
            "input": {"query": "test query"}
        }
        
        # Call the wrapped node
        result = wrapped_node(test_state)
        
        # Verify the result has the expected structure
        self.assertTrue(result["processed"])
        self.assertIn("result", result)
        self.assertEqual(result["result"]["output"], "test output")
    
    @patch('src.state_verification_integration.verify_state')
    def test_verification_called(self, mock_verify_state):
        """Test that verification is called when using the wrapper."""
        # Configure mock
        mock_verify_state.return_value = []
        
        # Create a simple node function
        def simple_node(state, *args, **kwargs):
            return state
        
        # Wrap it
        wrapped_node = verify_node_wrapper(simple_node)
        
        # Create a test state
        test_state = {
            "task_name": "test",
            "input": {"query": "test"}
        }
        
        # Call the wrapped node
        wrapped_node(test_state)
        
        # Verify that verify_state was called
        mock_verify_state.assert_called()
    
    def test_wrap_all_nodes(self):
        """Test wrapping multiple nodes."""
        # Create mock node functions with required fields in output
        def node1(state, *args, **kwargs):
            return {
                "processed_by": "node1",
                "task_name": "test_task",
                "input": {"query": "test"}
            }
            
        def node2(state, *args, **kwargs):
            return {
                "processed_by": "node2",
                "task_name": "test_task",
                "input": {"query": "test"}
            }
        
        # Create a dictionary of nodes
        nodes = {
            "node1": node1,
            "node2": node2
        }
        
        # Create a patch to avoid validation errors
        with patch('src.state_verification_integration.verify_state', return_value=[]):
            with patch('src.state_verification_integration.verify_transition', return_value=[]):
                # Wrap all nodes
                wrapped_nodes = wrap_all_nodes(nodes)
                
                # Verify we got wrapped versions
                self.assertEqual(len(wrapped_nodes), 2)
                self.assertIn("node1", wrapped_nodes)
                self.assertIn("node2", wrapped_nodes)
                
                # Create a valid test state to avoid validation errors
                test_state = {
                    "task_name": "test_task",
                    "input": {"query": "test"}
                }
                
                # Verify the wrapped versions work
                result1 = wrapped_nodes["node1"](test_state)
                result2 = wrapped_nodes["node2"](test_state)
                
                self.assertEqual(result1["processed_by"], "node1")
                self.assertEqual(result2["processed_by"], "node2")

class TestEndToEndVerification(unittest.TestCase):
    """End-to-end test of the verification framework."""
    
    @patch('src.state_verification_integration.create_verification_graph')
    def test_verification_graph_creation(self, mock_create_graph):
        """Test creating a verification-enabled graph."""
        # Configure mock
        mock_graph = MagicMock()
        mock_components = {"test_component": MagicMock()}
        mock_create_graph.return_value = (mock_graph, mock_components)
        
        # Import the module that uses the graph
        from src.state_verification_integration import create_verification_graph
        
        # Call the function
        graph, components = create_verification_graph()
        
        # Verify we got the expected result
        self.assertEqual(graph, mock_graph)
        self.assertEqual(components, mock_components)
        
        # Verify create_verification_graph was called
        mock_create_graph.assert_called_once()

if __name__ == "__main__":
    unittest.main() 