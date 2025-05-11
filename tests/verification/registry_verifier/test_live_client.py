"""
Unit tests for LiveComponentRegistryClient
"""

import unittest
from typing import Dict, Any
import sys
import os

# Add the src directory to the path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from src.core.component_registry import ComponentRegistry
from src.verification.registry_verifier.live_client import LiveComponentRegistryClient
from src.verification.registry_verifier.verifier import RegistryStateVerifier

class TestLiveComponentRegistryClient(unittest.TestCase):
    """Test cases for the LiveComponentRegistryClient class."""
    
    def setUp(self):
        """Set up test environment before each test method."""
        # Create a test registry with some test components
        self.registry = ComponentRegistry()
        
        # Define test component functions
        def test_component_1(input_data):
            """Test component 1 docstring."""
            return {"result": f"Component 1 processed {input_data}"}, 0.8
        
        def test_component_2(input_data):
            """Test component 2 docstring."""
            return {"result": f"Component 2 processed {input_data}"}, 0.95
        
        # Add some custom attributes to component functions for testing attribute extraction
        test_component_1.accuracy_level = 0.8
        test_component_1.latency_profile = "fast"
        test_component_2.accuracy_level = 0.95
        test_component_2.latency_profile = "slow"
        
        # Register the components
        self.registry.register_component("component_1", test_component_1, True)  # This one is default
        self.registry.register_component("component_2", test_component_2)
        
        # Create the client
        self.client = LiveComponentRegistryClient(self.registry)
        
    def test_get_component_state_returns_metadata(self):
        """Test that get_component_state returns appropriate metadata."""
        # Get state for component_1
        state = self.client.get_component_state("component_1")
        
        # Verify basic metadata
        self.assertIsNotNone(state)
        self.assertEqual(state["component_id"], "component_1")
        self.assertTrue(state["is_default"])
        self.assertTrue(state["callable"])
        self.assertEqual(state["function_name"], "test_component_1")
        
        # Verify custom attributes
        self.assertEqual(state["attr_accuracy_level"], 0.8)
        self.assertEqual(state["attr_latency_profile"], "fast")
        
        # Verify docstring
        self.assertIn("Test component 1 docstring", state["doc"])
        
        # Verify signature information
        self.assertIn("signature", state)
        self.assertIn("parameters", state["signature"])
        self.assertEqual(state["signature"]["parameter_count"], 1)
        
    def test_get_component_state_nonexistent_component(self):
        """Test that get_component_state returns None for nonexistent components."""
        state = self.client.get_component_state("nonexistent_component")
        self.assertIsNone(state)
        
    def test_get_all_components_state(self):
        """Test that get_all_components_state returns states for all components."""
        all_states = self.client.get_all_components_state()
        
        # Verify we got states for both components
        self.assertIn("component_1", all_states)
        self.assertIn("component_2", all_states)
        
        # Verify default flag is correct
        self.assertTrue(all_states["component_1"]["is_default"])
        self.assertFalse(all_states["component_2"]["is_default"])
        
        # Verify attributes
        self.assertEqual(all_states["component_1"]["attr_accuracy_level"], 0.8)
        self.assertEqual(all_states["component_2"]["attr_accuracy_level"], 0.95)
        
    def test_get_registry_snapshot(self):
        """Test that get_registry_snapshot returns a complete registry snapshot."""
        snapshot = self.client.get_registry_snapshot()
        
        # Verify basic registry metadata
        self.assertIn("components", snapshot)
        self.assertIn("default_component_key", snapshot)
        self.assertIn("component_count", snapshot)
        self.assertIn("snapshot_time", snapshot)
        
        # Verify correct values
        self.assertEqual(snapshot["default_component_key"], "component_1")
        self.assertEqual(snapshot["component_count"], 2)
        
        # Verify components are included
        self.assertIn("component_1", snapshot["components"])
        self.assertIn("component_2", snapshot["components"])
        
    def test_with_registry_state_verifier(self):
        """Test using the LiveComponentRegistryClient with RegistryStateVerifier."""
        # Create a verifier using our client
        verifier = RegistryStateVerifier(self.client)
        
        # Define expected attributes for verification
        expected_attributes = {
            "component_1": {
                "is_default": True,
                "attr_accuracy_level": 0.8,
                "attr_latency_profile": "fast"
            },
            "component_2": {
                "is_default": False,
                "attr_accuracy_level": 0.95,
                "attr_latency_profile": "slow"
            }
        }
        
        # Run verification
        result = verifier.verify_multiple_components(expected_attributes)
        
        # Check that verification passed
        self.assertTrue(result.overall_passed)
        self.assertEqual(result.error_count, 0)
        
        # Run a verification that should fail
        bad_expectations = {
            "component_1": {
                "is_default": False,  # This is wrong, should fail
                "attr_accuracy_level": 0.9  # This is wrong, should fail
            },
            "nonexistent_component": {  # This component doesn't exist, should fail
                "some_attr": "some_value"
            }
        }
        
        # Run verification with bad expectations
        result = verifier.verify_multiple_components(bad_expectations)
        
        # Check that verification failed
        self.assertFalse(result.overall_passed)
        self.assertGreater(result.error_count, 0)

if __name__ == "__main__":
    unittest.main() 