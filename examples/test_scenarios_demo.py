"""
Test Scenarios Demo

This example script demonstrates how to use the test scenarios module
for testing various aspects of the KFM framework.
"""

import sys
import os
import json
from typing import Dict, Any, List

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.test_scenarios import (
    get_scenario, 
    get_all_scenarios, 
    get_scenarios_by_tag,
    registry
)
from src.scenario_utils import (
    create_pytest_parameters,
    filter_scenarios,
    create_scenario_variations
)
from src.core.state import KFMAgentState


def print_section(title: str):
    """Print a section title."""
    print("\n" + "=" * 50)
    print(f"  {title}")
    print("=" * 50)


def demo_basic_usage():
    """Demonstrate basic scenario usage."""
    print_section("Basic Scenario Usage")
    
    # Get a specific scenario
    scenario = get_scenario("kfm", "happy_path")
    print(f"Loaded scenario: {scenario.metadata.name}")
    print(f"Description: {scenario.metadata.description}")
    print(f"Expected sequence: {scenario.metadata.expected_sequence}")
    
    # Convert scenario to state object
    state = KFMAgentState(scenario.initial_state)
    print(f"\nCreated KFMAgentState: {state}")


def demo_scenario_categories():
    """Demonstrate working with scenario categories."""
    print_section("Scenario Categories")
    
    # List all categories
    categories = registry.list_categories()
    print(f"Available categories: {categories}")
    
    # Get scenarios by category
    for category in categories:
        scenarios = get_all_scenarios(category)
        print(f"\nCategory '{category}' has {len(scenarios)} scenarios:")
        for scenario in scenarios:
            print(f"  - {scenario.metadata.name}: {scenario.metadata.description}")


def demo_filtering_and_tags():
    """Demonstrate filtering scenarios and using tags."""
    print_section("Filtering and Tags")
    
    # Get scenarios by tag
    error_scenarios = get_scenarios_by_tag("error")
    print(f"Found {len(error_scenarios)} scenarios with 'error' tag:")
    for scenario in error_scenarios:
        print(f"  - {scenario.metadata.name}: {scenario.metadata.description}")
    
    # Custom filtering
    def has_execution_result(scenario):
        return "execution_result" in scenario.initial_state
    
    success_scenarios = filter_scenarios(get_all_scenarios(), has_execution_result)
    print(f"\nFound {len(success_scenarios)} scenarios with execution results:")
    for scenario in success_scenarios:
        print(f"  - {scenario.metadata.name}: {scenario.metadata.description}")


def demo_scenario_variations():
    """Demonstrate creating scenario variations."""
    print_section("Scenario Variations")
    
    # Get base scenario
    base_scenario = get_scenario("kfm", "happy_path")
    
    # Define variations
    variations = [
        {
            "performance_data": {
                "component_a": {"latency": 1.2, "accuracy": 0.91}  # Different metrics
            }
        },
        {
            "task_requirements": {
                "max_latency": 2.0,  # Different requirements
                "min_accuracy": 0.85
            }
        },
        {
            "kfm_action": {  # Different action
                "action": "marry",
                "component": "component_a",
                "reason": "Enhanced metrics"
            }
        }
    ]
    
    # Create variations
    scenario_variations = create_scenario_variations(
        base_scenario, 
        variations,
        name_template="happy_path_variation_{variation_index}"
    )
    
    print(f"Created {len(scenario_variations)} variations of '{base_scenario.metadata.name}':")
    for i, var in enumerate(scenario_variations):
        print(f"\nVariation {i+1}: {var.metadata.name}")
        
        # Show the key differences for this variation
        if i == 0:
            print(f"  Changed performance metrics:")
            print(f"    latency: {var.initial_state['performance_data']['component_a']['latency']}")
            print(f"    accuracy: {var.initial_state['performance_data']['component_a']['accuracy']}")
        elif i == 1:
            print(f"  Changed requirements:")
            print(f"    max_latency: {var.initial_state['task_requirements']['max_latency']}")
            print(f"    min_accuracy: {var.initial_state['task_requirements']['min_accuracy']}")
        elif i == 2:
            print(f"  Changed KFM action:")
            print(f"    action: {var.initial_state['kfm_action']['action']}")
            print(f"    reason: {var.initial_state['kfm_action']['reason']}")


def demo_pytest_integration():
    """Demonstrate how to use scenarios with pytest."""
    print_section("PyTest Integration")
    
    # Get all error scenarios
    error_scenarios = get_scenarios_by_tag("error")
    
    # Convert to pytest parameters
    pytest_params = create_pytest_parameters(error_scenarios)
    
    print("PyTest parameter example:")
    print(json.dumps(pytest_params[0], indent=2))
    
    # Example of how to use in a pytest test
    print("\nExample pytest test:")
    print("""
    @pytest.mark.parametrize("scenario_params", pytest_params)
    def test_error_handling(scenario_params):
        # Initialize state from scenario
        initial_state = scenario_params["initial_state"]
        state = KFMAgentState(initial_state)
        
        # Run the test
        result = run_graph_with_state(state)
        
        # Check assertions based on scenario expectations
        if scenario_params["expected_error"]:
            assert result.has_error()
    """)


def demo_saving_scenarios():
    """Demonstrate saving scenarios to files."""
    print_section("Saving Scenarios")
    
    # Create example directory
    example_dir = os.path.join(project_root, "examples", "test_states")
    os.makedirs(example_dir, exist_ok=True)
    
    # Get a complex scenario
    scenario = get_scenario("complex", "multi_component")
    
    # Save to file
    file_path = os.path.join(example_dir, "complex_test_state.json")
    scenario.save_to_file(file_path)
    
    print(f"Saved scenario '{scenario.metadata.name}' to:")
    print(f"  {file_path}")
    
    # Verify
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    print(f"\nVerified file contains {len(data)} fields including:")
    for key in list(data.keys())[:5]:  # Show first 5 keys
        print(f"  - {key}")


def run_all_demos():
    """Run all demos."""
    demo_basic_usage()
    demo_scenario_categories()
    demo_filtering_and_tags()
    demo_scenario_variations()
    demo_pytest_integration()
    demo_saving_scenarios()


if __name__ == "__main__":
    run_all_demos() 