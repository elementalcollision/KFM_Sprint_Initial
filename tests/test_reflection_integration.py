import sys
import os
import unittest
from unittest.mock import patch

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.state_types import KFMAgentState
from src.langgraph_nodes import reflection_node, call_llm_for_reflection


class TestReflectionIntegration(unittest.TestCase):
    """Integration tests for the reflection_node with the mock call_llm_for_reflection."""
    
    def test_integration_with_valid_state(self):
        """Test that reflection_node works correctly with our mock call_llm_for_reflection."""
        # Create a valid state with all required fields
        state: KFMAgentState = {
            'kfm_action': {
                'action': 'keep', 
                'component': 'database_service'
            },
            'active_component': 'database_service',
            'result': {'status': 'success'},
            'execution_performance': {'latency': 0.5, 'accuracy': 0.95}
        }
        
        # Call the reflection node
        result = reflection_node(state)
        
        # Verify that the reflection was added to the state
        self.assertIn('reflection', result)
        self.assertIn('reflections', result)
        self.assertEqual(len(result['reflections']), 1)
        
        # Verify that the reflection contains expected content from our mock
        self.assertIn("Reflection on Keep Decision", result['reflection'])
        self.assertIn("database_service", result['reflection'])
        
        # Verify validation results
        self.assertIn('validation_results', result)
        self.assertTrue(result['validation_results']['valid'])
        self.assertNotIn('error', result)
    
    def test_integration_with_different_action_types(self):
        """Test integration with different KFM action types."""
        # Test actions
        actions = ['keep', 'kill', 'marry']
        
        for action in actions:
            with self.subTest(action=action):
                # Create a state with the current action
                state: KFMAgentState = {
                    'kfm_action': {
                        'action': action, 
                        'component': 'test_component'
                    },
                    'active_component': 'test_component',
                    'result': {'status': 'success'},
                    'execution_performance': {'latency': 0.5, 'accuracy': 0.95}
                }
                
                # Call the reflection node
                result = reflection_node(state)
                
                # Verify that the reflection contains action-specific content
                self.assertIn(f"Reflection on {action.capitalize()} Decision", result['reflection'])
                self.assertTrue(result['validation_results']['valid'])
    
    def test_integration_with_validation_failure(self):
        """Test that validation failures in reflection_node work as expected."""
        # Create a state with missing required fields
        state: KFMAgentState = {
            'kfm_action': {
                # Missing 'action' field
                'component': 'test_component'
            }
        }
        
        # Call the reflection node
        result = reflection_node(state)
        
        # Verify that validation failed
        self.assertIn('validation_results', result)
        self.assertFalse(result['validation_results'].get('has_required_fields', True))
        self.assertIn('error', result)
        
        # Verify no reflection was added
        self.assertNotIn('reflection', result)
        self.assertEqual(len(result.get('reflections', [])), 0)
    
    def test_integration_capitalized_action(self):
        """Test integration with capitalized action names."""
        # Create a state with capitalized action
        state: KFMAgentState = {
            'kfm_action': {
                'action': 'KEEP',  # Capitalized 
                'component': 'test_component'
            },
            'active_component': 'test_component',
            'result': {'status': 'success'},
            'execution_performance': {'latency': 0.5, 'accuracy': 0.95}
        }
        
        # Call the reflection node
        result = reflection_node(state)
        
        # Verify that the reflection worked correctly with case-insensitive action
        self.assertIn('reflection', result)
        self.assertIn("Reflection on Keep Decision", result['reflection'])
        self.assertTrue(result['validation_results']['valid'])
    
    @patch('src.langgraph_nodes.call_llm_for_reflection')
    def test_llm_function_is_called(self, mock_llm_call):
        """Test that our function is actually called by reflection_node."""
        # Setup the mock
        mock_llm_call.return_value = "Mock reflection response"
        
        # Create a valid state
        state: KFMAgentState = {
            'kfm_action': {
                'action': 'keep', 
                'component': 'test_component'
            },
            'active_component': 'test_component'
        }
        
        # Call the reflection node
        reflection_node(state)
        
        # Verify that our function was called - using any_call instead of assert_called_once_with
        # since reflection_node modifies the state before calling the function
        self.assertEqual(mock_llm_call.call_count, 1)
        # Ensure the first argument (state) contains our expected values
        call_args = mock_llm_call.call_args[0][0]
        self.assertEqual(call_args['kfm_action']['action'], 'keep')
        self.assertEqual(call_args['kfm_action']['component'], 'test_component')
        self.assertEqual(call_args['active_component'], 'test_component')


if __name__ == '__main__':
    unittest.main() 