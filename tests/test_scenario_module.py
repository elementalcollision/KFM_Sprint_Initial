import sys
import os
import pytest
import tempfile
from typing import Dict, Any, List

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.test_scenarios import (
    TestScenario,
    ScenarioMetadata,
    registry,
    get_scenario,
    get_all_scenarios,
    get_scenarios_by_tag
)
from src.scenario_utils import (
    create_pytest_parameters,
    filter_scenarios,
    create_scenario_variations,
    merge_scenario_states,
    load_scenarios_from_directory,
    register_custom_scenarios
)
from src.core.state import KFMAgentState


class TestScenarioModule:
    """Tests for the test_scenarios module."""
    
    def test_scenario_registry(self):
        """Test that the scenario registry is properly initialized."""
        # The registry should have multiple categories
        categories = registry.list_categories()
        assert len(categories) >= 3, "Should have at least 3 categories"
        assert "kfm" in categories, "Should have 'kfm' category"
        assert "errors" in categories, "Should have 'errors' category"
        assert "complex" in categories, "Should have 'complex' category"
        
        # Each category should have scenarios
        kfm_scenarios = get_all_scenarios("kfm")
        assert len(kfm_scenarios) >= 3, "Should have at least 3 KFM scenarios"
        
        error_scenarios = get_all_scenarios("errors")
        assert len(error_scenarios) >= 3, "Should have at least 3 error scenarios"
        
        complex_scenarios = get_all_scenarios("complex")
        assert len(complex_scenarios) >= 2, "Should have at least 2 complex scenarios"
    
    def test_get_specific_scenario(self):
        """Test retrieving a specific scenario."""
        # Get a known scenario
        happy_path = get_scenario("kfm", "happy_path")
        assert happy_path is not None, "Should find the happy path scenario"
        assert happy_path.metadata.name == "happy_path"
        assert "keep" in happy_path.metadata.tags
        
        # Try a non-existent scenario
        non_existent = get_scenario("kfm", "non_existent")
        assert non_existent is None, "Should return None for non-existent scenario"
    
    def test_filter_by_tag(self):
        """Test filtering scenarios by tag."""
        # Get scenarios with the 'error' tag
        error_scenarios = get_scenarios_by_tag("error")
        assert len(error_scenarios) >= 2, "Should find at least 2 scenarios with error tag"
        assert all("error" in s.metadata.tags for s in error_scenarios)
        
        # Get scenarios with the 'success' tag
        success_scenarios = get_scenarios_by_tag("success")
        assert len(success_scenarios) >= 3, "Should find at least 3 scenarios with success tag"
        assert all("success" in s.metadata.tags for s in success_scenarios)
    
    def test_custom_filtering(self):
        """Test custom filtering function."""
        # Define a custom filter: scenarios with execution_result field
        def has_execution_result(scenario):
            return "execution_result" in scenario.initial_state
        
        # Apply the filter
        with_results = filter_scenarios(get_all_scenarios(), has_execution_result)
        assert len(with_results) >= 4, "Should find at least 4 scenarios with execution results"
        assert all("execution_result" in s.initial_state for s in with_results)
    
    def test_create_and_save_scenario(self):
        """Test creating a custom scenario and saving it to a file."""
        # Create a simple test scenario
        metadata = ScenarioMetadata(
            name="test_scenario",
            description="Test scenario created in unit test",
            expected_sequence=["step1", "step2"],
            tags=["test", "unit-test"]
        )
        
        initial_state = {
            "input_data": {"text": "Test input"},
            "task_name": "test_task"
        }
        
        scenario = TestScenario(initial_state, metadata)
        
        # Save to a temporary file
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "test_scenario.json")
            scenario.save_to_file(file_path)
            
            # Verify the file exists
            assert os.path.exists(file_path), "File should be created"
            
            # Load the scenario back
            loaded_scenario = TestScenario.load_from_file(file_path)
            assert loaded_scenario.metadata.name == "test_scenario"
            assert loaded_scenario.metadata.description == "Test scenario created in unit test"
            assert loaded_scenario.initial_state["task_name"] == "test_task"
    
    def test_convert_to_state_object(self):
        """Test converting a scenario to a KFMAgentState object."""
        # Get a scenario
        scenario = get_scenario("kfm", "happy_path")
        
        # Convert to a state object
        state = KFMAgentState(scenario.initial_state)
        
        # Verify key fields were transferred correctly
        assert state.task_name == scenario.initial_state["task_name"]
        assert "component_a" in state.performance
        assert state.kfm_decision["action"] == "keep"
    
    def test_create_variations(self):
        """Test creating variations of a scenario."""
        # Get base scenario
        base_scenario = get_scenario("kfm", "happy_path")
        
        # Define variations
        variations = [
            {"task_name": "variation1"},
            {"task_name": "variation2"}
        ]
        
        # Create variations
        variant_scenarios = create_scenario_variations(
            base_scenario, 
            variations,
            name_template="test_variation_{variation_index}"
        )
        
        # Verify the variations
        assert len(variant_scenarios) == 2
        assert variant_scenarios[0].initial_state["task_name"] == "variation1"
        assert variant_scenarios[1].initial_state["task_name"] == "variation2"
        assert variant_scenarios[0].metadata.name == "test_variation_1"
        assert variant_scenarios[1].metadata.name == "test_variation_2"
    
    def test_merge_scenario_states(self):
        """Test merging scenario states."""
        # Define base and override states
        base_state = {
            "task_name": "base_task",
            "nested": {
                "field1": "value1",
                "field2": "value2"
            },
            "list_field": [1, 2, 3]
        }
        
        override_state = {
            "task_name": "override_task",
            "nested": {
                "field1": "new_value1",
                "field3": "value3"
            },
            "new_field": "new_value"
        }
        
        # Merge the states
        merged = merge_scenario_states(base_state, override_state)
        
        # Verify the merged state
        assert merged["task_name"] == "override_task"
        assert merged["nested"]["field1"] == "new_value1"
        assert merged["nested"]["field2"] == "value2"
        assert merged["nested"]["field3"] == "value3"
        assert merged["list_field"] == [1, 2, 3]
        assert merged["new_field"] == "new_value"
    
    def test_create_pytest_parameters(self):
        """Test converting scenarios to pytest parameters."""
        # Get some scenarios
        scenarios = get_all_scenarios("errors")
        
        # Convert to pytest parameters
        params = create_pytest_parameters(scenarios)
        
        # Verify the parameters
        assert len(params) == len(scenarios)
        for i, param in enumerate(params):
            assert "scenario_name" in param
            assert "initial_state" in param
            assert "expected_sequence" in param
            assert "expected_error" in param
            assert param["scenario_name"] == scenarios[i].metadata.name


if __name__ == "__main__":
    pytest.main(["-xvs", __file__]) 