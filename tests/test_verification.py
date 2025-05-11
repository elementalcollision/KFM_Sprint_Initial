import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.verification_utils import verify_e2e_test_results, verify_specific_test_case

class TestVerification(unittest.TestCase):
    """Test cases for the verification functions."""
    
    def test_verify_e2e_results_passing(self):
        """Test verify_e2e_test_results with a passing state."""
        # Mock a final state with all required elements
        final_state = {
            'kfm_action': {'action': 'Kill', 'component': 'analyze_fast'},
            'active_component': 'analyze_fast',
            'result': {'type': 'fast_analysis', 'summary': 'Analysis complete'},
            'reflections': ['This is a reflection on the Kill decision'],
            'execution_performance': {'latency': 0.5, 'accuracy': 0.8}
        }
        
        # Run verification
        results, all_verified = verify_e2e_test_results("Passing Test", {}, final_state)
        
        # Check verification results
        self.assertTrue(results["decision_logged"])
        self.assertTrue(results["component_registry_updated"])
        self.assertTrue(results["component_execution_logged"]) 
        self.assertTrue(results["reflection_triggered"])
        self.assertTrue(results["reflection_output_logged"])
        self.assertTrue(results["final_state_valid"])
        self.assertTrue(all_verified)
    
    def test_verify_e2e_results_failing(self):
        """Test verify_e2e_test_results with a failing state."""
        # Mock a final state missing some required elements
        final_state = {
            'kfm_action': {'action': 'Kill', 'component': 'analyze_fast'},
            'active_component': 'analyze_fast',
            # Missing result and reflections
            'error': 'Some error occurred'
        }
        
        # Run verification
        results, all_verified = verify_e2e_test_results("Failing Test", {}, final_state)
        
        # Check verification results - some should fail
        self.assertTrue(results["decision_logged"])
        self.assertTrue(results["component_registry_updated"])
        self.assertFalse(results["component_execution_logged"])
        # Reflection shouldn't be triggered due to the error, and it isn't,
        # so reflection_triggered should be True because the behavior is correct
        self.assertTrue(results["reflection_triggered"])
        self.assertFalse(results["reflection_output_logged"])
        self.assertFalse(results["final_state_valid"])  # Has error
        self.assertFalse(all_verified)  # Overall verification should fail
    
    def test_verify_e2e_results_missing_reflection(self):
        """Test verify_e2e_test_results with a state that should have reflections but doesn't."""
        # State has kfm_action and no error, but no reflections
        final_state = {
            'kfm_action': {'action': 'Kill', 'component': 'analyze_fast'},
            'active_component': 'analyze_fast',
            'result': {'type': 'fast_analysis', 'summary': 'Analysis complete'},
            # Missing reflections
            'error': None
        }
        
        # Run verification
        results, all_verified = verify_e2e_test_results("Missing Reflection Test", {}, final_state)
        
        # Reflection should be triggered but isn't, so it should fail
        self.assertFalse(results["reflection_triggered"])
        self.assertFalse(results["reflection_output_logged"])
        self.assertFalse(all_verified)  # Overall verification should fail
    
    def test_verify_specific_test_case_passing(self):
        """Test verify_specific_test_case with matching expected values."""
        # Mock a final state
        final_state = {
            'kfm_action': {'action': 'Kill', 'component': 'analyze_fast'},
            'active_component': 'analyze_fast',
            'result': {'type': 'fast_analysis', 'summary': 'Analysis complete'},
            'reflections': ['This is a reflection on the Kill decision'],
            'execution_performance': {'latency': 0.5, 'accuracy': 0.8}
        }
        
        # Define expected values that match the final state
        expected_values = {
            'expected_kfm_action': 'Kill',
            'expected_active_component': 'analyze_fast',
            'expected_result_type': 'fast_analysis',
            'expected_reflection_count': 1
        }
        
        # Run specific verification
        results, all_verified = verify_specific_test_case(
            "Specific Passing Test", {}, final_state, expected_values
        )
        
        # Check specific verification results
        self.assertTrue(results["kfm_action_correct"])
        self.assertTrue(results["active_component_correct"])
        self.assertTrue(results["result_type_correct"])
        self.assertTrue(results["reflection_count_correct"])
        self.assertTrue(all_verified)
    
    def test_verify_specific_test_case_failing(self):
        """Test verify_specific_test_case with non-matching expected values."""
        # Mock a final state
        final_state = {
            'kfm_action': {'action': 'Kill', 'component': 'analyze_fast'},
            'active_component': 'analyze_fast',
            'result': {'type': 'fast_analysis', 'summary': 'Analysis complete'},
            'reflections': ['This is a reflection on the Kill decision'],
            'execution_performance': {'latency': 0.5, 'accuracy': 0.8}
        }
        
        # Define expected values that don't match the final state
        expected_values = {
            'expected_kfm_action': 'Marry',  # Different than actual
            'expected_active_component': 'analyze_fast',
            'expected_result_type': 'fast_analysis',
            'expected_reflection_count': 2  # Different than actual
        }
        
        # Run specific verification
        results, all_verified = verify_specific_test_case(
            "Specific Failing Test", {}, final_state, expected_values
        )
        
        # Check specific verification results
        self.assertFalse(results["kfm_action_correct"])
        self.assertTrue(results["active_component_correct"])
        self.assertTrue(results["result_type_correct"])
        self.assertFalse(results["reflection_count_correct"])
        self.assertFalse(all_verified)  # Overall verification should fail
    
    def test_verify_specific_test_case_with_initial_state_fallback(self):
        """Test verify_specific_test_case using initial state when final state is missing values."""
        # Initial state with values
        initial_state = {
            'kfm_action': {'action': 'Kill', 'component': 'analyze_fast'},
            'result': {'type': 'fast_analysis'}
        }
        
        # Final state missing values (e.g., kfm_action might be cleared by decision node)
        final_state = {
            'kfm_action': None, 
            'active_component': 'analyze_fast',
            'reflections': ['This is a reflection']
        }
        
        # Expected values matching the initial state
        expected_values = {
            'expected_kfm_action': 'Kill',
            'expected_result_type': 'fast_analysis'
        }
        
        # Run verification
        results, all_verified = verify_specific_test_case(
            "Initial State Fallback Test", initial_state, final_state, expected_values
        )
        
        # We're specifically testing the initial state fallback mechanism here, 
        # so we only need to check if the specific verifications pass
        self.assertTrue(results["kfm_action_correct"], "KFM action check should pass due to fallback")
        self.assertTrue(results["result_type_correct"], "Result type check should pass due to fallback")

if __name__ == '__main__':
    unittest.main() 