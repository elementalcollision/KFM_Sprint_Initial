import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.langgraph_nodes import reflect_node


class TestReflectNode(unittest.TestCase):
    """Test cases for the reflect_node function."""
    
    @patch('src.langgraph_nodes.reflect_logger')
    @patch('src.langgraph_nodes.call_llm_for_reflection')
    def test_reflection_with_kfm_action(self, mock_llm_reflection, mock_logger):
        """Test reflection when KFM action is present and no error exists."""
        # Create a test state with KFM action and no error
        state = {
            'kfm_action': {'action': 'marry', 'component': 'analyze_deep'},
            'active_component': 'analyze_deep',
            'result': {'analysis': 'Sample result'},
            'execution_performance': {'latency': 1.5, 'accuracy': 0.95},
            'error': None
        }
        
        # Mock the LLM reflection call
        mock_llm_reflection.return_value = "Mock reflection text."
        
        # Call the reflect_node
        result_state = reflect_node(state)
        
        # Verify logger was called with expected messages
        mock_logger.info.assert_any_call(f"Performing reflection on KFM decision: {state['kfm_action']}")
        mock_logger.info.assert_any_call(f"Used component: {state['active_component']}")
        mock_logger.debug.assert_any_call(f"Result: {state['result']}")
        mock_logger.debug.assert_any_call(f"Performance: {state['execution_performance']}")
        
        # Verify LLM reflection was called
        mock_llm_reflection.assert_called_once_with(state)
        
        # Verify reflection info was logged
        mock_logger.info.assert_any_call("Reflection generated:")
        mock_logger.info.assert_any_call("Mock reflection text.")
        
        # Verify reflections list was created and populated
        self.assertIn('reflections', result_state)
        self.assertEqual(len(result_state['reflections']), 1)
        self.assertEqual(result_state['reflections'][0], "Mock reflection text.")
        
        # Verify single reflection field is also set (backward compatibility)
        self.assertEqual(result_state['reflection'], "Mock reflection text.")
        
        # Verify other state fields are unchanged
        for key in state:
            self.assertEqual(result_state[key], state[key])
    
    @patch('src.langgraph_nodes.reflect_logger')
    @patch('src.langgraph_nodes.call_llm_for_reflection')
    def test_multiple_reflections(self, mock_llm_reflection, mock_logger):
        """Test that multiple reflections are accumulated in the reflections list."""
        # Create a test state that already has a reflection
        state = {
            'kfm_action': {'action': 'marry', 'component': 'analyze_deep'},
            'active_component': 'analyze_deep',
            'result': {'analysis': 'Sample result'},
            'execution_performance': {'latency': 1.5, 'accuracy': 0.95},
            'error': None,
            'reflections': ["Previous reflection."]
        }
        
        # Mock the LLM reflection call
        mock_llm_reflection.return_value = "New reflection text."
        
        # Call the reflect_node
        result_state = reflect_node(state)
        
        # Verify reflections list now has two items
        self.assertEqual(len(result_state['reflections']), 2)
        self.assertEqual(result_state['reflections'][0], "Previous reflection.")
        self.assertEqual(result_state['reflections'][1], "New reflection text.")
        
        # Verify the most recent reflection is set as the single reflection field
        self.assertEqual(result_state['reflection'], "New reflection text.")
        
        # Verify the reflection history log was generated
        mock_logger.info.assert_any_call("Reflection added to history. Total reflections: 2")
    
    @patch('src.langgraph_nodes.reflect_logger')
    def test_reflection_with_error(self, mock_logger):
        """Test reflection when an error is present."""
        # Create a test state with an error
        state = {
            'kfm_action': {'action': 'marry', 'component': 'analyze_deep'},
            'error': 'Test error occurred'
        }
        
        # Call the reflect_node
        result_state = reflect_node(state)
        
        # Verify logger was called with error message
        mock_logger.warning.assert_called_once_with(f"Skipping reflection due to error: {state['error']}")
        
        # Verify state is returned unchanged
        self.assertEqual(result_state, state)
    
    @patch('src.langgraph_nodes.reflect_logger')
    def test_reflection_without_kfm_action(self, mock_logger):
        """Test reflection when no KFM action is present."""
        # Create a test state without KFM action
        state = {
            'kfm_action': None,
            'active_component': 'analyze_fast',
            'result': {'analysis': 'Sample result'},
            'execution_performance': {'latency': 0.5, 'accuracy': 0.85},
            'error': None
        }
        
        # Call the reflect_node
        result_state = reflect_node(state)
        
        # Verify logger was called with appropriate message
        mock_logger.info.assert_called_once_with("Skipping reflection: No KFM decision was made")
        
        # Verify state is returned unchanged
        self.assertEqual(result_state, state)


if __name__ == '__main__':
    unittest.main() 