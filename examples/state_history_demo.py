#!/usr/bin/env python
"""
Demonstration of the state history tracking functionality.

This script shows how to use the state history tracking features
to debug and analyze state changes during graph execution.
"""

import os
import sys
import json
import time
from typing import Dict, Any

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tracing import (
    configure_tracing,
    reset_trace_history,
    save_state_snapshot,
    get_state_snapshot,
    list_state_snapshots,
    search_state_history,
    get_state_timeline,
    get_state_at_point,
    get_state_history_tracker
)

from src.debugging import (
    configure_debug_level,
    diff_states,
    create_state_checkpoint,
    compare_with_checkpoint,
    show_execution_timeline,
    find_states_with_value,
    time_travel_to_state
)

from src.logger import setup_logger

# Setup a logger for this demo
demo_logger = setup_logger('examples.state_history_demo')


def simulate_node_execution(node_name: str, input_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Simulate a node execution that transforms a state.
    
    Args:
        node_name: Name of the node
        input_state: Input state to transform
        
    Returns:
        Transformed state
    """
    demo_logger.info(f"Executing node: {node_name}")
    
    # Clone the input state to avoid modifying the original
    output_state = json.loads(json.dumps(input_state))
    
    # Apply transformations based on node name
    if node_name == "initialize_state":
        output_state["initialized"] = True
        output_state["timestamp"] = time.time()
        output_state["step_count"] = 1
    
    elif node_name == "process_data":
        output_state["data_processed"] = True
        output_state["processed_items"] = output_state.get("items", [])
        output_state["items"] = []  # Clear original items
        output_state["step_count"] += 1
    
    elif node_name == "validate_results":
        output_state["validation_status"] = "passed" if output_state.get("data_processed") else "failed"
        output_state["validation_timestamp"] = time.time()
        output_state["step_count"] += 1
    
    elif node_name == "generate_output":
        output_state["output_generated"] = True
        output_state["output"] = {
            "status": output_state.get("validation_status", "unknown"),
            "items_processed": len(output_state.get("processed_items", [])),
            "timestamp": time.time()
        }
        output_state["step_count"] += 1
    
    elif node_name == "finalize":
        output_state["done"] = True
        output_state["final_status"] = "success" if output_state.get("output_generated") else "incomplete"
        output_state["step_count"] += 1
    
    # Add some artificial delay to show timeline differences
    time.sleep(0.5)
    
    # Add this state to the history tracker
    tracker = get_state_history_tracker()
    tracker.add_state(
        node_name=node_name,
        state=output_state,
        is_input=False,
        metadata={
            "node_name": node_name,
            "timestamp": time.time()
        }
    )
    
    return output_state


def demonstrate_state_history_tracking():
    """
    Demonstrate the state history tracking functionality.
    """
    demo_logger.info("=== STATE HISTORY TRACKING DEMONSTRATION ===")
    
    # Configure tracing and debugging
    configure_tracing(log_level="INFO", history_buffer_size=20)
    configure_debug_level("INFO")
    reset_trace_history()
    
    # Initial state
    initial_state = {
        "id": "demo-123",
        "name": "State History Demo",
        "items": ["item1", "item2", "item3"],
        "options": {
            "verbose": True,
            "debug": True
        }
    }
    
    demo_logger.info("\n1. Creating initial state snapshot")
    initial_checkpoint_id = create_state_checkpoint(
        initial_state, 
        "Initial State", 
        "demo", 
        "Initial state for the demonstration"
    )
    
    # Simulate graph execution
    demo_logger.info("\n2. Simulating graph execution through multiple nodes")
    
    # Define the execution path
    execution_path = [
        "initialize_state",
        "process_data",
        "validate_results",
        "generate_output",
        "finalize"
    ]
    
    # Execute each node in the path
    current_state = initial_state
    for node_name in execution_path:
        demo_logger.info(f"Executing node: {node_name}")
        current_state = simulate_node_execution(node_name, current_state)
    
    # Show final state
    demo_logger.info("\n3. Final state:")
    demo_logger.info(json.dumps(current_state, indent=2))
    
    # Create a snapshot of the final state
    demo_logger.info("\n4. Creating final state snapshot")
    final_checkpoint_id = create_state_checkpoint(
        current_state, 
        "Final State", 
        "demo", 
        "Final state after execution"
    )
    
    # Compare initial and final states
    demo_logger.info("\n5. Comparing initial and final states")
    diff_result = compare_with_checkpoint(current_state, initial_checkpoint_id)
    demo_logger.info(f"Comparison summary: {diff_result['summary']}")
    demo_logger.info("Detailed differences:")
    demo_logger.info(diff_result['visualization'])
    
    # Show timeline visualization
    demo_logger.info("\n6. Execution timeline:")
    timeline = show_execution_timeline(width=100, include_states=False)
    demo_logger.info(timeline)
    
    # Search state history
    demo_logger.info("\n7. Searching state history")
    search_results = find_states_with_value("validate")
    demo_logger.info(f"Found {len(search_results)} states containing 'validate'")
    for i, result in enumerate(search_results):
        demo_logger.info(f"Result {i+1}: Node '{result['node_name']}' at {result['datetime']}")
    
    # Time travel to a specific state
    demo_logger.info("\n8. Time traveling to a specific state")
    # Get the state after the "process_data" node (index 1)
    process_data_state = time_travel_to_state(1)
    if process_data_state:
        demo_logger.info("State after 'process_data':")
        demo_logger.info(json.dumps(process_data_state, indent=2))
    
    # List all available snapshots
    demo_logger.info("\n9. Listing all snapshots")
    snapshots = list_state_snapshots()
    demo_logger.info(f"Found {len(snapshots)} snapshots:")
    for snapshot in snapshots:
        demo_logger.info(f"- {snapshot['label']} ({snapshot['id']})")
    
    # Filter snapshots by category
    demo_logger.info("\n10. Filtering snapshots by category")
    demo_snapshots = list_state_snapshots(category="demo")
    demo_logger.info(f"Found {len(demo_snapshots)} snapshots in category 'demo':")
    for snapshot in demo_snapshots:
        demo_logger.info(f"- {snapshot['label']} ({snapshot['id']})")
    
    # Demonstrate detailed timeline
    demo_logger.info("\n11. Detailed execution timeline with states:")
    detailed_timeline = show_execution_timeline(width=100, include_states=True)
    demo_logger.info(detailed_timeline)
    
    demo_logger.info("\n=== DEMONSTRATION COMPLETE ===")


if __name__ == "__main__":
    demonstrate_state_history_tracking() 