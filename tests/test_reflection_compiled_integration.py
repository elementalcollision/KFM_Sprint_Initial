import sys
import os
import unittest
import logging
from unittest.mock import patch, MagicMock, call
import src.kfm_agent  # Import src modules
import src.langgraph_nodes

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.kfm_agent import create_kfm_agent_graph, run_kfm_agent
from src.state_types import KFMAgentState
from src.langgraph_nodes import call_llm_for_reflection, extract_reflection_insights
from tests.test_compiled_graph_execution import CompiledGraphTestHarness


class TestReflectionCompiledIntegration(CompiledGraphTestHarness):
    """Tests for the reflection node integration in the compiled graph."""
    
    def setUp(self):
        """Set up test fixtures, including mock components and tracing."""
        super().setUp()
        
        # Set up standard inputs
        self.standard_input = {"text": "Reflection integration test input"}
        self.task_name = "reflection_integration_test"
        
        # Expected mock reflection output
        self.mock_reflection_text = """# Reflection on Keep Decision for Component 'analyze_balanced'

## Decision Analysis
The keep decision for component 'analyze_balanced' was appropriate given its performance metrics.

## Execution Assessment
The execution using component 'analyze_balanced' met the requirements.
- Latency: 1.0s (within acceptable range)
- Accuracy: 0.85 (meets minimum requirement of 0.8)

## Performance Analysis
The component shows a good balance between latency and accuracy, making it a reliable choice for this task.
"""
        
        # Set up mock for LLM reflection
        self.patcher = patch('src.langgraph_nodes.call_llm_for_reflection')
        self.mock_llm_client = self.patcher.start()
        self.mock_llm_client.return_value = self.mock_reflection_text
        
        # Performance data for tests
        self.test_performance_data = {
            "analyze_fast": {"latency": 0.5, "accuracy": 0.7},
            "analyze_accurate": {"latency": 2.0, "accuracy": 0.95},
            "analyze_balanced": {"latency": 1.0, "accuracy": 0.85}
        }
        
        # Task requirements
        self.test_requirements = {
            "max_latency": 1.5,
            "min_accuracy": 0.8
        }
        
    def tearDown(self):
        """Tear down test fixtures after test completion."""
        self.patcher.stop()
        super().tearDown()
        
    def create_test_state_with_kfm_action(self, kfm_action, reflection_text=None):
        """Create a test state with the specified KFM action.
        
        Args:
            kfm_action: KFM action to include in the state
            reflection_text: Optional reflection text to use for the mock
            
        Returns:
            A state dictionary suitable for testing reflection
        """
        # Set up the mock LLM if a reflection text is provided
        if reflection_text:
            self.mock_llm_client.return_value = reflection_text
        
        # Create a complete test state with everything needed for reflection
        test_state = {
            "input": self.standard_input,
            "task_name": self.task_name,
            "performance_data": self.test_performance_data,
            "task_requirements": self.test_requirements,
            "kfm_action": kfm_action,
            "active_component": kfm_action.get("component") if kfm_action else "analyze_balanced",
            "result": {
                "word_count": 4,
                "type": "balanced_analysis",
                "summary": "Balanced analysis complete"
            },
            "execution_performance": {
                "latency": 0.0000001,
                "accuracy": 0.85
            },
            "error": None,
            "done": True
        }
        
        return test_state
        
    def execute_standard_workflow(self, mock_reflection_text=None):
        """Execute the workflow with standard inputs and a specified reflection.
        
        Args:
            mock_reflection_text: Optional custom reflection text
        
        Returns:
            Final state after execution
        """
        # Use provided reflection or default
        reflection_text = mock_reflection_text or self.mock_reflection_text
        
        # Set up mock LLM to return the configured reflection
        self.mock_llm_client.return_value = reflection_text
        
        # Create a KFM action to inject
        kfm_action = {
            "action": "keep",
            "component": "analyze_balanced",
            "reason": "Good performance balance"
        }
        
        # Create a test state with our action
        test_state = self.create_test_state_with_kfm_action(kfm_action, reflection_text)
        
        # Apply the reflection node directly to get the reflection results
        reflection_state = src.langgraph_nodes.reflection_node(test_state)
        test_state.update(reflection_state)
        
        return test_state
        
    def test_reflection_node_integration(self):
        """Test that reflection node is properly integrated in the compiled graph."""
        # Execute standard workflow
        final_state = self.execute_standard_workflow()
        
        # Verify reflection field is present in final state
        self.assertIn('reflection', final_state, "Reflection field should be present in final state")
        self.assertEqual(final_state['reflection'], self.mock_reflection_text)
        
    def test_reflection_insights_extraction(self):
        """Test that reflection insights are properly extracted in the compiled graph."""
        # Execute standard workflow
        final_state = self.execute_standard_workflow()
        
        # Verify reflection insights are present
        self.assertIn('reflection_insights', final_state, "Reflection insights should be present in final state")
        insights = final_state['reflection_insights']
        
        # Verify structure of insights
        self.assertIn('summary', insights, "Insights should have a summary field")
        self.assertIn('strengths', insights, "Insights should have a strengths field")
        self.assertIn('improvements', insights, "Insights should have an improvements field")
        self.assertIn('recommendation', insights, "Insights should have a recommendation field")
        
    def test_reflection_analysis(self):
        """Test that reflection analysis is properly added to the state."""
        # Execute standard workflow
        final_state = self.execute_standard_workflow()
        
        # Verify reflection analysis is present
        self.assertIn('reflection_analysis', final_state, "Reflection analysis should be present in state")
        analysis = final_state['reflection_analysis']
        
        # Check analysis structure
        self.assertIn('decision_appropriate', analysis, "Analysis should have decision_appropriate field")
        self.assertIn('execution_effective', analysis, "Analysis should have execution_effective field")
        self.assertIn('confidence', analysis, "Analysis should have confidence field")
        
    def test_reflection_validation(self):
        """Test that reflection validation results are properly added to the state."""
        # Execute standard workflow
        final_state = self.execute_standard_workflow()
        
        # Verify validation results are present
        self.assertIn('validation_results', final_state, "Validation results should be present in state")
        validation = final_state['validation_results']
        
        # Check validation structure
        self.assertIn('valid', validation, "Validation should have valid field")
        self.assertTrue(validation['valid'], "Validation should be successful")
        
    def test_different_kfm_actions(self):
        """Test reflection with different KFM actions (keep, kill, marry)."""
        # Define test cases for different actions
        actions = [
            {
                "action": "keep",
                "component": "analyze_balanced",
                "reason": "Good performance",
                "expected_text": "The keep decision for component 'analyze_balanced' was appropriate given Good performance"
            },
            {
                "action": "kill",
                "component": "analyze_fast",
                "reason": "Poor accuracy",
                "expected_text": "The kill decision for component 'analyze_fast' was appropriate given Poor accuracy"
            },
            {
                "action": "marry",
                "component": "analyze_accurate",
                "reason": "Excellent accuracy",
                "expected_text": "The marry decision for component 'analyze_accurate' was appropriate given Excellent accuracy"
            }
        ]
        
        # Test each action case
        for action_case in actions:
            with self.subTest(action=action_case["action"]):
                # Create custom reflection text for this action
                reflection_text = f"""# Reflection on {action_case['action'].capitalize()} Decision for Component '{action_case['component']}'

## Decision Analysis
The {action_case['action']} decision for component '{action_case['component']}' was appropriate given {action_case['reason']}.

## Execution Assessment
The execution using component '{action_case['component']}' met the requirements.
- Details on execution and performance metrics
"""
                
                # Create a KFM action to inject
                kfm_action = {
                    "action": action_case["action"],
                    "component": action_case["component"],
                    "reason": action_case["reason"]
                }
                
                # Create test state with action and apply reflection node
                test_state = self.create_test_state_with_kfm_action(kfm_action, reflection_text)
                reflection_state = src.langgraph_nodes.reflection_node(test_state)
                test_state.update(reflection_state)
                
                # Verify the state has the KFM action and reflection data
                self.assertIsNotNone(test_state['kfm_action'])
                self.assertEqual(test_state['kfm_action']['action'], action_case['action'])
                self.assertIn('reflection', test_state)
                
                # Verify reflection contains expected text for this action
                self.assertIn(action_case['expected_text'], test_state['reflection'])
                
    def test_multiple_reflections_accumulation(self):
        """Test that multiple reflections accumulate in the reflections array."""
        # Define two different reflections
        first_reflection = """# First Reflection
        
## Analysis
This is the first reflection in the sequence.

## Assessment
The first evaluation shows good results.
"""

        second_reflection = """# Second Reflection
        
## Analysis
This is the second reflection in the sequence.

## Assessment
The second evaluation shows improved results over the first.
"""

        # First run with keep action
        first_action = {
            "action": "keep",
            "component": "analyze_balanced",
            "reason": "Good performance balance"
        }
        
        # Create first state and apply reflection
        self.mock_llm_client.return_value = first_reflection
        first_state = self.create_test_state_with_kfm_action(first_action)
        first_reflection_state = src.langgraph_nodes.reflection_node(first_state)
        first_state.update(first_reflection_state)
        
        # Verify first reflection state
        self.assertIn('reflections', first_state, "Reflections should be present in first run")
        self.assertEqual(len(first_state['reflections']), 1, "Should have one reflection in first run")
        self.assertEqual(first_state['reflection'], first_reflection)
        
        # Save reflections from first run
        first_reflections = first_state.get('reflections', [])
        
        # Second run with marry action and existing reflections
        second_action = {
            "action": "marry",
            "component": "analyze_accurate",
            "reason": "Excellent accuracy on second run"
        }
        
        # Create second state with accumulated reflections
        self.mock_llm_client.return_value = second_reflection
        second_state = self.create_test_state_with_kfm_action(second_action)
        second_state['reflections'] = first_reflections.copy()
        
        # Apply reflection to second state
        second_reflection_state = src.langgraph_nodes.reflection_node(second_state)
        second_state.update(second_reflection_state)
        
        # Verify both reflections are present
        self.assertIn('reflection', second_state)
        self.assertIn('reflections', second_state)
        self.assertEqual(second_state['reflection'], second_reflection)
        self.assertEqual(len(second_state['reflections']), 2, "Should have two reflections after second run")
        
    def test_reflection_with_invalid_action(self):
        """Test reflection behavior with an invalid KFM action."""
        # Create invalid KFM action
        invalid_action = {
            "action": "invalidaction",  # Invalid action type
            "component": "analyze_balanced",
            "reason": "Testing invalid action"
        }
        
        # Create test state with invalid action
        test_state = self.create_test_state_with_kfm_action(invalid_action)
        
        # Apply reflection node to test state
        reflection_state = src.langgraph_nodes.reflection_node(test_state)
        test_state.update(reflection_state)
        
        # Verify validation results
        self.assertIn('validation_results', test_state, "Validation results should be present")
        validation = test_state['validation_results']
        
        # Check validation structure for invalid action
        self.assertIn('valid_action_type', validation, "Should validate action type")
        self.assertFalse(validation['valid_action_type'], "Should report invalid action type")
        
        # Verify error is present in state
        self.assertIn('error', test_state, "Error should be present for invalid action")


if __name__ == '__main__':
    unittest.main() 