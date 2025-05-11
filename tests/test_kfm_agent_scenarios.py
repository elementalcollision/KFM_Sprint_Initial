import sys
import os
from typing import Dict, Any

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Define test scenarios for use in integration tests

class TestKfmAgentScenarios:
    """Collection of test scenarios for testing the KFM agent graph."""
    
    @staticmethod
    def get_happy_path_scenario() -> Dict[str, Any]:
        """Get a standard successful execution scenario.
        
        Returns:
            Dictionary with scenario data
        """
        return {
            "name": "happy_path",
            "description": "Standard successful execution with 'keep' action",
            "input_data": {
                "text": "This is a sample text for processing"
            },
            "task_name": "happy_path_task",
            "performance_data": {
                "component_a": {"latency": 0.5, "accuracy": 0.95},
                "component_b": {"latency": 0.8, "accuracy": 0.85}
            },
            "task_requirements": {
                "max_latency": 1.0,
                "min_accuracy": 0.9
            },
            "kfm_action": {
                "action": "keep",
                "component": "component_a",
                "reason": "Good performance metrics"
            },
            "execution_result": {
                "status": "success", 
                "data": {"records": 10}
            },
            "execution_performance": {
                "latency": 0.5, 
                "accuracy": 0.95
            },
            "expected_sequence": ["monitor", "decide", "execute", "reflect"],
            "expected_final_keys": [
                "input", "task_name", "performance_data", "task_requirements",
                "kfm_action", "active_component", "result", "execution_performance",
                "reflection", "reflections", "reflection_insights", 
                "reflection_analysis", "validation_results"
            ]
        }
    
    @staticmethod
    def get_kill_action_scenario() -> Dict[str, Any]:
        """Get a scenario with 'kill' KFM action.
        
        Returns:
            Dictionary with scenario data
        """
        return {
            "name": "kill_action",
            "description": "Execution with 'kill' action due to poor performance",
            "input_data": {
                "text": "Kill action test input"
            },
            "task_name": "kill_action_task",
            "performance_data": {
                "component_a": {"latency": 2.5, "accuracy": 0.60},
                "component_b": {"latency": 0.9, "accuracy": 0.92}
            },
            "task_requirements": {
                "max_latency": 1.0,
                "min_accuracy": 0.9
            },
            "kfm_action": {
                "action": "kill",
                "component": "component_a",
                "reason": "Poor performance metrics"
            },
            "execution_result": {
                "status": "success", 
                "data": {"records": 5}
            },
            "execution_performance": {
                "latency": 2.5, 
                "accuracy": 0.60
            },
            "expected_sequence": ["monitor", "decide", "execute", "reflect"],
            "expected_final_keys": [
                "input", "task_name", "performance_data", "task_requirements",
                "kfm_action", "active_component", "result", "execution_performance",
                "reflection", "reflections", "reflection_insights", 
                "reflection_analysis", "validation_results"
            ]
        }
    
    @staticmethod
    def get_marry_action_scenario() -> Dict[str, Any]:
        """Get a scenario with 'marry' KFM action.
        
        Returns:
            Dictionary with scenario data
        """
        return {
            "name": "marry_action",
            "description": "Execution with 'marry' action due to excellent performance",
            "input_data": {
                "text": "Marry action test input"
            },
            "task_name": "marry_action_task",
            "performance_data": {
                "component_a": {"latency": 0.3, "accuracy": 0.98},
                "component_b": {"latency": 0.8, "accuracy": 0.90}
            },
            "task_requirements": {
                "max_latency": 1.0,
                "min_accuracy": 0.95
            },
            "kfm_action": {
                "action": "marry",
                "component": "component_a",
                "reason": "Excellent performance metrics"
            },
            "execution_result": {
                "status": "success", 
                "data": {"records": 15}
            },
            "execution_performance": {
                "latency": 0.3, 
                "accuracy": 0.98
            },
            "expected_sequence": ["monitor", "decide", "execute", "reflect"],
            "expected_final_keys": [
                "input", "task_name", "performance_data", "task_requirements",
                "kfm_action", "active_component", "result", "execution_performance",
                "reflection", "reflections", "reflection_insights", 
                "reflection_analysis", "validation_results"
            ]
        }
    
    @staticmethod
    def get_execution_error_scenario() -> Dict[str, Any]:
        """Get a scenario with an error during execution.
        
        Returns:
            Dictionary with scenario data
        """
        return {
            "name": "execution_error",
            "description": "Execution with error in the execute action node",
            "input_data": {
                "text": "Error scenario test input"
            },
            "task_name": "error_task",
            "performance_data": {
                "component_a": {"latency": 0.5, "accuracy": 0.95},
                "component_b": {"latency": 0.8, "accuracy": 0.85}
            },
            "task_requirements": {
                "max_latency": 1.0,
                "min_accuracy": 0.9
            },
            "kfm_action": {
                "action": "keep",
                "component": "component_a",
                "reason": "Good performance metrics"
            },
            "execution_error": "Test execution error",
            "expected_sequence": ["monitor", "decide", "execute", "reflect"],
            "expected_final_keys": [
                "input", "task_name", "error", "done",
                "kfm_action", "active_component", "validation_results"
            ],
            "unexpected_final_keys": [
                "reflection_insights", "reflection_analysis"
            ]
        }
    
    @staticmethod
    def get_reflection_error_scenario() -> Dict[str, Any]:
        """Get a scenario with an error during reflection but successful execution.
        
        Returns:
            Dictionary with scenario data
        """
        return {
            "name": "reflection_error",
            "description": "Successful execution but error in reflection",
            "input_data": {
                "text": "Reflection error test input"
            },
            "task_name": "reflection_error_task",
            "performance_data": {
                "component_a": {"latency": 0.5, "accuracy": 0.95},
                "component_b": {"latency": 0.8, "accuracy": 0.85}
            },
            "task_requirements": {
                "max_latency": 1.0,
                "min_accuracy": 0.9
            },
            "kfm_action": {
                "action": "keep",
                "component": "component_a",
                "reason": "Good performance metrics"
            },
            "execution_result": {
                "status": "success", 
                "data": {"records": 10}
            },
            "execution_performance": {
                "latency": 0.5, 
                "accuracy": 0.95
            },
            "reflection_error": "LLM API error",
            "expected_sequence": ["monitor", "decide", "execute", "reflect"],
            "expected_final_keys": [
                "input", "task_name", "performance_data", "task_requirements",
                "kfm_action", "active_component", "result", "execution_performance",
                "reflection", "reflections", "validation_results"
            ]
        }
    
    @staticmethod
    def get_missing_fields_scenario() -> Dict[str, Any]:
        """Get a scenario with missing fields in the state.
        
        Returns:
            Dictionary with scenario data
        """
        return {
            "name": "missing_fields",
            "description": "Missing fields in the state",
            "input_data": {
                "text": "Missing fields test input"
            },
            "task_name": "missing_fields_task",
            # No performance_data or task_requirements
            "expected_sequence": ["monitor"],  # Should stop after monitor
            "expected_error": True
        }
    
    @staticmethod
    def get_all_scenarios() -> Dict[str, Dict[str, Any]]:
        """Get all available test scenarios.
        
        Returns:
            Dictionary where keys are scenario names and values are scenario data
        """
        return {
            "happy_path": TestKfmAgentScenarios.get_happy_path_scenario(),
            "kill_action": TestKfmAgentScenarios.get_kill_action_scenario(),
            "marry_action": TestKfmAgentScenarios.get_marry_action_scenario(),
            "execution_error": TestKfmAgentScenarios.get_execution_error_scenario(),
            "reflection_error": TestKfmAgentScenarios.get_reflection_error_scenario(),
            "missing_fields": TestKfmAgentScenarios.get_missing_fields_scenario(),
        } 