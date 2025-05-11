"""
Scenario Utilities

This module provides utility functions for working with test scenarios
in various testing contexts, including loading from files, managing collections
of scenarios, and transforming scenarios for different test frameworks.
"""

import os
import json
from typing import Dict, Any, List, Optional, Union, Callable
import copy

# Import main scenario module
from src.test_scenarios import TestScenario, registry, ScenarioMetadata

# Local type for scenario collection
ScenarioCollection = Dict[str, Dict[str, TestScenario]]


def load_scenarios_from_directory(directory: str) -> ScenarioCollection:
    """
    Load all scenario JSON files from a directory into a collection.
    
    Args:
        directory: Directory containing JSON scenario files
        
    Returns:
        Dictionary mapping category -> name -> TestScenario
    """
    result: ScenarioCollection = {}
    
    if not os.path.exists(directory):
        return result
    
    for filename in os.listdir(directory):
        if not filename.endswith('.json'):
            continue
            
        file_path = os.path.join(directory, filename)
        try:
            scenario = TestScenario.load_from_file(file_path)
            
            # Extract category from filename or default to "custom"
            parts = filename.split('_')
            if len(parts) > 1:
                category = parts[0]
            else:
                category = "custom"
                
            if category not in result:
                result[category] = {}
                
            result[category][scenario.metadata.name] = scenario
        except Exception as e:
            print(f"Error loading scenario from {file_path}: {str(e)}")
    
    return result


def register_custom_scenarios(directory: str) -> int:
    """
    Load scenario files from a directory and register them.
    
    Args:
        directory: Directory containing scenario JSON files
        
    Returns:
        Number of scenarios registered
    """
    count = 0
    scenario_collection = load_scenarios_from_directory(directory)
    
    for category, scenarios in scenario_collection.items():
        for name, scenario in scenarios.items():
            registry.register(category, scenario)
            count += 1
    
    return count


def create_pytest_parameters(scenarios: List[TestScenario]) -> List[Dict[str, Any]]:
    """
    Convert scenarios to pytest parameter format.
    
    Args:
        scenarios: List of TestScenario objects
        
    Returns:
        List of dictionaries suitable for pytest.mark.parametrize
    """
    return [
        {
            "scenario_name": scenario.metadata.name,
            "initial_state": scenario.initial_state,
            "expected_sequence": scenario.metadata.expected_sequence,
            "expected_error": scenario.metadata.expected_error,
            "description": scenario.metadata.description
        }
        for scenario in scenarios
    ]


def filter_scenarios(
    scenarios: List[TestScenario],
    filter_func: Callable[[TestScenario], bool]
) -> List[TestScenario]:
    """
    Filter scenarios using a custom filtering function.
    
    Args:
        scenarios: List of TestScenario objects
        filter_func: Function that takes a TestScenario and returns True to keep it
        
    Returns:
        Filtered list of TestScenario objects
    """
    return [s for s in scenarios if filter_func(s)]


def merge_scenario_states(base_state: Dict[str, Any], 
                         override_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge two scenario states, with override_state taking precedence.
    
    Args:
        base_state: Base state dictionary
        override_state: Override state dictionary
        
    Returns:
        Merged state dictionary
    """
    result = copy.deepcopy(base_state)
    
    for key, value in override_state.items():
        if isinstance(value, dict) and key in result and isinstance(result[key], dict):
            # Recursively merge dictionaries
            result[key] = merge_scenario_states(result[key], value)
        else:
            # For other types, just override
            result[key] = copy.deepcopy(value)
    
    return result


def create_scenario_variations(
    base_scenario: TestScenario,
    variations: List[Dict[str, Any]],
    name_template: str = "{base_name}_{variation_index}"
) -> List[TestScenario]:
    """
    Create variations of a base scenario by applying different state changes.
    
    Args:
        base_scenario: Base TestScenario object
        variations: List of dictionaries with state changes to apply
        name_template: Template for naming variations (placeholders: {base_name}, {variation_index})
        
    Returns:
        List of TestScenario variations
    """
    result = []
    
    for i, variation in enumerate(variations):
        # Create a new state by merging the base state with the variation
        new_state = merge_scenario_states(base_scenario.initial_state, variation)
        
        # Create a new metadata object with an updated name
        new_name = name_template.format(
            base_name=base_scenario.metadata.name,
            variation_index=i+1
        )
        
        new_metadata = ScenarioMetadata(
            name=new_name,
            description=f"{base_scenario.metadata.description} (Variation {i+1})",
            expected_sequence=base_scenario.metadata.expected_sequence,
            expected_final_keys=base_scenario.metadata.expected_final_keys,
            unexpected_final_keys=base_scenario.metadata.unexpected_final_keys,
            expected_error=base_scenario.metadata.expected_error,
            tags=base_scenario.metadata.tags + [f"variation-{i+1}"]
        )
        
        # Create the new scenario
        new_scenario = TestScenario(new_state, new_metadata)
        result.append(new_scenario)
    
    return result 