import sys
import os
import unittest
import logging
from unittest.mock import patch, MagicMock, call

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.kfm_agent import run_kfm_agent
from src.state_types import KFMAgentState


class TestKFMIntegration(unittest.TestCase):
    """Integration tests for the KFM Agent graph."""
    
    @patch('src.kfm_agent.print_execution_summary')
    @patch('src.kfm_agent.create_kfm_agent_graph')
    def test_run_kfm_agent_function(self, mock_create_graph, mock_print_summary):
        """Test the run_kfm_agent function that provides higher-level execution."""
        # Create mock graph and setup return values
        mock_graph = MagicMock()
        
        # Mock the final state returned by the graph
        mock_final_state = {
            'task_name': 'test_task',
            'input': {'text': 'Higher level execution test'},
            'kfm_action': {'action': 'marry', 'component': 'analyze_deep'},
            'active_component': 'analyze_deep',
            'result': {'analysis': 'Detailed analysis result'},
            'execution_performance': {'latency': 1.8, 'accuracy': 0.92},
            'done': True
        }
        mock_graph.invoke.return_value = mock_final_state
        
        # Mock components dictionary
        mock_components = {'registry': MagicMock(), 'monitor': MagicMock()}
        
        # Setup the create_graph mock to return our mocked graph and components
        mock_create_graph.return_value = (mock_graph, mock_components)
        
        # Execute via the run function
        input_data = {'text': 'Higher level execution test'}
        final_state = run_kfm_agent(input_data, task_name='test_task')
        
        # Verify the function returns the expected state
        self.assertEqual(final_state, mock_final_state)
        self.assertEqual(final_state.get('task_name'), 'test_task')
        self.assertEqual(final_state.get('input'), input_data)
        
        # Verify the correct initial state was passed to the graph
        mock_graph.invoke.assert_called_once()
        call_args = mock_graph.invoke.call_args[0][0]  # Get the first positional argument
        self.assertEqual(call_args['task_name'], 'test_task')
        self.assertEqual(call_args['input'], input_data)

    @patch('src.kfm_agent.create_kfm_agent')
    @patch('src.langgraph_nodes.call_llm_for_reflection')
    @patch('src.langgraph_nodes.print_execution_summary')
    def test_integration_flow_simulation(self, mock_print_summary, mock_call_llm, mock_create_kfm_agent):
        """Test the integrated flow through all nodes with a simulated execution."""
        # Mock the reflection function
        mock_call_llm.return_value = "Mock reflection text about KFM decision"
        
        # Create mock components
        mock_registry = MagicMock()
        mock_monitor = MagicMock()
        mock_planner = MagicMock()
        mock_engine = MagicMock()
        
        # Configure mocks with specific behaviors
        mock_monitor.get_performance_data.return_value = {
            'analyze_fast': {'latency': 0.5, 'accuracy': 0.8},
            'analyze_deep': {'latency': 2.0, 'accuracy': 0.95}
        }
        mock_monitor.get_task_requirements.return_value = {
            'latency_weight': 0.3,
            'accuracy_weight': 0.7
        }
        mock_planner.decide_kfm_action.return_value = {
            'action': 'marry',
            'component': 'analyze_deep'
        }
        mock_engine.get_active_component_key.return_value = 'analyze_deep'
        mock_engine.execute_task.return_value = (
            {'analysis': 'Detailed analysis result'},
            {'latency': 1.8, 'accuracy': 0.92}
        )
        
        # Set up the factory mock to return our mocks
        mock_create_kfm_agent.return_value = (
            mock_registry,
            mock_monitor,
            mock_planner,
            mock_engine
        )
        
        # Import here to use the patched factory
        from src.kfm_agent import create_kfm_agent_graph
        from langgraph.graph import StateGraph
        
        # Create graph with our mocked components
        kfm_app, components = create_kfm_agent_graph()
        
        # Create initial state
        initial_state = {
            'input': {'text': 'Sample text to analyze'},
            'task_name': 'default',
            'performance_data': {},
            'task_requirements': {},
            'kfm_action': None,
            'active_component': None,
            'result': None,
            'execution_performance': None,
            'error': None,
            'done': False
        }
        
        # Execute the graph
        final_state = kfm_app.invoke(initial_state)
        
        # Verify components were called
        mock_monitor.get_performance_data.assert_called_once()
        mock_monitor.get_task_requirements.assert_called_once_with('default')
        mock_planner.decide_kfm_action.assert_called_once_with('default')
        
        # Verify the KFM action was set in the state
        self.assertEqual(final_state.get('kfm_action'), {'action': 'marry', 'component': 'analyze_deep'})
        
        # Verify execution occurred
        mock_engine.get_active_component_key.assert_called_once()
        mock_engine.execute_task.assert_called_once()
        
        # Verify the execution results are in the state
        self.assertEqual(final_state.get('active_component'), 'analyze_deep')
        self.assertEqual(final_state.get('result'), {'analysis': 'Detailed analysis result'})
        self.assertEqual(final_state.get('execution_performance'), {'latency': 1.8, 'accuracy': 0.92})
        
        # Verify reflection was called
        mock_call_llm.assert_called_once()
        
        # Verify completion
        self.assertTrue(final_state.get('done', False))
        self.assertIsNone(final_state.get('error'))
    
    @patch('src.kfm_agent.create_kfm_agent')
    def test_error_handling_simulation(self, mock_create_kfm_agent):
        """Test error handling in the workflow with simulated execution."""
        # Create mock components
        mock_registry = MagicMock()
        mock_monitor = MagicMock()
        mock_planner = MagicMock()
        mock_engine = MagicMock()
        
        # Configure mocks with specific behaviors
        mock_monitor.get_performance_data.return_value = {
            'analyze_fast': {'latency': 0.5, 'accuracy': 0.8}
        }
        mock_monitor.get_task_requirements.return_value = {
            'latency_weight': 0.3,
            'accuracy_weight': 0.7
        }
        mock_planner.decide_kfm_action.return_value = {
            'action': 'marry',
            'component': 'analyze_deep'
        }
        
        # Simulate an error in the execution engine
        mock_engine.execute_task.side_effect = ValueError("Simulated execution error")
        
        # Set up the factory mock to return our mocks
        mock_create_kfm_agent.return_value = (
            mock_registry,
            mock_monitor,
            mock_planner,
            mock_engine
        )
        
        # Import here to use the patched factory
        from src.kfm_agent import create_kfm_agent_graph
        
        # Create graph with our mocked components
        kfm_app, components = create_kfm_agent_graph()
        
        # Create initial state
        initial_state = {
            'input': {'text': 'Text that causes an error'},
            'task_name': 'default',
            'performance_data': {},
            'task_requirements': {},
            'kfm_action': None,
            'active_component': None,
            'result': None,
            'execution_performance': None,
            'error': None,
            'done': False
        }
        
        # Execute the graph
        final_state = kfm_app.invoke(initial_state)
        
        # Verify error is properly captured
        self.assertIsNotNone(final_state.get('error'))
        self.assertIn("Simulated execution error", final_state.get('error', ''))
        self.assertTrue(final_state.get('done', False))
        
        # Verify component calls
        mock_monitor.get_performance_data.assert_called_once()
        mock_planner.decide_kfm_action.assert_called_once()
        mock_engine.execute_task.assert_called_once()
    
    @patch('src.kfm_agent.create_kfm_agent')
    def test_no_kfm_action_simulation(self, mock_create_kfm_agent):
        """Test the workflow when no KFM action is decided."""
        # Create mock components
        mock_registry = MagicMock()
        mock_monitor = MagicMock()
        mock_planner = MagicMock()
        mock_engine = MagicMock()
        
        # Configure mocks with specific behaviors 
        mock_monitor.get_performance_data.return_value = {
            'analyze_fast': {'latency': 0.5, 'accuracy': 0.8}
        }
        mock_monitor.get_task_requirements.return_value = {
            'latency_weight': 0.3,
            'accuracy_weight': 0.7
        }
        
        # Set planner to return None (no KFM action)
        mock_planner.decide_kfm_action.return_value = None
        
        mock_engine.get_active_component_key.return_value = 'analyze_balanced'
        mock_engine.execute_task.return_value = (
            {'summary': 'Basic analysis'},
            {'latency': 0.5, 'accuracy': 0.8}
        )
        
        # Set up the factory mock to return our mocks
        mock_create_kfm_agent.return_value = (
            mock_registry,
            mock_monitor,
            mock_planner,
            mock_engine
        )
        
        # Import here to use the patched factory
        from src.kfm_agent import create_kfm_agent_graph
        
        # Create graph with our mocked components
        kfm_app, components = create_kfm_agent_graph()
        
        # Create initial state
        initial_state = {
            'input': {'text': 'No action needed text'},
            'task_name': 'default',
            'performance_data': {},
            'task_requirements': {},
            'kfm_action': None,
            'active_component': None,
            'result': None,
            'execution_performance': None,
            'error': None,
            'done': False
        }
        
        # Execute the graph
        final_state = kfm_app.invoke(initial_state)
        
        # Verify state reflects no KFM action
        self.assertIsNone(final_state.get('kfm_action'))
        self.assertTrue(final_state.get('done', False))
        self.assertNotIn('reflections', final_state)
        
        # Verify component calls
        mock_monitor.get_performance_data.assert_called_once()
        mock_planner.decide_kfm_action.assert_called_once()
        mock_engine.execute_task.assert_called_once()


if __name__ == '__main__':
    # Enable detailed logging for tracing during tests
    logging.basicConfig(level=logging.DEBUG)
    unittest.main() 