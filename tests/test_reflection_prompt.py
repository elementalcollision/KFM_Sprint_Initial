import sys
import os
import unittest

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.langgraph_nodes import get_reflection_prompt


class TestReflectionPrompt(unittest.TestCase):
    """Test cases for the get_reflection_prompt function."""
    
    def test_reflection_prompt_formatting(self):
        """Test that the reflection prompt is properly formatted with all required elements."""
        # Create a test state with KFM action and execution data
        state = {
            'kfm_action': {'action': 'marry', 'component': 'analyze_deep'},
            'active_component': 'analyze_deep',
            'result': {'analysis': 'Sample result'},
            'execution_performance': {'latency': 1.5, 'accuracy': 0.95},
            'error': None
        }
        
        # Call the function
        prompt = get_reflection_prompt(state)
        
        # Verify the prompt structure
        self.assertIn("# KFM Agent Reflection", prompt)
        self.assertIn("## Context", prompt)
        self.assertIn("## Decision Details", prompt)
        self.assertIn("## Reflection Questions", prompt)
        self.assertIn("## Instructions", prompt)
        
        # Verify the prompt contains all the required state information
        self.assertIn("Decision Type: marry for component 'analyze_deep'", prompt)
        self.assertIn("Active Component Used: analyze_deep", prompt)
        self.assertIn("Performance Metrics: {'latency': 1.5, 'accuracy': 0.95}", prompt)
        self.assertIn("Execution Results: {'analysis': 'Sample result'}", prompt)
        
        # Verify the prompt contains all reflection questions
        self.assertIn("1. Was the marry decision appropriate", prompt)
        self.assertIn("2. How effective was the execution", prompt)
        self.assertIn("3. What went well", prompt)
        self.assertIn("4. What could be improved", prompt)
        self.assertIn("5. Are there any patterns or insights", prompt)
        
        # Verify instructions are present
        self.assertIn("Provide a thoughtful reflection", prompt)
    
    def test_handles_missing_values(self):
        """Test that the function handles missing or incomplete state data gracefully."""
        # Create a state with minimal information
        state = {
            'kfm_action': {'action': 'kill'},  # Missing component
            # Missing active_component
            # Missing result
            'execution_performance': {},  # Empty performance data
            'error': None
        }
        
        # Call the function - should not raise exceptions
        prompt = get_reflection_prompt(state)
        
        # Verify prompt contains fallback values
        self.assertIn("Decision Type: kill for component 'unknown'", prompt)
        self.assertIn("Active Component Used: unknown", prompt)
        self.assertIn("Performance Metrics: {}", prompt)
        self.assertIn("Execution Results: {}", prompt)
    
    def test_no_kfm_action(self):
        """Test that the function handles states with no KFM action."""
        # Create a state with no KFM action
        state = {
            # No kfm_action
            'active_component': 'analyze_deep',
            'result': {'analysis': 'Sample result'},
            'execution_performance': {'latency': 1.5, 'accuracy': 0.95},
            'error': None
        }
        
        # Call the function - should not raise exceptions
        prompt = get_reflection_prompt(state)
        
        # Verify prompt contains fallback values
        self.assertIn("Decision Type: No decision for component 'unknown'", prompt)


if __name__ == '__main__':
    unittest.main() 