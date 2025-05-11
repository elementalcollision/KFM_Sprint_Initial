import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.state_types import KFMAgentState
from src.langgraph_nodes import (
    monitor_state_node, 
    kfm_decision_node, 
    execute_action_node, 
    reflection_node
)


class TestCompleteWorkflow(unittest.TestCase):
    """Integration tests for the complete KFM agent workflow with reflection."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create mock dependencies
        self.mock_state_monitor = MagicMock()
        self.mock_kfm_planner = MagicMock()
        self.mock_execution_engine = MagicMock()
        
        # Configure mock state monitor
        self.mock_state_monitor.get_performance_data.return_value = {
            'component_a': {'latency': 0.5, 'accuracy': 0.95},
            'component_b': {'latency': 0.8, 'accuracy': 0.85}
        }
        self.mock_state_monitor.get_task_requirements.return_value = {
            'max_latency': 1.0,
            'min_accuracy': 0.9
        }
        
        # Configure mock KFM planner
        self.mock_kfm_planner.decide_kfm_action.return_value = {
            'action': 'keep',
            'component': 'component_a',
            'reason': 'Good performance metrics'
        }
        
        # Configure mock execution engine
        self.mock_execution_engine.apply_kfm_action.return_value = None
        self.mock_execution_engine.get_active_component_key.return_value = 'component_a'
        self.mock_execution_engine.execute_task.return_value = (
            {'status': 'success', 'data': {'records': 10}},
            {'latency': 0.5, 'accuracy': 0.95}
        )
        
        # Initial state
        self.initial_state = {
            'task_name': 'test_task',
            'input': {'query': 'test query'}
        }
    
    def test_complete_workflow(self):
        """Test the complete KFM agent workflow from monitoring to reflection."""
        # Step 1: Monitoring
        monitored_state = monitor_state_node(
            self.initial_state,
            self.mock_state_monitor
        )
        
        # Verify monitoring results
        self.assertIn('performance_data', monitored_state)
        self.assertIn('task_requirements', monitored_state)
        
        # Step 2: Decision making
        decision_state = kfm_decision_node(
            monitored_state,
            self.mock_kfm_planner
        )
        
        # Verify decision results
        self.assertIn('kfm_action', decision_state)
        self.assertEqual(decision_state['kfm_action']['action'], 'keep')
        
        # Step 3: Execution
        execution_state = execute_action_node(
            decision_state,
            self.mock_execution_engine
        )
        
        # Verify execution results
        self.assertIn('active_component', execution_state)
        self.assertIn('result', execution_state)
        self.assertIn('execution_performance', execution_state)
        self.assertEqual(execution_state['active_component'], 'component_a')
        
        # Step 4: Reflection
        final_state = reflection_node(execution_state)
        
        # Verify reflection results
        self.assertIn('reflection', final_state)
        self.assertIn('reflections', final_state)
        self.assertIn('reflection_insights', final_state)
        self.assertIn('reflection_analysis', final_state)
        self.assertIn('validation_results', final_state)
        
        # Verify insights structure
        insights = final_state['reflection_insights']
        self.assertIn('summary', insights)
        self.assertIn('strengths', insights)
        self.assertIn('improvements', insights)
        self.assertIn('recommendation', insights)
        
        # Verify analysis structure
        analysis = final_state['reflection_analysis']
        self.assertIn('decision_appropriate', analysis)
        self.assertIn('execution_effective', analysis)
        self.assertIn('confidence', analysis)
    
    def test_workflow_with_error_in_execution(self):
        """Test the workflow when an error occurs during execution."""
        # Setup mock execution engine to return an error
        error_execution_engine = MagicMock()
        error_execution_engine.apply_kfm_action.return_value = None
        error_execution_engine.get_active_component_key.return_value = 'component_a'
        error_execution_engine.execute_task.side_effect = Exception("Test execution error")
        
        # Run through the workflow until execution
        monitored_state = monitor_state_node(
            self.initial_state,
            self.mock_state_monitor
        )
        decision_state = kfm_decision_node(
            monitored_state,
            self.mock_kfm_planner
        )
        
        # Execute with error
        execution_state = execute_action_node(
            decision_state,
            error_execution_engine
        )
        
        # Verify error is captured
        self.assertIn('error', execution_state)
        self.assertTrue(execution_state['done'])
        
        # Verify reflection still works with error state
        final_state = reflection_node(execution_state)
        
        # Verify reflection results with error
        self.assertIn('validation_results', final_state)
        self.assertFalse(final_state['validation_results'].get('error_check', True))
        self.assertNotIn('reflection_insights', final_state)  # Shouldn't proceed to reflection


if __name__ == '__main__':
    unittest.main() 