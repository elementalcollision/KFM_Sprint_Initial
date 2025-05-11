"""
Test Scenarios Module

This module provides a collection of reusable test scenarios for the KFM framework.
Scenarios are organized by category and provide different test cases with predefined
state structures for various testing purposes.
"""

from typing import Dict, Any, List, Optional, Union, Callable
import os
import json
import copy


class ScenarioMetadata:
    """Metadata for a test scenario including description and expected outcomes."""
    
    def __init__(self, 
                 name: str, 
                 description: str,
                 expected_sequence: List[str] = None,
                 expected_final_keys: List[str] = None,
                 unexpected_final_keys: List[str] = None,
                 expected_error: bool = False,
                 tags: List[str] = None):
        """
        Initialize scenario metadata.
        
        Args:
            name: Unique identifier for the scenario
            description: Human-readable description of the scenario
            expected_sequence: Expected execution sequence of graph nodes
            expected_final_keys: Expected keys in final state
            unexpected_final_keys: Keys that should not be in final state
            expected_error: Whether an error is expected during execution
            tags: List of tags for categorizing scenarios
        """
        self.name = name
        self.description = description
        self.expected_sequence = expected_sequence or []
        self.expected_final_keys = expected_final_keys or []
        self.unexpected_final_keys = unexpected_final_keys or []
        self.expected_error = expected_error
        self.tags = tags or []


class TestScenario:
    """A test scenario with input state, expected outputs, and metadata."""
    
    def __init__(self, 
                 initial_state: Dict[str, Any],
                 metadata: ScenarioMetadata):
        """
        Initialize a test scenario.
        
        Args:
            initial_state: Initial state dictionary to seed the test
            metadata: Metadata object with scenario information
        """
        self.initial_state = initial_state
        self.metadata = metadata
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the scenario to a dictionary representation.
        
        Returns:
            Dictionary containing all scenario data
        """
        result = copy.deepcopy(self.initial_state)
        result.update({
            "name": self.metadata.name,
            "description": self.metadata.description,
            "expected_sequence": self.metadata.expected_sequence,
            "expected_final_keys": self.metadata.expected_final_keys
        })
        
        if self.metadata.unexpected_final_keys:
            result["unexpected_final_keys"] = self.metadata.unexpected_final_keys
            
        if self.metadata.expected_error:
            result["expected_error"] = True
            
        if self.metadata.tags:
            result["tags"] = self.metadata.tags
            
        return result
    
    def save_to_file(self, file_path: str) -> None:
        """
        Save the scenario to a JSON file.
        
        Args:
            file_path: Path to save the JSON file
        """
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load_from_file(cls, file_path: str) -> 'TestScenario':
        """
        Load a scenario from a JSON file.
        
        Args:
            file_path: Path to the JSON file
            
        Returns:
            TestScenario object
        """
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # Extract metadata fields
        metadata = ScenarioMetadata(
            name=data.pop("name", "unnamed"),
            description=data.pop("description", ""),
            expected_sequence=data.pop("expected_sequence", []),
            expected_final_keys=data.pop("expected_final_keys", []),
            unexpected_final_keys=data.pop("unexpected_final_keys", []),
            expected_error=data.pop("expected_error", False),
            tags=data.pop("tags", [])
        )
        
        # The rest of the data is considered the initial state
        return cls(initial_state=data, metadata=metadata)


class ScenarioRegistry:
    """Registry to store and retrieve test scenarios by category."""
    
    def __init__(self):
        """Initialize an empty scenario registry."""
        self._scenarios: Dict[str, Dict[str, TestScenario]] = {}
    
    def register(self, category: str, scenario: TestScenario) -> None:
        """
        Register a scenario in a specific category.
        
        Args:
            category: Category name for grouping related scenarios
            scenario: TestScenario object to register
        """
        if category not in self._scenarios:
            self._scenarios[category] = {}
        
        self._scenarios[category][scenario.metadata.name] = scenario
    
    def get(self, category: str, name: str) -> Optional[TestScenario]:
        """
        Get a scenario by category and name.
        
        Args:
            category: Category to look in
            name: Name of the scenario
            
        Returns:
            TestScenario object or None if not found
        """
        return self._scenarios.get(category, {}).get(name)
    
    def get_all(self, category: Optional[str] = None) -> List[TestScenario]:
        """
        Get all scenarios, optionally filtered by category.
        
        Args:
            category: Optional category to filter by
            
        Returns:
            List of TestScenario objects
        """
        if category:
            return list(self._scenarios.get(category, {}).values())
        
        result = []
        for cat_scenarios in self._scenarios.values():
            result.extend(cat_scenarios.values())
        return result
    
    def get_by_tag(self, tag: str) -> List[TestScenario]:
        """
        Get all scenarios that have a specific tag.
        
        Args:
            tag: Tag to filter by
            
        Returns:
            List of TestScenario objects with the specified tag
        """
        result = []
        for scenario in self.get_all():
            if tag in scenario.metadata.tags:
                result.append(scenario)
        return result
    
    def list_categories(self) -> List[str]:
        """
        Get all category names.
        
        Returns:
            List of category names
        """
        return list(self._scenarios.keys())
    
    def list_scenario_names(self, category: Optional[str] = None) -> Dict[str, List[str]]:
        """
        Get all scenario names, grouped by category.
        
        Args:
            category: Optional category to filter by
            
        Returns:
            Dictionary mapping category names to lists of scenario names
        """
        if category:
            return {category: list(self._scenarios.get(category, {}).keys())}
        
        result = {}
        for cat, scenarios in self._scenarios.items():
            result[cat] = list(scenarios.keys())
        return result


# Create a global registry instance
registry = ScenarioRegistry()


# KFM Action Scenarios
# -------------------

def create_happy_path_scenario() -> TestScenario:
    """Create a standard successful execution scenario with 'keep' action."""
    initial_state = {
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
        }
    }
    
    metadata = ScenarioMetadata(
        name="happy_path",
        description="Standard successful execution with 'keep' action",
        expected_sequence=["monitor", "decide", "execute", "reflect"],
        expected_final_keys=[
            "input", "task_name", "performance_data", "task_requirements",
            "kfm_action", "active_component", "result", "execution_performance",
            "reflection", "reflections", "reflection_insights", 
            "reflection_analysis", "validation_results"
        ],
        tags=["kfm", "success", "keep"]
    )
    
    return TestScenario(initial_state, metadata)


def create_kill_action_scenario() -> TestScenario:
    """Create a scenario with 'kill' KFM action due to poor performance."""
    initial_state = {
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
        }
    }
    
    metadata = ScenarioMetadata(
        name="kill_action",
        description="Execution with 'kill' action due to poor performance",
        expected_sequence=["monitor", "decide", "execute", "reflect"],
        expected_final_keys=[
            "input", "task_name", "performance_data", "task_requirements",
            "kfm_action", "active_component", "result", "execution_performance",
            "reflection", "reflections", "reflection_insights", 
            "reflection_analysis", "validation_results"
        ],
        tags=["kfm", "success", "kill"]
    )
    
    return TestScenario(initial_state, metadata)


def create_marry_action_scenario() -> TestScenario:
    """Create a scenario with 'marry' KFM action due to excellent performance."""
    initial_state = {
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
        }
    }
    
    metadata = ScenarioMetadata(
        name="marry_action",
        description="Execution with 'marry' action due to excellent performance",
        expected_sequence=["monitor", "decide", "execute", "reflect"],
        expected_final_keys=[
            "input", "task_name", "performance_data", "task_requirements",
            "kfm_action", "active_component", "result", "execution_performance",
            "reflection", "reflections", "reflection_insights", 
            "reflection_analysis", "validation_results"
        ],
        tags=["kfm", "success", "marry"]
    )
    
    return TestScenario(initial_state, metadata)


# Error Scenarios
# --------------

def create_execution_error_scenario() -> TestScenario:
    """Create a scenario with an error during execution."""
    initial_state = {
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
        "execution_error": "Test execution error"
    }
    
    metadata = ScenarioMetadata(
        name="execution_error",
        description="Execution with error in the execute action node",
        expected_sequence=["monitor", "decide", "execute", "reflect"],
        expected_final_keys=[
            "input", "task_name", "error", "done",
            "kfm_action", "active_component", "validation_results"
        ],
        unexpected_final_keys=[
            "reflection_insights", "reflection_analysis"
        ],
        expected_error=True,
        tags=["error", "execution"]
    )
    
    return TestScenario(initial_state, metadata)


def create_reflection_error_scenario() -> TestScenario:
    """Create a scenario with an error during reflection but successful execution."""
    initial_state = {
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
        "reflection_error": "LLM API error"
    }
    
    metadata = ScenarioMetadata(
        name="reflection_error",
        description="Successful execution but error in reflection",
        expected_sequence=["monitor", "decide", "execute", "reflect"],
        expected_final_keys=[
            "input", "task_name", "performance_data", "task_requirements",
            "kfm_action", "active_component", "result", "execution_performance",
            "reflection", "reflections", "validation_results"
        ],
        tags=["error", "reflection"]
    )
    
    return TestScenario(initial_state, metadata)


def create_missing_fields_scenario() -> TestScenario:
    """Create a scenario with missing fields in the state."""
    initial_state = {
        "input_data": {
            "text": "Missing fields test input"
        },
        "task_name": "missing_fields_task"
        # No performance_data or task_requirements
    }
    
    metadata = ScenarioMetadata(
        name="missing_fields",
        description="Missing fields in the state",
        expected_sequence=["monitor"],  # Should stop after monitor
        expected_error=True,
        tags=["error", "validation"]
    )
    
    return TestScenario(initial_state, metadata)


# Complex Scenarios
# ---------------

def create_multi_component_scenario() -> TestScenario:
    """Create a scenario with multiple components and complex performance data."""
    initial_state = {
        "input_data": {
            "text": "Complex multi-component test input",
            "parameters": {
                "max_tokens": 100,
                "temperature": 0.7
            }
        },
        "task_name": "multi_component_task",
        "performance_data": {
            "component_a": {"latency": 0.5, "accuracy": 0.95, "cost": 0.01},
            "component_b": {"latency": 0.8, "accuracy": 0.85, "cost": 0.005},
            "component_c": {"latency": 0.3, "accuracy": 0.88, "cost": 0.015},
            "component_d": {"latency": 1.2, "accuracy": 0.98, "cost": 0.02}
        },
        "task_requirements": {
            "max_latency": 1.0,
            "min_accuracy": 0.9,
            "max_cost": 0.02
        },
        "kfm_action": {
            "action": "keep",
            "component": "component_a",
            "reason": "Best balance of metrics"
        },
        "execution_result": {
            "status": "success", 
            "data": {
                "records": 10,
                "metadata": {
                    "processing_time": 0.5,
                    "model_version": "v2"
                }
            }
        },
        "execution_performance": {
            "latency": 0.5, 
            "accuracy": 0.95,
            "cost": 0.01
        }
    }
    
    metadata = ScenarioMetadata(
        name="multi_component",
        description="Complex scenario with multiple components and detailed metrics",
        expected_sequence=["monitor", "decide", "execute", "reflect"],
        expected_final_keys=[
            "input", "task_name", "performance_data", "task_requirements",
            "kfm_action", "active_component", "result", "execution_performance",
            "reflection", "reflections", "reflection_insights", 
            "reflection_analysis", "validation_results"
        ],
        tags=["complex", "multi-component"]
    )
    
    return TestScenario(initial_state, metadata)


def create_multi_iteration_scenario() -> TestScenario:
    """Create a scenario for testing multiple iterations of the KFM loop."""
    initial_state = {
        "input_data": {
            "text": "Multi-iteration test input"
        },
        "task_name": "multi_iteration_task",
        "performance_data": {
            "component_a": {"latency": 0.5, "accuracy": 0.85},
            "component_b": {"latency": 0.8, "accuracy": 0.90},
            "component_c": {"latency": 0.4, "accuracy": 0.75}
        },
        "task_requirements": {
            "max_latency": 1.0,
            "min_accuracy": 0.95  # Set high to force multiple iterations
        },
        "iteration_count": 0,
        "max_iterations": 3,
        "previous_decisions": []
    }
    
    metadata = ScenarioMetadata(
        name="multi_iteration",
        description="Scenario designed for testing multiple iterations of the KFM loop",
        expected_sequence=["monitor", "decide", "execute", "reflect", "monitor"],  # Should loop
        tags=["complex", "multi-iteration", "loop"]
    )
    
    return TestScenario(initial_state, metadata)


# Register all scenarios
# --------------------

def register_all_scenarios():
    """Register all predefined scenarios with the registry."""
    # KFM Action Scenarios
    registry.register("kfm", create_happy_path_scenario())
    registry.register("kfm", create_kill_action_scenario())
    registry.register("kfm", create_marry_action_scenario())
    
    # Error Scenarios
    registry.register("errors", create_execution_error_scenario())
    registry.register("errors", create_reflection_error_scenario())
    registry.register("errors", create_missing_fields_scenario())
    
    # Complex Scenarios
    registry.register("complex", create_multi_component_scenario())
    registry.register("complex", create_multi_iteration_scenario())


# Helper functions for test usage
# -----------------------------

def get_scenario(category: str, name: str) -> Optional[TestScenario]:
    """
    Get a specific scenario by category and name.
    
    Args:
        category: Category to look in
        name: Name of the scenario
        
    Returns:
        TestScenario object or None if not found
    """
    return registry.get(category, name)


def get_all_scenarios(category: Optional[str] = None) -> List[TestScenario]:
    """
    Get all scenarios, optionally filtered by category.
    
    Args:
        category: Optional category to filter by
        
    Returns:
        List of TestScenario objects
    """
    return registry.get_all(category)


def get_scenarios_by_tag(tag: str) -> List[TestScenario]:
    """
    Get all scenarios that have a specific tag.
    
    Args:
        tag: Tag to filter by
        
    Returns:
        List of TestScenario objects with the specified tag
    """
    return registry.get_by_tag(tag)


def save_scenarios_to_directory(directory: str, 
                               scenarios: Optional[List[TestScenario]] = None) -> None:
    """
    Save scenarios to JSON files in a directory.
    
    Args:
        directory: Directory to save the files
        scenarios: Optional list of scenarios to save (defaults to all)
    """
    if scenarios is None:
        scenarios = registry.get_all()
    
    os.makedirs(directory, exist_ok=True)
    
    for scenario in scenarios:
        file_name = f"{scenario.metadata.name}.json"
        file_path = os.path.join(directory, file_name)
        scenario.save_to_file(file_path)


# Initialize the registry when the module is imported
register_all_scenarios() 