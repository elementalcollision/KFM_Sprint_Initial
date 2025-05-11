import sys
import os
import unittest
from unittest.mock import patch, MagicMock
from typing import Dict, Any

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.state_types import KFMAgentState
from src.langgraph_nodes import reflection_node


class TestE2EReflection(unittest.TestCase):
    """Test cases for the reflection node functionality."""
    
    def test_reflection_validation_valid_decision(self):
        """Test the reflection node with a valid decision."""
        state = {
            "kfm_action": {"action": "keep", "component": "component_a", "reason": "Good performance"},
            "active_component": "component_a",
            "execution_performance": {"latency": 0.5, "accuracy": 0.95}
        }
        
        with patch('src.langgraph_nodes.call_llm_for_reflection') as mock_llm_call:
            mock_llm_call.return_value = "The keep decision was appropriate given the good performance."
            
            result = reflection_node(state)
            
            # Verify validation results
            self.assertIn('validation_results', result)
            self.assertTrue(result['validation_results']['valid'])
            
            # Verify reflection added
            self.assertIn('reflections', result)
            self.assertIn('reflection', result)
            self.assertEqual(result['reflection'], 
                            "The keep decision was appropriate given the good performance.")
    
    def test_reflection_validation_invalid_action(self):
        """Test the reflection node with an invalid action type."""
        state = {
            "kfm_action": {"action": "invalid_action", "component": "component_a"},
            "active_component": "component_a"
        }
        
        result = reflection_node(state)
        
        # Verify validation failed
        self.assertIn('validation_results', result)
        self.assertFalse(result['validation_results'].get('valid_action_type', True))
        self.assertIn('message', result['validation_results'])
        self.assertIn('Invalid action type', result['validation_results']['message'])
        
        # Verify error set
        self.assertIn('error', result)
        
        # Verify no reflection added
        self.assertIn('reflections', result)
        self.assertEqual(len(result['reflections']), 0)
    
    def test_reflection_validation_missing_decision(self):
        """Test the reflection node with a missing KFM decision."""
        state = {
            "active_component": "component_a"
        }
        
        result = reflection_node(state)
        
        # Verify validation failed
        self.assertIn('validation_results', result)
        self.assertFalse(result['validation_results'].get('kfm_decision_exists', True))
        
        # Verify no error set (this is an expected condition)
        self.assertNotIn('error', result)
        
        # Verify no reflection added
        self.assertIn('reflections', result)
        self.assertEqual(len(result['reflections']), 0)
    
    def test_reflection_with_llm_error(self):
        """Test the reflection node handling of LLM errors."""
        state = {
            "kfm_action": {"action": "keep", "component": "component_a", "reason": "Good performance"},
            "active_component": "component_a",
            "execution_performance": {"latency": 0.5, "accuracy": 0.95}
        }
        
        with patch('src.langgraph_nodes.call_llm_for_reflection') as mock_llm_call:
            # Simulate an LLM API error
            mock_llm_call.side_effect = Exception("LLM API error")
            
            result = reflection_node(state)
            
            # Verify validation still passes
            self.assertIn('validation_results', result)
            self.assertTrue(result['validation_results']['valid'])
            self.assertFalse(result['validation_results'].get('reflection_success', True))
            
            # Verify fallback reflection added
            self.assertIn('reflections', result)
            self.assertIn('reflection', result)
            self.assertIn('[LLM REFLECTION ERROR]', result['reflection'])
            self.assertIn('LLM API error', result['reflection'])
            
            # Verify no error propagated to state
            self.assertNotIn('error', result)
    
    def test_reflection_validation_with_existing_error(self):
        """Test reflection validation when state already has an error."""
        state = {
            "kfm_action": {"action": "keep", "component": "component_a"},
            "active_component": "component_a",
            "error": "Existing error in state"
        }
        
        result = reflection_node(state)
        
        # Verify validation failed
        self.assertIn('validation_results', result)
        self.assertFalse(result['validation_results'].get('error_check', True))
        
        # Verify error preserved
        self.assertEqual(result['error'], "Existing error in state")
        
        # Verify no reflection added
        self.assertIn('reflections', result)
        self.assertEqual(len(result['reflections']), 0)
    
    def test_reflection_with_kill_decision(self):
        """Test reflection with a kill decision."""
        state = {
            "kfm_action": {"action": "kill", "component": "component_a", "reason": "Poor performance"},
            "active_component": "component_a",
            "execution_performance": {"latency": 2.5, "accuracy": 0.6}
        }
        
        with patch('src.langgraph_nodes.call_llm_for_reflection') as mock_llm_call:
            mock_llm_call.return_value = "The kill decision was appropriate due to poor performance."
            
            result = reflection_node(state)
            
            # Verify validation passes
            self.assertIn('validation_results', result)
            self.assertTrue(result['validation_results']['valid'])
            
            # Verify reflection added
            self.assertIn('reflections', result)
            self.assertIn('reflection', result)
            self.assertEqual(result['reflection'], 
                           "The kill decision was appropriate due to poor performance.")
    
    def test_reflection_with_marry_decision(self):
        """Test reflection with a marry decision."""
        state = {
            "kfm_action": {"action": "marry", "component": "component_a", "reason": "Excellent performance"},
            "active_component": "component_a",
            "execution_performance": {"latency": 0.8, "accuracy": 0.99}
        }
        
        with patch('src.langgraph_nodes.call_llm_for_reflection') as mock_llm_call:
            mock_llm_call.return_value = "The marry decision was appropriate due to excellent performance."
            
            result = reflection_node(state)
            
            # Verify validation passes
            self.assertIn('validation_results', result)
            self.assertTrue(result['validation_results']['valid'])
            
            # Verify reflection added
            self.assertIn('reflections', result)
            self.assertIn('reflection', result)
            self.assertEqual(result['reflection'], 
                           "The marry decision was appropriate due to excellent performance.")


if __name__ == '__main__':
    unittest.main() 