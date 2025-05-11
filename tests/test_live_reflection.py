import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.langgraph_nodes import get_reflection_prompt, call_llm_for_reflection
from src.state_types import KFMAgentState


class TestLiveReflection(unittest.TestCase):
    """Test cases for the live reflection implementation."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a mock state for testing
        self.test_state = {
            'kfm_action': {
                'action': 'keep',
                'component': 'test_component',
                'reason': 'Good performance metrics'
            },
            'active_component': 'test_component',
            'result': {'status': 'success', 'data': 'test data'},
            'execution_performance': {'latency': 0.5, 'accuracy': 0.95}
        }
        
        # Mock response from Generative AI API
        self.mock_response_text = """# Reflection on Keep Decision for Component 'test_component'

## Decision Analysis
The KEEP decision for component 'test_component' was appropriate given the good performance metrics.

## Execution Assessment
The execution using component 'test_component' was effective and efficient.
- Latency: 0.5
- Accuracy: 0.95

## Strengths
- Maintained system stability
- Preserved existing functionality
- Good performance metrics

## Areas for Improvement
- Consider monitoring for edge cases
- Potential optimizations for latency

## Patterns and Insights
This keep decision indicates a conservative approach which balances performance and stability.

## Recommendation
Continue monitoring this component while exploring minor optimizations.
"""

    def test_reflection_prompt_format(self):
        """Test that the reflection prompt contains all required sections and placeholders."""
        # Get the prompt
        prompt = get_reflection_prompt(self.test_state)
        
        # Verify required sections are present
        self.assertIn("# KFM Agent Reflection Analysis", prompt)
        self.assertIn("## Context", prompt)
        self.assertIn("## Decision Details", prompt)
        self.assertIn("## Reflection Questions", prompt)
        self.assertIn("## Output Format Requirements", prompt)
        self.assertIn("## Guidelines", prompt)
        
        # Verify state information is included
        self.assertIn("KFM Action: KEEP", prompt)
        self.assertIn("Component: 'test_component'", prompt)
        self.assertIn("Reason Given: \"Good performance metrics\"", prompt)
        self.assertIn("Active Component Used: 'test_component'", prompt)
        self.assertIn("Latency: 0.5", prompt)
        self.assertIn("Accuracy: 0.95", prompt)
        
        # Verify output format template is provided
        self.assertIn("# Reflection on Keep Decision for Component 'test_component'", prompt)
        self.assertIn("[Your analysis of whether the decision was appropriate]", prompt)
        self.assertIn("[Your assessment of the execution effectiveness]", prompt)
        
        # Verify guidelines are provided
        self.assertIn("Be specific and objective in your analysis", prompt)
        self.assertIn("Keep your total response under 500 words", prompt)

    def test_call_llm_for_reflection_import_error(self):
        """Test handling of import errors for Google Generative AI SDK."""
        # Only register the patch inside the test
        with patch('src.langgraph_nodes.generate_error_reflection') as mock_generate_error, \
             patch('builtins.__import__', side_effect=ImportError("No module named 'google.generativeai'")):
            
            # Configure mock to return a test error message
            mock_generate_error.return_value = "[LLM REFLECTION ERROR] Mock error response"
            
            # Call the function
            result = call_llm_for_reflection(self.test_state)
            
            # Verify error handling occurred
            mock_generate_error.assert_called_once()
            args, _ = mock_generate_error.call_args
            self.assertEqual(args[0], self.test_state)
            self.assertIn("Error setting up reflection", args[1])
            self.assertEqual(result, "[LLM REFLECTION ERROR] Mock error response")


if __name__ == '__main__':
    unittest.main() 