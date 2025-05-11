#!/usr/bin/env python3
"""
Demonstrates the state tracing functionality in the KFM Agent workflow.

This example runs the KFM Agent with state tracing enabled to visualize
how state flows through the nodes and track changes between each step.
"""

import sys
import os
import logging

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.kfm_agent import run_kfm_agent, print_state_trace
from src.tracing import visualize_trace_path


def run_normal_example():
    """Run the KFM agent with standard input."""
    print("\n=== Running KFM Agent with Normal Input ===\n")
    
    # Create sample input data
    input_data = {
        "text": "This is a sample text to analyze.",
        "metadata": {
            "source": "example",
            "priority": "medium"
        }
    }
    
    # Run the agent with tracing enabled
    final_state = run_kfm_agent(
        input_data=input_data,
        task_name="trace_example",
        trace_level=logging.INFO
    )
    
    # Print the state trace
    print("\nState Trace (normal execution):")
    print_state_trace(show_all_states=False)


def run_error_example():
    """Run the KFM agent with input that will cause an error."""
    print("\n=== Running KFM Agent with Error-Inducing Input ===\n")
    
    # Create input data that will cause an error
    # (assuming our components expect a "text" field)
    input_data = {
        "non_text_field": "This will cause an error because 'text' is missing.",
        "metadata": {
            "source": "error_example",
            "priority": "high"
        }
    }
    
    # Run the agent with tracing enabled
    final_state = run_kfm_agent(
        input_data=input_data,
        task_name="error_example",
        trace_level=logging.INFO
    )
    
    # Print the state trace
    print("\nState Trace (error execution):")
    print_state_trace(show_all_states=False)


def run_custom_task_example():
    """Run the KFM agent with custom task requirements."""
    print("\n=== Running KFM Agent with Custom Task Requirements ===\n")
    
    # Create sample input data
    input_data = {
        "text": "This is a custom task example with specific requirements.",
        "metadata": {
            "source": "custom_example",
            "priority": "high"
        }
    }
    
    # Override the task name to trigger different requirements
    # (assuming the StateMonitor has specific requirements for tasks)
    final_state = run_kfm_agent(
        input_data=input_data,
        task_name="high_accuracy_task",
        trace_level=logging.INFO
    )
    
    # Print the state trace
    print("\nState Trace (custom task execution):")
    print_state_trace(show_all_states=False)


if __name__ == "__main__":
    # Run the examples
    try:
        # First example - normal execution
        run_normal_example()
        
        # Second example - error handling
        run_error_example()
        
        # Third example - custom task
        run_custom_task_example()
        
    except Exception as e:
        print(f"Error during example execution: {e}")
        # Still show the trace if available
        try:
            print("\nState Trace (after error):")
            print_state_trace()
        except:
            print("Trace visualization not available") 