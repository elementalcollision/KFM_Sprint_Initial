#!/usr/bin/env python
"""
Demonstration of the Cursor AI Command Palette Integration.

This script shows how to use the Cursor AI Command Palette to interact
with the LangGraph debugging, tracing, and visualization tools.
"""

import os
import sys
import time
import random
from typing import Dict, Any, List

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the cursor_commands module
from src.cursor_commands import (
    handle_command,
    COMMAND_PREFIX,
    current_graph,
    current_state,
    current_execution_history
)

# Import necessary modules for the demo
from src.debugging import (
    set_breakpoint,
    clear_all_breakpoints
)

from src.tracing import (
    configure_tracing,
    reset_trace_history
)

from src.logger import setup_logger

# Setup logger for the demo
demo_logger = setup_logger('examples.cursor_commands_demo')

# Import langgraph components for creating a sample graph
from langgraph.graph import StateGraph
import networkx as nx

class DemoState(dict):
    """Simple state class for the demo."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def to_dict(self):
        return dict(self)

def setup_demo_graph():
    """
    Create a sample graph for the demo.
    
    Returns:
        StateGraph: A simple graph for demonstration
    """
    # Create the graph
    graph = StateGraph(DemoState)
    
    # Add nodes
    graph.add_node("start", lambda state: process_start(state))
    graph.add_node("process_data", lambda state: process_data(state))
    graph.add_node("validate_data", lambda state: validate_data(state))
    graph.add_node("transform_data", lambda state: transform_data(state))
    graph.add_node("handle_error", lambda state: handle_error(state))
    graph.add_node("finalize", lambda state: finalize(state))
    
    # Add edges
    graph.add_edge("start", "process_data")
    graph.add_conditional_edges(
        "process_data",
        lambda state: "validate_data" if not state.get("error") else "handle_error"
    )
    graph.add_edge("validate_data", "transform_data")
    graph.add_edge("handle_error", "finalize")
    graph.add_edge("transform_data", "finalize")
    graph.add_edge("finalize", "end")
    
    # Set the entry point
    graph.set_entry_point("start")
    
    return graph

def process_start(state: Dict[str, Any]) -> Dict[str, Any]:
    """Start node function."""
    demo_logger.info("Processing start node")
    
    # Update state
    state["timestamp"] = time.time()
    state["processed"] = False
    state["data"] = {"values": [random.randint(1, 100) for _ in range(5)]}
    state["meta"] = {"source": "demo", "version": "1.0"}
    
    return state

def process_data(state: Dict[str, Any]) -> Dict[str, Any]:
    """Process data node function."""
    demo_logger.info("Processing data node")
    
    # Simulate processing
    time.sleep(0.2)
    
    # Update state
    state["processed"] = True
    state["processing_time"] = 0.2
    
    # Randomly introduce an error
    if random.random() < 0.3:
        state["error"] = "Data processing failed: Invalid format"
        demo_logger.warning(f"Error in process_data: {state['error']}")
    
    return state

def validate_data(state: Dict[str, Any]) -> Dict[str, Any]:
    """Validate data node function."""
    demo_logger.info("Validating data")
    
    # Simulate validation
    time.sleep(0.1)
    
    # Update state
    state["validated"] = True
    state["validation_timestamp"] = time.time()
    
    # Check data values
    values = state.get("data", {}).get("values", [])
    state["stats"] = {
        "count": len(values),
        "sum": sum(values),
        "average": sum(values) / len(values) if values else 0
    }
    
    return state

def transform_data(state: Dict[str, Any]) -> Dict[str, Any]:
    """Transform data node function."""
    demo_logger.info("Transforming data")
    
    # Simulate transformation
    time.sleep(0.3)
    
    # Update state
    values = state.get("data", {}).get("values", [])
    state["data"]["transformed_values"] = [v * 2 for v in values]
    state["transformation_complete"] = True
    
    return state

def handle_error(state: Dict[str, Any]) -> Dict[str, Any]:
    """Handle error node function."""
    demo_logger.info("Handling error")
    
    # Simulate error handling
    time.sleep(0.1)
    
    # Update state
    error = state.get("error", "Unknown error")
    state["error_handled"] = True
    state["resolution"] = f"Resolved: {error}"
    
    return state

def finalize(state: Dict[str, Any]) -> Dict[str, Any]:
    """Finalize node function."""
    demo_logger.info("Finalizing")
    
    # Simulate finalization
    time.sleep(0.1)
    
    # Update state
    state["complete"] = True
    state["end_timestamp"] = time.time()
    state["duration"] = state["end_timestamp"] - state.get("timestamp", state["end_timestamp"])
    
    return state

def run_graph(graph, initial_state=None):
    """Run the graph and collect execution data."""
    from src.cursor_commands import current_graph, current_state, current_execution_history
    
    # Reset the trace history
    reset_trace_history()
    
    # Create initial state if not provided
    if initial_state is None:
        initial_state = DemoState()
    
    # Set the current graph for the cursor commands
    import src.cursor_commands
    src.cursor_commands.current_graph = graph
    src.cursor_commands.current_execution_history = []
    
    # Execute the graph
    try:
        # Mock execution and collection of state history
        # In a real application, this would be actual graph execution
        
        # Initial state
        current_state = initial_state
        src.cursor_commands.current_state = current_state
        src.cursor_commands.current_execution_history.append({
            "node_name": "entry",
            "state": dict(current_state),
            "timestamp": time.time()
        })
        
        # Execute each node in sequence
        nodes = ["start", "process_data"]
        
        # Determine conditional path
        if not process_data(current_state).get("error"):
            nodes.extend(["validate_data", "transform_data"])
        else:
            nodes.append("handle_error")
        
        # Finalize
        nodes.append("finalize")
        
        # Execute the nodes
        for node in nodes:
            # Get the node function
            if node == "start":
                node_func = process_start
            elif node == "process_data":
                node_func = process_data
            elif node == "validate_data":
                node_func = validate_data
            elif node == "transform_data":
                node_func = transform_data
            elif node == "handle_error":
                node_func = handle_error
            elif node == "finalize":
                node_func = finalize
            else:
                continue
            
            # Execute the node
            demo_logger.info(f"Executing node: {node}")
            start_time = time.time()
            current_state = node_func(current_state)
            duration = time.time() - start_time
            
            # Update global state
            src.cursor_commands.current_state = current_state
            
            # Record execution
            src.cursor_commands.current_execution_history.append({
                "node_name": node,
                "state": dict(current_state),
                "timestamp": time.time(),
                "duration": duration
            })
            
            # Pause to simulate real execution
            time.sleep(0.1)
        
        # Final state
        return current_state
    
    except Exception as e:
        demo_logger.exception(f"Error during graph execution: {e}")
        return None

def display_command_help():
    """Display help for using the Cursor AI Command Palette."""
    print("\n" + "="*80)
    print(" CURSOR AI COMMAND PALETTE DEMO ")
    print("="*80)
    print(f"The command prefix is: {COMMAND_PREFIX}")
    print("Commands are entered in the format: /lg command [arguments]")
    print("\nTry these example commands:")
    
    examples = [
        "help                        - Show all available commands",
        "help breakpoint             - Get help for a specific command",
        "breakpoint --node process_data - Set a breakpoint on a node",
        "breakpoints                 - List all breakpoints",
        "inspect                     - View the current state",
        "inspect --field data        - View a specific field in the state",
        "inspect --format json       - View the state as JSON",
        "timeline                    - Show the execution timeline",
        "search --term error         - Search for values in state history",
        "visualize                   - Create a basic visualization",
        "visualize --type execution  - Visualize the execution path",
        "visualize --interactive     - Create an interactive visualization"
    ]
    
    for example in examples:
        print(f"{COMMAND_PREFIX} {example}")
    
    print("\nYou can run commands by entering them below.")
    print("Type 'exit' to quit the demo.\n")

def demo_repl():
    """Run a simple REPL for testing Cursor AI commands."""
    display_command_help()
    
    # Create and run the graph
    print("\nSetting up the demo graph...")
    graph = setup_demo_graph()
    
    # Configure tracing
    configure_tracing(log_level="INFO")
    
    print("Running the graph...")
    final_state = run_graph(graph)
    
    if final_state:
        print("Graph execution complete.")
        print(f"Final state has {len(final_state)} keys.")
    else:
        print("Graph execution failed.")
    
    # Set a sample breakpoint for the demo
    set_breakpoint("process_data", "state.get('error') is not None", description="Break on error")
    
    # Run the REPL
    print("\nEnter commands below (type 'exit' to quit):")
    while True:
        try:
            command = input("> ")
            
            if command.lower() in ("exit", "quit"):
                break
            
            # Handle empty input
            if not command:
                continue
            
            # Process the command
            if not command.startswith(COMMAND_PREFIX):
                # Auto-add prefix
                command = f"{COMMAND_PREFIX} {command}"
            
            result = handle_command(command)
            print(result)
            
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")
    
    # Clean up
    clear_all_breakpoints()
    print("Demo complete. Thanks for trying the Cursor AI Command Palette!")

def test_visualization_robustness():
    """Test the visualization function's robustness to different graph structures."""
    from src.cursor_commands import handle_command, COMMAND_PREFIX
    import src.cursor_commands
    
    # Test with a minimal mock graph
    print("\nTesting visualization command with minimal graph structure...")
    
    # Create a basic mock object that doesn't have expected graph properties
    class MinimalMockGraph:
        def __init__(self):
            # No graph attribute
            pass
        
        @property
        def nodes(self):
            return ["start", "process", "validate", "end"]
    
    # Set the mock graph
    src.cursor_commands.current_graph = MinimalMockGraph()
    
    # Create some execution history
    src.cursor_commands.current_execution_history = [
        {"node_name": "start", "state": {}, "timestamp": time.time()},
        {"node_name": "process", "state": {}, "timestamp": time.time()},
        {"node_name": "validate", "state": {}, "timestamp": time.time()}
    ]
    
    # Test with different visualization types
    for viz_type in ["basic", "execution", "timing"]:
        print(f"\nTesting visualization type: {viz_type}")
        result = handle_command(f"{COMMAND_PREFIX} visualize --type {viz_type}")
        print(f"Result: {result}")
        if "Error" in result:
            print("FAILED: Visualization failed with error")
        else:
            print("SUCCESS: Visualization created successfully")
    
    # Test with empty execution history
    print("\nTesting with empty execution history...")
    src.cursor_commands.current_execution_history = []
    result = handle_command(f"{COMMAND_PREFIX} visualize")
    print(f"Result: {result}")
    if "Error" in result:
        print("FAILED: Visualization failed with error")
    else:
        print("SUCCESS: Visualization created successfully")
    
    # Reset the state
    src.cursor_commands.current_graph = None
    src.cursor_commands.current_execution_history = []
    
    print("\nVisualization robustness testing complete.\n")

if __name__ == "__main__":
    # Run the robustness test first to verify our fixes
    test_visualization_robustness()
    
    # Then run the regular demo REPL
    demo_repl() 