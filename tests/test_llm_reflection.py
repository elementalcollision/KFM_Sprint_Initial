import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.langgraph_nodes import call_llm_for_reflection


class TestLLMReflection(unittest.TestCase):
    """Test cases for the call_llm_for_reflection function."""
    
    @patch('src.langgraph_nodes.reflect_logger')
    def test_reflection_prompt_formatting(self, mock_logger):
        """Test that the reflection prompt is properly formatted with state data."""
        # Create a test state with KFM action and execution data
        state = {
            'kfm_action': {'action': 'marry', 'component': 'analyze_deep'},
            'active_component': 'analyze_deep',
            'result': {'analysis': 'Sample result'},
            'execution_performance': {'latency': 1.5, 'accuracy': 0.95},
            'error': None
        }
        
        # Call the function
        reflection = call_llm_for_reflection(state)
        
        # Verify logger was called to log the prompt
        mock_logger.debug.assert_called_once()
        prompt_log = mock_logger.debug.call_args[0][0]
        
        # Verify the prompt contains all the required state information
        self.assertIn("Decision: {'action': 'marry', 'component': 'analyze_deep'}", prompt_log)
        self.assertIn("Active Component: analyze_deep", prompt_log)
        self.assertIn("Results: {'analysis': 'Sample result'}", prompt_log)
        self.assertIn("Performance: {'latency': 1.5, 'accuracy': 0.95}", prompt_log)
    
    def test_mock_response_generation(self):
        """Test that the function returns a properly formatted mock response."""
        # Create a test state
        state = {
            'kfm_action': {'action': 'kill', 'component': 'analyze_fast'},
            'active_component': 'analyze_deep',
            'result': {'analysis': 'Detailed analysis'},
            'execution_performance': {'latency': 2.5, 'accuracy': 0.98},
            'error': None
        }
        
        # Call the function
        reflection = call_llm_for_reflection(state)
        
        # Verify the response includes the KFM action information
        self.assertIn("Mock reflection on 'kill' decision for component 'analyze_fast'", reflection)
        
        # Verify the response includes execution information
        self.assertIn("execution was successful using component 'analyze_deep'", reflection.lower())
        
        # Verify the response includes performance metrics
        self.assertIn("latency of 2.5s", reflection)
        self.assertIn("accuracy of 0.98", reflection)
    
    def test_handles_missing_values(self):
        """Test that the function handles missing or incomplete state data gracefully."""
        # Create a state with minimal information
        state = {
            'kfm_action': {'action': 'marry'},  # Missing component
            # Missing active_component
            # Missing result
            'execution_performance': {},  # Empty performance data
            'error': None
        }
        
        # Call the function - should not raise exceptions
        reflection = call_llm_for_reflection(state)
        
        # Verify response contains fallback values
        self.assertIn("component 'unknown'", reflection)
        self.assertIn("latency of N/A", reflection)
        self.assertIn("accuracy of N/A", reflection)


if __name__ == '__main__':
    unittest.main() 