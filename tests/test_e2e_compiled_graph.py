import sys
import os
import unittest
import logging
from unittest.mock import patch, MagicMock

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.kfm_agent import create_kfm_agent_graph, run_kfm_agent
from src.state_types import KFMAgentState
from src.langgraph_nodes import call_llm_for_reflection
from tests.test_compiled_graph_execution import CompiledGraphTestHarness
from tests.test_scenarios import TestScenarios


class TestE2ECompiledGraph(CompiledGraphTestHarness):
    """End-to-end tests for the compiled graph execution with full scenarios."""
    
    def setUp(self):
        """Set up test fixtures, including mock components and tracing."""
        super().setUp()
        # Get all test scenarios
        self.scenarios = TestScenarios.get_all_scenarios()
    
    def configure_mocks_for_scenario(self, scenario_name):
        """Configure mock components for the specified scenario.
        
        Args:
            scenario_name: Name of the scenario to configure
        """
        if scenario_name not in self.scenarios:
            raise ValueError(f"Unknown scenario: {scenario_name}")
        
        scenario = self.scenarios[scenario_name]
        
        # Configure mock monitor
        if "performance_data" in scenario:
            self.mock_monitor.get_performance_data.return_value = scenario["performance_data"]
        if "task_requirements" in scenario:
            self.mock_monitor.get_task_requirements.return_value = scenario["task_requirements"]
        
        # Configure mock planner
        if "kfm_action" in scenario:
            self.mock_planner.decide_kfm_action.return_value = scenario["kfm_action"]
        
        # Configure mock execution engine
        if "execution_error" in scenario:
            self.mock_engine.execute_task.side_effect = Exception(scenario["execution_error"])
        elif "execution_result" in scenario and "execution_performance" in scenario:
            self.mock_engine.execute_task.return_value = (
                scenario["execution_result"],
                scenario["execution_performance"]
            )
        
        # Configure active component
        if "kfm_action" in scenario:
            self.mock_engine.get_active_component_key.return_value = scenario["kfm_action"].get("component")
        
        # Return the configured scenario for reference
        return scenario
    
    def test_happy_path_scenario(self):
        """Test the happy path scenario with successful execution."""
        # Configure mocks for happy path
        scenario = self.configure_mocks_for_scenario("happy_path")
        
        # Execute the graph
        with patch('src.langgraph_nodes.call_llm_for_reflection') as mock_llm_call:
            # Configure mock reflection
            mock_llm_call.return_value = "The keep decision was appropriate given the good performance."
            
            # Run the graph
            final_state = self.execute_graph(
                input_data=scenario["input_data"],
                task_name=scenario["task_name"]
            )
            
            # Verify execution completed successfully
            self.assertIsNotNone(final_state)
            self.assertNotIn('error', final_state)
            
            # Verify state contains expected fields
            self.assertTrue(self.verify_final_state(final_state, scenario["expected_final_keys"]))
            
            # Verify execution sequence
            self.assertTrue(self.verify_node_execution_sequence(scenario["expected_sequence"]))
            
            # Verify reflection was called
            mock_llm_call.assert_called_once()
            
            # Verify reflection insights and analysis
            self.assertIn('reflection_insights', final_state)
            self.assertIn('reflection_analysis', final_state)
            
            # Verify KFM action and component
            self.assertEqual(final_state['kfm_action']['action'], 'keep')
            self.assertEqual(final_state['active_component'], 'component_a')
            
            # Dump trace for analysis
            self.dump_trace_to_file(f"{scenario['name']}_trace.json")
    
    def test_kill_action_scenario(self):
        """Test the scenario with 'kill' KFM action."""
        # Configure mocks for kill action
        scenario = self.configure_mocks_for_scenario("kill_action")
        
        # Execute the graph
        with patch('src.langgraph_nodes.call_llm_for_reflection') as mock_llm_call:
            # Configure mock reflection for kill action
            mock_llm_call.return_value = "The kill decision was appropriate due to poor performance."
            
            # Run the graph
            final_state = self.execute_graph(
                input_data=scenario["input_data"],
                task_name=scenario["task_name"]
            )
            
            # Verify execution completed successfully
            self.assertIsNotNone(final_state)
            self.assertNotIn('error', final_state)
            
            # Verify state contains expected fields
            self.assertTrue(self.verify_final_state(final_state, scenario["expected_final_keys"]))
            
            # Verify execution sequence
            self.assertTrue(self.verify_node_execution_sequence(scenario["expected_sequence"]))
            
            # Verify reflection was called
            mock_llm_call.assert_called_once()
            
            # Verify KFM action and component
            self.assertEqual(final_state['kfm_action']['action'], 'kill')
            self.assertEqual(final_state['active_component'], 'component_a')
            
            # Dump trace for analysis
            self.dump_trace_to_file(f"{scenario['name']}_trace.json")
    
    def test_marry_action_scenario(self):
        """Test the scenario with 'marry' KFM action."""
        # Configure mocks for marry action
        scenario = self.configure_mocks_for_scenario("marry_action")
        
        # Execute the graph
        with patch('src.langgraph_nodes.call_llm_for_reflection') as mock_llm_call:
            # Configure mock reflection for marry action
            mock_llm_call.return_value = "The marry decision was appropriate due to excellent performance."
            
            # Run the graph
            final_state = self.execute_graph(
                input_data=scenario["input_data"],
                task_name=scenario["task_name"]
            )
            
            # Verify execution completed successfully
            self.assertIsNotNone(final_state)
            self.assertNotIn('error', final_state)
            
            # Verify state contains expected fields
            self.assertTrue(self.verify_final_state(final_state, scenario["expected_final_keys"]))
            
            # Verify execution sequence
            self.assertTrue(self.verify_node_execution_sequence(scenario["expected_sequence"]))
            
            # Verify reflection was called
            mock_llm_call.assert_called_once()
            
            # Verify KFM action and component
            self.assertEqual(final_state['kfm_action']['action'], 'marry')
            self.assertEqual(final_state['active_component'], 'component_a')
            
            # Dump trace for analysis
            self.dump_trace_to_file(f"{scenario['name']}_trace.json")
    
    def test_execution_error_scenario(self):
        """Test the scenario with an error during execution."""
        # Configure mocks for execution error
        scenario = self.configure_mocks_for_scenario("execution_error")
        
        # Execute the graph
        with patch('src.langgraph_nodes.call_llm_for_reflection') as mock_llm_call:
            # Configure mock reflection
            mock_llm_call.return_value = "Reflection on execution error."
            
            # Run the graph
            final_state = self.execute_graph(
                input_data=scenario["input_data"],
                task_name=scenario["task_name"]
            )
            
            # Verify execution completed with error
            self.assertIsNotNone(final_state)
            self.assertIn('error', final_state)
            self.assertIn(scenario["execution_error"], final_state['error'])
            
            # Verify done flag is set
            self.assertTrue(final_state.get('done', False))
            
            # Verify state contains expected fields and doesn't have unexpected ones
            self.assertTrue(self.verify_final_state(
                final_state, 
                scenario["expected_final_keys"],
                scenario.get("unexpected_final_keys", [])
            ))
            
            # Dump trace for analysis
            self.dump_trace_to_file(f"{scenario['name']}_trace.json")
    
    def test_reflection_error_scenario(self):
        """Test the scenario with an error during reflection."""
        # Configure mocks for reflection error
        scenario = self.configure_mocks_for_scenario("reflection_error")
        
        # Execute the graph
        with patch('src.langgraph_nodes.call_llm_for_reflection') as mock_llm_call:
            # Configure mock reflection to raise error
            mock_llm_call.side_effect = Exception(scenario["reflection_error"])
            
            # Run the graph
            final_state = self.execute_graph(
                input_data=scenario["input_data"],
                task_name=scenario["task_name"]
            )
            
            # Verify execution completed
            self.assertIsNotNone(final_state)
            self.assertNotIn('error', final_state)  # Main workflow should not error
            
            # Verify state contains expected fields
            self.assertTrue(self.verify_final_state(final_state, scenario["expected_final_keys"]))
            
            # Verify reflection was called
            mock_llm_call.assert_called_once()
            
            # Verify reflection contains error message
            self.assertIn('reflection', final_state)
            self.assertIn('[LLM REFLECTION ERROR]', final_state.get('reflection', ''))
            
            # Verify validation results
            self.assertIn('validation_results', final_state)
            self.assertFalse(final_state['validation_results'].get('reflection_success', True))
            
            # Dump trace for analysis
            self.dump_trace_to_file(f"{scenario['name']}_trace.json")
    
    def test_all_scenarios(self):
        """Test all scenarios in sequence."""
        # Exclude scenarios that cause errors
        excluded_scenarios = ["missing_fields"]
        scenario_names = [name for name in self.scenarios.keys() 
                         if name not in excluded_scenarios]
        
        for scenario_name in scenario_names:
            # Reset for each scenario
            reset_trace_history = getattr(self, 'reset_trace_history', None)
            if reset_trace_history:
                reset_trace_history()
            
            # Configure mocks for this scenario
            scenario = self.configure_mocks_for_scenario(scenario_name)
            
            # Configure reflection mock based on scenario
            if "reflection_error" in scenario:
                # Skip this in all_scenarios test as it needs special handling
                continue
            
            with patch('src.langgraph_nodes.call_llm_for_reflection') as mock_llm_call:
                # Configure mock reflection
                mock_action = scenario.get("kfm_action", {}).get("action", "keep")
                mock_llm_call.return_value = f"The {mock_action} decision was appropriate."
                
                try:
                    # Run the graph
                    final_state = self.execute_graph(
                        input_data=scenario["input_data"],
                        task_name=scenario["task_name"]
                    )
                    
                    # Basic verification based on scenario expectation
                    if scenario.get("expected_error", False):
                        self.assertIn('error', final_state)
                    else:
                        self.assertIsNotNone(final_state)
                        if "execution_error" not in scenario:
                            self.assertNotIn('error', final_state)
                    
                    # Print summary for each scenario
                    print(f"\nScenario '{scenario_name}' executed.")
                    if final_state and 'error' in final_state:
                        print(f"Error: {final_state['error']}")
                    
                except Exception as e:
                    print(f"Scenario '{scenario_name}' failed with exception: {str(e)}")
                    self.fail(f"Scenario '{scenario_name}' failed with exception: {str(e)}")


if __name__ == '__main__':
    unittest.main() 