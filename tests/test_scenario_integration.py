import sys
import os
import pytest
from typing import Dict, Any, List

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.test_scenarios import (
    get_scenario,
    get_all_scenarios,
    get_scenarios_by_tag
)
from src.scenario_utils import create_pytest_parameters
from src.core.state import KFMAgentState
from src.core.validation import validate_performance_metrics


def test_happy_path_scenario_state():
    """Test that the happy path scenario creates a valid state object."""
    # Get the happy path scenario
    scenario = get_scenario("kfm", "happy_path")
    
    # Convert to state object
    state = KFMAgentState(scenario.initial_state)
    
    # Verify the state was created correctly with all expected fields
    assert state.task_name == "happy_path_task", "Task name should match"
    assert "component_a" in state.performance, "Performance data should be available"
    assert state.kfm_decision is not None, "KFM decision should be set"
    assert state.kfm_decision["action"] == "keep", "Action should be 'keep'"
    assert state.kfm_decision["component"] == "component_a", "Component should be 'component_a'"
    
    # Validate performance metrics
    assert state.task_requirements["min_accuracy"] == 0.9, "Accuracy requirement should be 0.9"
    assert state.task_requirements["max_latency"] == 1.0, "Latency requirement should be 1.0"
    assert state.performance["component_a"]["accuracy"] == 0.95, "Component A accuracy should be 0.95"
    assert state.performance["component_a"]["latency"] == 0.5, "Component A latency should be 0.5"
    
    # Check that the performance metrics meet the requirements
    performance_valid = validate_performance_metrics(
        state.performance, 
        state.task_requirements
    )
    assert performance_valid, "Performance metrics should be valid for the task requirements"


def test_kill_action_scenario_state():
    """Test that the kill action scenario creates a valid state object."""
    # Get the kill action scenario
    scenario = get_scenario("kfm", "kill_action")
    
    # Convert to state object
    state = KFMAgentState(scenario.initial_state)
    
    # Verify the state was created correctly
    assert state.task_name == "kill_action_task", "Task name should match"
    assert "component_a" in state.performance, "Performance data should be available"
    assert state.kfm_decision is not None, "KFM decision should be set"
    assert state.kfm_decision["action"] == "kill", "Action should be 'kill'"
    assert state.kfm_decision["component"] == "component_a", "Component should be 'component_a'"
    
    # Validate performance metrics
    # component_a performance doesn't meet task requirements
    component_a_meets_requirements = (
        state.performance["component_a"]["accuracy"] >= state.task_requirements["min_accuracy"] and 
        state.performance["component_a"]["latency"] <= state.task_requirements["max_latency"]
    )
    assert not component_a_meets_requirements, "Component A performance should not meet requirements"
    
    # component_b performance does meet task requirements
    component_b_meets_requirements = (
        state.performance["component_b"]["accuracy"] >= state.task_requirements["min_accuracy"] and 
        state.performance["component_b"]["latency"] <= state.task_requirements["max_latency"]
    )
    assert component_b_meets_requirements, "Component B performance should meet requirements"


def test_complex_multi_component_scenario():
    """Test that the complex multi-component scenario creates a valid state object."""
    # Get the multi-component scenario
    scenario = get_scenario("complex", "multi_component")
    
    # Convert to state object
    state = KFMAgentState(scenario.initial_state)
    
    # Verify basic state properties
    assert state.task_name == "multi_component_task", "Task name should match"
    assert len(state.performance) == 4, "Should have 4 components in performance data"
    assert "execution_performance" in scenario.initial_state, "Should have execution performance"
    
    # Check that the cost field is present in the performance data
    assert "cost" in state.performance["component_a"], "Cost field should be present"
    assert "max_cost" in state.task_requirements, "Max cost requirement should be present"
    
    # Check that the performance metrics for the chosen component meet the requirements
    component = state.kfm_decision["component"]
    assert state.performance[component]["accuracy"] >= state.task_requirements["min_accuracy"], "Accuracy should meet requirement"
    assert state.performance[component]["latency"] <= state.task_requirements["max_latency"], "Latency should meet requirement"
    assert state.performance[component]["cost"] <= state.task_requirements["max_cost"], "Cost should meet requirement"


def test_missing_fields_scenario():
    """Test that the missing fields scenario correctly identifies missing fields."""
    # Get the missing fields scenario
    scenario = get_scenario("errors", "missing_fields")
    
    # Convert to state object
    state = KFMAgentState(scenario.initial_state)
    
    # Verify missing fields
    assert not hasattr(state, "performance_data"), "Performance data attribute should not exist"
    assert state.performance == {}, "Performance should be empty"
    assert state.task_requirements == {}, "Task requirements should be empty"
    
    # Validate the scenario has the expected error flag
    assert scenario.metadata.expected_error, "Scenario should expect an error"


def generate_scenario_test_cases():
    """Generate test cases from all scenarios with 'success' tag."""
    success_scenarios = get_scenarios_by_tag("success")
    return create_pytest_parameters(success_scenarios)


@pytest.mark.parametrize("scenario_params", generate_scenario_test_cases())
def test_all_success_scenarios(scenario_params):
    """Test all scenarios tagged with 'success'."""
    # Initialize state from scenario
    state = KFMAgentState(scenario_params["initial_state"])
    
    # Validate that the state has required KFM fields
    assert state.task_name is not None, f"Task name should be set for scenario '{scenario_params['scenario_name']}'"
    assert state.kfm_decision is not None, f"KFM decision should be set for scenario '{scenario_params['scenario_name']}'"
    
    # Verify the KFM action is what we expect
    assert state.kfm_decision["action"] in ["keep", "kill", "marry"], f"Action should be valid for scenario '{scenario_params['scenario_name']}'"
    
    # If the scenario has execution results, verify they exist in the state
    if "execution_result" in scenario_params["initial_state"]:
        assert state.results is not None, f"Results should be present for scenario '{scenario_params['scenario_name']}'"
        if "status" in scenario_params["initial_state"]["execution_result"]:
            status = scenario_params["initial_state"]["execution_result"]["status"]
            assert status == "success", f"Execution result should indicate success for scenario '{scenario_params['scenario_name']}'"


if __name__ == "__main__":
    pytest.main(["-xvs", __file__]) 