import sys
import os
import unittest
import json
from unittest.mock import patch, MagicMock, call

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.langgraph_nodes import execute_action_node
from src.state_types import KFMAgentState

class TestExecuteActionErrorHandling(unittest.TestCase):
    """Test cases for error handling in execute_action_node."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a mock execution engine
        self.mock_engine = MagicMock()
        
        # Create a basic state for testing
        self.test_state = {
            'input': {'text': 'Test input'},
            'kfm_action': {'action': 'adjust_kfm', 'component': 'analyze_deep'},
            'task_name': 'test_task'
        }
    
    def test_skip_on_previous_error(self):
        """Test that execution is skipped when there's a previous error in the state."""
        # Create state with existing error
        state_with_error = self.test_state.copy()
        state_with_error['error'] = 'Previous error'
        
        # Execute action
        result_state = execute_action_node(state_with_error, self.mock_engine)
        
        # Verify no methods of execution_engine were called
        self.mock_engine.apply_kfm_action.assert_not_called()
        self.mock_engine.get_active_component_key.assert_not_called()
        self.mock_engine.execute_task.assert_not_called()
        
        # Verify error was preserved
        self.assertEqual(result_state['error'], 'Previous error')
    
    @patch('src.langgraph_nodes.execute_logger')
    def test_error_applying_kfm_action(self, mock_logger):
        """Test error handling when applying KFM action fails."""
        # Setup mock to raise an exception
        self.mock_engine.apply_kfm_action.side_effect = ValueError("Test KFM action error")
        
        # Execute action
        result_state = execute_action_node(self.test_state, self.mock_engine)
        
        # Verify error was captured
        self.assertIn('error', result_state)
        
        # Parse the JSON error string
        error_data = json.loads(result_state['error'])
        
        # Verify error structure and content
        self.assertEqual(error_data['type'], 'ValueError')
        self.assertEqual(error_data['message'], 'Test KFM action error')
        self.assertEqual(error_data['category'], 'Error applying KFM action')
        self.assertEqual(error_data['severity'], 'ERROR')
        self.assertFalse(error_data['context']['recoverable'])
        
        # Verify task execution was not attempted
        self.mock_engine.execute_task.assert_not_called()
        
        # Verify done flag was set
        self.assertTrue(result_state['done'])
        
        # Verify proper logging
        mock_logger.exception.assert_called()
    
    @patch('src.langgraph_nodes.execute_logger')
    def test_error_getting_active_component(self, mock_logger):
        """Test error handling when getting active component fails."""
        # Setup mocks: KFM action succeeds but getting component fails
        self.mock_engine.get_active_component_key.side_effect = RuntimeError("Component registry error")
        
        # Execute action
        result_state = execute_action_node(self.test_state, self.mock_engine)
        
        # Verify error was captured
        self.assertIn('error', result_state)
        
        # Parse the JSON error string
        error_data = json.loads(result_state['error'])
        
        # Verify error structure and content
        self.assertEqual(error_data['type'], 'RuntimeError')
        self.assertEqual(error_data['message'], 'Component registry error')
        self.assertEqual(error_data['category'], 'Error retrieving active component')
        self.assertEqual(error_data['severity'], 'ERROR')
        
        # Verify task execution was not attempted
        self.mock_engine.execute_task.assert_not_called()
        
        # Verify done flag was set
        self.assertTrue(result_state['done'])
    
    @patch('src.langgraph_nodes.execute_logger')
    def test_error_executing_task(self, mock_logger):
        """Test error handling when task execution fails."""
        # Setup mocks: KFM action and getting component succeed, but execution fails
        self.mock_engine.get_active_component_key.return_value = 'analyze_deep'
        self.mock_engine.execute_task.side_effect = Exception("Task execution failed")
        
        # Execute action
        result_state = execute_action_node(self.test_state, self.mock_engine)
        
        # Verify error was captured
        self.assertIn('error', result_state)
        
        # Parse the JSON error string
        error_data = json.loads(result_state['error'])
        
        # Verify error structure and content
        self.assertEqual(error_data['type'], 'Exception')
        self.assertEqual(error_data['message'], 'Task execution failed')
        self.assertEqual(error_data['category'], 'Error executing task')
        self.assertEqual(error_data['component'], 'analyze_deep')
        self.assertEqual(error_data['severity'], 'ERROR')
        
        # Verify done flag was set
        self.assertTrue(result_state['done'])
    
    @patch('src.langgraph_nodes.execute_logger')
    def test_error_reported_by_execution(self, mock_logger):
        """Test handling when execution returns an error in the result."""
        # Setup mocks: Execution returns an error in the result
        self.mock_engine.get_active_component_key.return_value = 'analyze_deep'
        self.mock_engine.execute_task.return_value = (
            {'error': 'Component execution error'},
            {'latency': 1.5, 'accuracy': 0}
        )
        
        # Execute action
        result_state = execute_action_node(self.test_state, self.mock_engine)
        
        # Verify error was captured
        self.assertIn('error', result_state)
        
        # Parse the JSON error string
        error_data = json.loads(result_state['error'])
        
        # Verify error structure and content
        self.assertEqual(error_data['type'], 'ComponentExecutionError')
        self.assertEqual(error_data['message'], 'Component execution error')
        self.assertEqual(error_data['component'], 'analyze_deep')
        self.assertEqual(error_data['category'], 'Component reported error')
        self.assertEqual(error_data['severity'], 'ERROR')
        self.assertTrue(error_data['context']['recoverable'])
        
        # Verify result and performance were still saved
        self.assertIn('result', result_state)
        self.assertIn('execution_performance', result_state)
        
        # Verify done flag was set
        self.assertTrue(result_state['done'])
    
    @patch('src.langgraph_nodes.execute_logger')
    def test_missing_active_component(self, mock_logger):
        """Test error handling when no active component is available."""
        # Setup mocks: No active component available
        self.mock_engine.get_active_component_key.return_value = None
        
        # Execute action
        result_state = execute_action_node(self.test_state, self.mock_engine)
        
        # Verify error was captured
        self.assertIn('error', result_state)
        
        # Parse the JSON error string
        error_data = json.loads(result_state['error'])
        
        # Verify error structure and content
        self.assertEqual(error_data['type'], 'ComponentError')
        self.assertEqual(error_data['message'], 'No active component available for execution')
        self.assertEqual(error_data['category'], 'Error retrieving active component')
        
        # Verify task execution was not attempted
        self.mock_engine.execute_task.assert_not_called()
        
        # Verify done flag was set
        self.assertTrue(result_state['done'])
    
    @patch('src.langgraph_nodes.execute_logger')
    def test_type_error_executing_task(self, mock_logger):
        """Test error handling for type errors during task execution."""
        # Setup mocks: KFM action and getting component succeed, but execution has a type error
        self.mock_engine.get_active_component_key.return_value = 'analyze_deep'
        self.mock_engine.execute_task.side_effect = TypeError("Invalid input type")
        
        # Execute action
        result_state = execute_action_node(self.test_state, self.mock_engine)
        
        # Verify error was captured
        self.assertIn('error', result_state)
        
        # Parse the JSON error string
        error_data = json.loads(result_state['error'])
        
        # Verify error structure and content
        self.assertEqual(error_data['type'], 'TypeError')
        self.assertEqual(error_data['message'], 'Invalid input type')
        self.assertEqual(error_data['category'], 'Error executing task')
        self.assertEqual(error_data['component'], 'analyze_deep')
        self.assertEqual(error_data['severity'], 'ERROR')
        
        # Verify done flag was set
        self.assertTrue(result_state['done'])
    
    @patch('src.langgraph_nodes.execute_logger')
    def test_value_error_executing_task(self, mock_logger):
        """Test error handling for value errors during task execution."""
        # Setup mocks: KFM action and getting component succeed, but execution has a value error
        self.mock_engine.get_active_component_key.return_value = 'analyze_deep'
        self.mock_engine.execute_task.side_effect = ValueError("Invalid input value")
        
        # Execute action
        result_state = execute_action_node(self.test_state, self.mock_engine)
        
        # Verify error was captured
        self.assertIn('error', result_state)
        
        # Parse the JSON error string
        error_data = json.loads(result_state['error'])
        
        # Verify error structure and content
        self.assertEqual(error_data['type'], 'ValueError')
        self.assertEqual(error_data['message'], 'Invalid input value')
        self.assertEqual(error_data['category'], 'Error executing task')
        self.assertEqual(error_data['component'], 'analyze_deep')
        self.assertEqual(error_data['severity'], 'ERROR')
        
        # Verify done flag was set
        self.assertTrue(result_state['done'])
    
    @patch('src.langgraph_nodes.execute_logger')
    def test_key_error_applying_kfm_action(self, mock_logger):
        """Test error handling for key errors when applying KFM action."""
        # Setup mock to raise a KeyError
        self.mock_engine.apply_kfm_action.side_effect = KeyError("component")
        
        # Execute action
        result_state = execute_action_node(self.test_state, self.mock_engine)
        
        # Verify error was captured
        self.assertIn('error', result_state)
        
        # Parse the JSON error string
        error_data = json.loads(result_state['error'])
        
        # Verify error structure and content
        self.assertEqual(error_data['type'], 'KeyError')
        self.assertTrue('Missing key' in error_data['message'])
        self.assertEqual(error_data['category'], 'Error applying KFM action')
        self.assertEqual(error_data['severity'], 'ERROR')
        
        # Verify task execution was not attempted
        self.mock_engine.execute_task.assert_not_called()
        
        # Verify done flag was set
        self.assertTrue(result_state['done'])
    
    @patch('src.langgraph_nodes.execute_logger')
    def test_successful_execution(self, mock_logger):
        """Test successful execution path to ensure error handling doesn't interfere."""
        # Setup successful execution
        self.mock_engine.get_active_component_key.return_value = 'analyze_deep'
        self.mock_engine.execute_task.return_value = (
            {'analysis_result': 'Good analysis'},
            {'latency': 1.5, 'accuracy': 0.95}
        )
        
        # Execute action
        result_state = execute_action_node(self.test_state, self.mock_engine)
        
        # Verify no error was captured
        self.assertNotIn('error', result_state)
        
        # Verify result and performance were saved
        self.assertEqual(result_state['active_component'], 'analyze_deep')
        self.assertEqual(result_state['result'], {'analysis_result': 'Good analysis'})
        self.assertEqual(result_state['execution_performance'], {'latency': 1.5, 'accuracy': 0.95})
        
        # Verify done flag was set
        self.assertTrue(result_state['done'])

if __name__ == '__main__':
    unittest.main() 