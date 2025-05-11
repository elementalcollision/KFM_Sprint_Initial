#!/usr/bin/env python3
"""
Example demonstrating the usage of KFMAgentState in a workflow scenario.

This example shows how to create, update, and use a KFMAgentState object
to track state changes through different processing steps.
"""

import sys
import os

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.core.state import KFMAgentState
from typing import Dict, Any


def monitor_step(state: KFMAgentState) -> KFMAgentState:
    """Simulate the monitoring step in the workflow."""
    print("\n--- Monitor Step ---")
    print(f"Current state: {state}")
    
    # Update performance data
    state.set_performance('analyze_fast', {'latency': 0.5, 'accuracy': 0.7})
    state.set_performance('analyze_accurate', {'latency': 2.0, 'accuracy': 0.95})
    
    # Update task requirements
    state.task_requirements = {
        'min_accuracy': 0.8,
        'max_latency': 1.0
    }
    
    print(f"Updated state: {state}")
    return state


def decision_step(state: KFMAgentState) -> KFMAgentState:
    """Simulate the decision step in the workflow."""
    print("\n--- Decision Step ---")
    print(f"Current state: {state}")
    
    # Make a KFM decision based on performance and requirements
    performance = state.get_performance()
    requirements = state.task_requirements
    
    # Simple decision logic (in a real system, this would be more complex)
    for component, metrics in performance.items():
        if metrics['accuracy'] >= requirements['min_accuracy'] and metrics['latency'] <= requirements['max_latency']:
            # Component meets all requirements - Marry
            state.set_kfm_decision('marry', component)
            print(f"Decision: Marry {component}")
            break
        elif metrics['accuracy'] >= requirements['min_accuracy']:
            # Component meets accuracy but not latency - Fuck
            state.set_kfm_decision('fuck', component)
            print(f"Decision: Fuck {component}")
            break
    else:
        # No component meets requirements - Kill
        # In this example, we'll kill the first component if neither meets requirements
        if performance:
            comp = next(iter(performance.keys()))
            state.set_kfm_decision('kill', comp)
            print(f"Decision: Kill {comp}")
    
    print(f"Updated state: {state}")
    return state


def execution_step(state: KFMAgentState) -> KFMAgentState:
    """Simulate the execution step in the workflow."""
    print("\n--- Execution Step ---")
    print(f"Current state: {state}")
    
    # Get KFM decision
    kfm_decision = state.kfm_decision
    if kfm_decision:
        action = kfm_decision['action']
        component = kfm_decision['component']
        print(f"Executing with {action} action on {component}")
        
        # Set active component based on decision
        state.active_component = component
        
        # Simulate execution result
        if action == 'marry':
            result = {"status": "success", "message": f"Component {component} executed perfectly"}
            perf = {'latency': 0.8, 'accuracy': 0.9}
        elif action == 'fuck':
            result = {"status": "partial", "message": f"Component {component} executed with some limitations"}
            perf = {'latency': 1.5, 'accuracy': 0.85}
        else:  # kill
            result = {"status": "failure", "message": f"Component {component} had to be terminated"}
            perf = {'latency': 3.0, 'accuracy': 0.5}
            # Set error for kill action (for demonstration)
            state.set_error(f"Component {component} performance was unacceptable")
    else:
        # No decision, use default component
        print("No KFM decision, using default component")
        state.active_component = "default_component"
        result = {"status": "default", "message": "Used default component"}
        perf = {'latency': 1.0, 'accuracy': 0.75}
    
    # Update state with results
    state.set_result(result)
    state.execution_performance = perf
    
    print(f"Updated state: {state}")
    return state


def reflect_step(state: KFMAgentState) -> KFMAgentState:
    """Simulate the reflection step in the workflow."""
    print("\n--- Reflection Step ---")
    print(f"Current state: {state}")
    
    # Check for error
    if state.has_error():
        print(f"Error detected: {state.error}")
        print("Not performing reflection due to error")
        state.set_done(True)
        return state
    
    # Simulate reflection on the execution
    kfm_decision = state.kfm_decision
    result = state.results
    execution_performance = state.execution_performance
    
    if kfm_decision:
        reflection = (
            f"Reflection: The {kfm_decision['action']} decision for component "
            f"{kfm_decision['component']} resulted in {result['status']} status. "
            f"Execution performance was latency={execution_performance['latency']}s, "
            f"accuracy={execution_performance['accuracy']}"
        )
        print(reflection)
        
        # In a real system, we might store this reflection in the state
        # state.reflection = reflection
    else:
        print("No KFM decision to reflect on")
    
    # Mark workflow as done
    state.set_done(True)
    
    print(f"Final state: {state}")
    return state


def run_workflow():
    """Run a simulated workflow using the KFMAgentState."""
    print("Starting KFM Agent Workflow Example")
    
    # Initialize state with input data
    initial_state = {
        'input': {'text': 'This is a sample text to analyze'},
        'task_name': 'text_analysis'
    }
    
    state = KFMAgentState(initial_state)
    print(f"Initial state: {state}")
    
    # Simulate workflow steps
    state = monitor_step(state)
    state = decision_step(state)
    state = execution_step(state)
    state = reflect_step(state)
    
    # Convert final state to dictionary (for compatibility with TypedDict)
    final_dict = state.to_dict()
    print("\nFinal state as dictionary (TypedDict compatible):")
    for key, value in final_dict.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    run_workflow() 