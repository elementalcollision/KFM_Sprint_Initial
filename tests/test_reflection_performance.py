import sys
import os
import unittest
import time
from unittest.mock import patch, MagicMock
import json

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Patch modules before importing
sys.modules['google'] = MagicMock()
sys.modules['google.generativeai'] = MagicMock()
sys.modules['google.api_core'] = MagicMock()
sys.modules['google.api_core.exceptions'] = MagicMock()

from src.langgraph_nodes import get_reflection_prompt
from src.state_types import KFMAgentState


class TestReflectionPerformance(unittest.TestCase):
    """Performance tests for the reflection prompt template."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a mock state with realistic test data
        self.test_state = {
            'kfm_action': {
                'action': 'keep',
                'component': 'test_component',
                'reason': 'Good performance metrics'
            },
            'active_component': 'test_component',
            'result': {'analysis': 'Test result with some meaningful content'},
            'execution_performance': {'latency': 0.5, 'accuracy': 0.95},
            'error': None
        }
        
        # Create a more complex state with verbose data
        self.complex_state = {
            'kfm_action': {
                'action': 'marry',
                'component': 'data_processor',
                'reason': 'Excellent performance metrics with high accuracy and good integration potential with other components'
            },
            'active_component': 'data_processor',
            'result': {
                'analysis': 'Detailed analysis of the component performance',
                'metrics': {
                    'throughput': 1000,
                    'error_rate': 0.01,
                    'response_distribution': [0.1, 0.2, 0.3, 0.4, 0.5]
                },
                'recommendations': [
                    'Consider enhancing with feature X',
                    'Monitor performance under high load',
                    'Add additional error handling'
                ]
            },
            'execution_performance': {
                'latency': 0.75,
                'accuracy': 0.98,
                'memory_usage': 256,
                'cpu_usage': 45.2
            },
            'error': None
        }
    
    def count_tokens(self, text):
        """Estimate token count using a simple heuristic.
        
        This is a rough approximation. For production, consider using the
        actual tokenizer from your LLM provider.
        """
        # Simple approximation: ~4 chars per token for English text
        return len(text) // 4
    
    def test_token_usage_standard_state(self):
        """Test token usage for a standard state."""
        # Generate the prompt
        prompt = get_reflection_prompt(self.test_state)
        
        # Count tokens
        token_count = self.count_tokens(prompt)
        
        # Log token usage for analysis
        print(f"\nStandard state prompt token count (estimated): {token_count}")
        
        # Verify token count is within reasonable limits
        # Most LLM context windows are at least 4K tokens, many are 8K+
        self.assertLess(token_count, 1000, "Prompt token usage should be well under 1000 tokens")
    
    def test_token_usage_complex_state(self):
        """Test token usage for a more complex state with verbose data."""
        # Generate the prompt
        prompt = get_reflection_prompt(self.complex_state)
        
        # Count tokens
        token_count = self.count_tokens(prompt)
        
        # Log token usage for analysis
        print(f"\nComplex state prompt token count (estimated): {token_count}")
        
        # Verify token count is within reasonable limits
        self.assertLess(token_count, 1500, "Even complex prompts should use less than 1500 tokens")
    
    def test_prompt_generation_time(self):
        """Test the time it takes to generate the reflection prompt."""
        # Measure time for multiple iterations to get reliable results
        iterations = 100
        start_time = time.time()
        
        for _ in range(iterations):
            get_reflection_prompt(self.test_state)
        
        total_time = time.time() - start_time
        avg_time = total_time / iterations
        
        # Log the results
        print(f"\nAverage prompt generation time ({iterations} iterations): {avg_time:.6f} seconds")
        
        # Verify generation time is fast enough - this threshold may need adjustment based on the test environment
        self.assertLess(avg_time, 0.005, "Prompt generation should be very fast (< 5ms)")


if __name__ == '__main__':
    unittest.main() 