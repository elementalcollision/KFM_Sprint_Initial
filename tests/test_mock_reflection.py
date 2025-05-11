import sys
import os
import unittest
from unittest.mock import patch

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.state_types import KFMAgentState
from src.langgraph_nodes import call_llm_for_reflection, generate_mock_reflection


class TestMockReflection(unittest.TestCase):
    """Test cases for the mock call_llm_for_reflection implementation."""
    
    def test_call_llm_for_reflection_returns_string(self):
        """Test that call_llm_for_reflection returns a string."""
        # Create a basic state
        state: KFMAgentState = {
            'kfm_action': {
                'action': 'keep', 
                'component': 'component_a'
            },
            'active_component': 'component_a',
            'result': {'status': 'success'},
            'execution_performance': {'latency': 0.5, 'accuracy': 0.95}
        }
        
        # Call the function
        result = call_llm_for_reflection(state)
        
        # Check that result is a string and not empty
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)
    
    def test_call_llm_for_reflection_with_keep_action(self):
        """Test that a 'keep' action generates an appropriate reflection."""
        # Create a state with 'keep' action
        state: KFMAgentState = {
            'kfm_action': {
                'action': 'keep', 
                'component': 'database_service'
            },
            'active_component': 'database_service',
            'result': {'status': 'success'},
            'execution_performance': {'latency': 0.5, 'accuracy': 0.95}
        }
        
        # Call the function
        result = call_llm_for_reflection(state)
        
        # Check for 'keep' specific content
        self.assertIn("Keep Decision", result)
        self.assertIn("database_service", result)
        self.assertIn("stability", result)  # 'keep' actions should mention stability
    
    def test_call_llm_for_reflection_with_kill_action(self):
        """Test that a 'kill' action generates an appropriate reflection."""
        # Create a state with 'kill' action
        state: KFMAgentState = {
            'kfm_action': {
                'action': 'kill', 
                'component': 'legacy_service'
            },
            'active_component': 'replacement_service',
            'result': {'status': 'success'},
            'execution_performance': {'latency': 0.3, 'accuracy': 0.98}
        }
        
        # Call the function
        result = call_llm_for_reflection(state)
        
        # Check for 'kill' specific content
        self.assertIn("Kill Decision", result)
        self.assertIn("legacy_service", result)
        self.assertIn("bottleneck", result)  # 'kill' actions should mention removal benefits
    
    def test_call_llm_for_reflection_with_marry_action(self):
        """Test that a 'marry' action generates an appropriate reflection."""
        # Create a state with 'marry' action
        state: KFMAgentState = {
            'kfm_action': {
                'action': 'marry', 
                'component': 'api_service'
            },
            'active_component': 'enhanced_api',
            'result': {'status': 'success'},
            'execution_performance': {'latency': 0.7, 'accuracy': 0.99}
        }
        
        # Call the function
        result = call_llm_for_reflection(state)
        
        # Check for 'marry' specific content
        self.assertIn("Marry Decision", result)
        self.assertIn("api_service", result)
        self.assertIn("integration", result)  # 'marry' actions should mention integration
    
    def test_call_llm_for_reflection_with_unknown_action(self):
        """Test that an unknown action type is handled gracefully."""
        # Create a state with an unknown action
        state: KFMAgentState = {
            'kfm_action': {
                'action': 'unknown_action', 
                'component': 'test_service'
            },
            'active_component': 'test_service',
            'result': {'status': 'success'},
            'execution_performance': {'latency': 0.5, 'accuracy': 0.9}
        }
        
        # Call the function
        result = call_llm_for_reflection(state)
        
        # Check for unknown action handling
        self.assertIn("Unknown_action Decision", result)
        self.assertIn("test_service", result)
        self.assertIn("non-standard", result)  # Unknown actions should mention they're non-standard
    
    def test_call_llm_for_reflection_with_missing_data(self):
        """Test that the function handles missing data gracefully."""
        # Create a state with minimal data
        state: KFMAgentState = {
            'kfm_action': {
                'action': 'keep'
                # Missing 'component' field
            }
            # Missing other fields
        }
        
        # Call the function
        result = call_llm_for_reflection(state)
        
        # Check that we got a valid response despite missing data
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)
        self.assertIn("Keep Decision", result)
        self.assertIn("unknown", result)  # Missing component should be replaced with 'unknown'
    
    def test_call_llm_for_reflection_with_invalid_state(self):
        """Test that the function handles an invalid state object."""
        # Create an invalid state (not a dictionary)
        state: KFMAgentState = None
        
        # Call the function and expect an error response
        result = call_llm_for_reflection(state)
        
        # Check that we got an error response
        self.assertIn("[LLM REFLECTION ERROR]", result)
        self.assertIn("error", result.lower())
    
    def test_generate_mock_reflection_directly(self):
        """Test the generate_mock_reflection function directly."""
        # Call the function with test data
        result = generate_mock_reflection(
            action_type="keep",
            component="test_component",
            active_component="current_component",
            latency=0.5,
            accuracy=0.95
        )
        
        # Check the structure and content of the result
        self.assertIn("# Reflection on Keep Decision", result)
        self.assertIn("test_component", result)
        self.assertIn("current_component", result)
        self.assertIn("Latency: 0.5", result)
        self.assertIn("Accuracy: 0.95", result)
        self.assertIn("## Strengths", result)
        self.assertIn("## Areas for Improvement", result)
        self.assertIn("## Patterns and Insights", result)
        self.assertIn("## Recommendation", result)


if __name__ == '__main__':
    unittest.main() 