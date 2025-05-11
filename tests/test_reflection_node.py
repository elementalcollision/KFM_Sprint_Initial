import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.state_types import KFMAgentState
from src.langgraph_nodes import reflection_node, reflect_node


class TestReflectionNode(unittest.TestCase):
    """Test cases for the reflection_node function in the KFM Agent LangGraph."""
    
    @patch('src.langgraph_nodes.call_llm_for_reflection')
    def test_valid_state_reflection(self, mock_llm_call):
        """Test reflection with a valid state containing kfm_decision and no errors."""
        # Setup mock
        mock_llm_call.return_value = "This is a valid reflection on the KFM decision."
        
        # Create a valid state
        state: KFMAgentState = {
            'kfm_action': {
                'action': 'keep', 
                'component': 'component_a', 
                'reason': 'Good performance'
            },
            'active_component': 'component_a',
            'result': {'status': 'success'},
            'execution_performance': {'latency': 0.5, 'accuracy': 0.95}
        }
        
        # Call the reflection node
        result = reflection_node(state)
        
        # Assertions
        self.assertIn('reflections', result)
        self.assertIn('reflection', result)
        self.assertEqual(result['reflection'], "This is a valid reflection on the KFM decision.")
        self.assertEqual(len(result['reflections']), 1)
        self.assertIn('validation_results', result)
        self.assertTrue(result['validation_results']['valid'])
        self.assertNotIn('error', result)
    
    def test_missing_kfm_decision(self):
        """Test validation when kfm_decision is missing from the state."""
        # Create a state without kfm_decision
        state: KFMAgentState = {
            'task_name': 'test_task',
            'active_component': 'component_a',
            'result': {'status': 'success'}
        }
        
        # Call the reflection node
        result = reflection_node(state)
        
        # Assertions
        self.assertIn('validation_results', result)
        self.assertFalse(result['validation_results'].get('kfm_decision_exists', True))
        self.assertIn('message', result['validation_results'])
        self.assertIn('No KFM decision found', result['validation_results']['message'])
        self.assertEqual(len(result.get('reflections', [])), 0)
        self.assertNotIn('error', result)  # Should not set an error in this case
    
    def test_with_non_null_error(self):
        """Test validation when there's an error in the state."""
        # Create a state with an error
        state: KFMAgentState = {
            'kfm_action': {
                'action': 'keep', 
                'component': 'component_a'
            },
            'error': 'Previous execution error'
        }
        
        # Call the reflection node
        result = reflection_node(state)
        
        # Assertions
        self.assertIn('validation_results', result)
        self.assertFalse(result['validation_results'].get('error_check', True))
        self.assertIn('message', result['validation_results'])
        self.assertIn('Error exists in state', result['validation_results']['message'])
        self.assertEqual(len(result.get('reflections', [])), 0)
        self.assertEqual(result['error'], 'Previous execution error')  # Should preserve the error
    
    def test_invalid_kfm_decision_structure(self):
        """Test validation when kfm_decision is not a dictionary."""
        # Create a state with invalid kfm_decision structure
        state: KFMAgentState = {
            'kfm_action': "invalid_string_instead_of_dict",
            'active_component': 'component_a'
        }
        
        # Call the reflection node
        result = reflection_node(state)
        
        # Assertions
        self.assertIn('validation_results', result)
        self.assertFalse(result['validation_results'].get('valid_structure', True))
        self.assertIn('message', result['validation_results'])
        self.assertIn('not a dictionary', result['validation_results']['message'])
        self.assertEqual(len(result.get('reflections', [])), 0)
        self.assertIn('error', result)  # Should set an error in this case
    
    def test_missing_required_fields(self):
        """Test validation when kfm_decision is missing required fields."""
        # Create a state with kfm_decision missing required fields
        state: KFMAgentState = {
            'kfm_action': {
                'action': 'keep'
                # Missing 'component' field
            },
            'active_component': 'component_a'
        }
        
        # Call the reflection node
        result = reflection_node(state)
        
        # Assertions
        self.assertIn('validation_results', result)
        self.assertFalse(result['validation_results'].get('has_required_fields', True))
        self.assertIn('message', result['validation_results'])
        self.assertIn('Missing required fields', result['validation_results']['message'])
        self.assertEqual(len(result.get('reflections', [])), 0)
        self.assertIn('error', result)  # Should set an error in this case
    
    def test_invalid_action_type(self):
        """Test validation when kfm_decision has an invalid action type."""
        # Create a state with invalid action type
        state: KFMAgentState = {
            'kfm_action': {
                'action': 'invalid_action',  # Not a valid KFM action
                'component': 'component_a'
            },
            'active_component': 'component_a'
        }
        
        # Call the reflection node
        result = reflection_node(state)
        
        # Assertions
        self.assertIn('validation_results', result)
        self.assertFalse(result['validation_results'].get('valid_action_type', True))
        self.assertIn('message', result['validation_results'])
        self.assertIn('Invalid action type', result['validation_results']['message'])
        self.assertEqual(len(result.get('reflections', [])), 0)
        self.assertIn('error', result)  # Should set an error in this case
    
    @patch('src.langgraph_nodes.call_llm_for_reflection')
    def test_llm_reflection_exception(self, mock_llm_call):
        """Test handling of exceptions during the LLM reflection call."""
        # Setup mock to raise an exception
        mock_llm_call.side_effect = Exception("LLM API error")
        
        # Create a valid state
        state: KFMAgentState = {
            'kfm_action': {
                'action': 'keep', 
                'component': 'component_a'
            },
            'active_component': 'component_a',
            'execution_performance': {'latency': 0.5}
        }
        
        # Call the reflection node
        result = reflection_node(state)
        
        # Assertions
        self.assertIn('reflections', result)
        self.assertIn('reflection', result)
        self.assertTrue('[LLM REFLECTION ERROR]' in result['reflection'])
        self.assertEqual(len(result['reflections']), 1)
        self.assertIn('validation_results', result)
        self.assertTrue(result['validation_results']['valid'])
        self.assertFalse(result['validation_results'].get('reflection_success', True))
        self.assertNotIn('error', result)  # Reflection errors shouldn't fail the process
    
    @patch('src.langgraph_nodes.reflection_node')
    def test_backwards_compatibility(self, mock_reflection_node):
        """Test that the original reflect_node delegates to the new implementation."""
        # Setup mock
        mock_state = {'test': 'value'}
        mock_reflection_node.return_value = {'test': 'updated'}
        
        # Call the original reflect_node
        result = reflect_node(mock_state)
        
        # Assertions
        mock_reflection_node.assert_called_once_with(mock_state)
        self.assertEqual(result, {'test': 'updated'})


if __name__ == '__main__':
    unittest.main() 