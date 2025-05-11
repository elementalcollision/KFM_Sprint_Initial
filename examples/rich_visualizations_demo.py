"""
Rich visualizations demo for Cursor AI command palette.

This script demonstrates the rich visualization capabilities 
for the Cursor AI command palette.
"""

import sys
import os
import time
from typing import Dict, Any, List, Optional
import networkx as nx
import matplotlib.pyplot as plt

# Add the parent directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.rich_visualizations import (
    format_rich_state,
    format_field_path,
    create_rich_graph_visualization,
    create_rich_diff_visualization,
    create_execution_replay_visualization
)

from src.cursor_commands import (
    command_inspect_rich_state,
    command_search_rich_states,
    command_visualize_rich_graph,
    command_diff_rich_states,
    command_execution_replay,
    command_show_rich_timeline,
    # Add access to global state
    handle_command, 
    COMMAND_PREFIX
)

import src.cursor_commands

def create_sample_state() -> Dict[str, Any]:
    """Create a sample state for demonstration purposes"""
    return {
        "user": {
            "id": "user123",
            "name": "John Doe",
            "email": "john@example.com",
            "preferences": {
                "theme": "dark",
                "notifications": True,
                "language": "en"
            }
        },
        "session": {
            "id": "sess456",
            "start_time": "2024-06-05T10:15:30",
            "active": True,
            "last_activity": "2024-06-05T11:45:12"
        },
        "data": {
            "items": [
                {"id": 1, "name": "Item 1", "price": 19.99},
                {"id": 2, "name": "Item 2", "price": 29.99},
                {"id": 3, "name": "Item 3", "price": 9.99}
            ],
            "count": 3,
            "total_price": 59.97
        },
        "errors": [],
        "status": "success"
    }

def create_sample_graph():
    """Create a sample graph for demonstration purposes"""
    G = nx.DiGraph()
    
    # Add nodes
    nodes = ["start", "process_input", "validate_data", "transform_data", 
             "apply_rules", "generate_output", "handle_error", "end"]
    
    for node in nodes:
        G.add_node(node)
    
    # Add edges
    G.add_edge("start", "process_input")
    G.add_edge("process_input", "validate_data")
    G.add_edge("validate_data", "transform_data")
    G.add_edge("validate_data", "handle_error")
    G.add_edge("transform_data", "apply_rules")
    G.add_edge("apply_rules", "generate_output")
    G.add_edge("apply_rules", "handle_error")
    G.add_edge("generate_output", "end")
    G.add_edge("handle_error", "end")
    
    return G

def create_sample_execution_history():
    """Create a sample execution history"""
    base_state = create_sample_state()
    graph = create_sample_graph()
    
    # Create execution history
    history = []
    nodes = ["start", "process_input", "validate_data", "transform_data", 
             "apply_rules", "generate_output", "end"]
    
    for i, node in enumerate(nodes):
        # Create a slightly modified state for each step
        state = base_state.copy()
        
        # Add some modifications to show state changes
        if node == "process_input":
            state["data"]["raw_input"] = "Sample input data"
        elif node == "validate_data":
            state["data"]["validation_result"] = "Valid"
        elif node == "transform_data":
            state["data"]["transformed"] = True
        elif node == "apply_rules":
            state["data"]["rules_applied"] = ["rule1", "rule2"]
        elif node == "generate_output":
            state["data"]["output"] = "Sample output data"
        
        # Timestamps with small increments
        timestamp = f"2024-06-05T10:{20+i}:{30+i*5}"
        
        # Create the history entry
        entry = {
            "node_name": node,
            "timestamp": timestamp,
            "state": state,
            "duration": 0.1 + (i * 0.05),  # Increasing duration
            "success": True
        }
        
        history.append(entry)
    
    return history, graph

def demo_rich_state_inspection():
    """Demonstrate rich state inspection"""
    print("\n===== Rich State Inspection =====")
    
    # Create sample state
    sample_state = create_sample_state()
    
    # Set the state in cursor_commands
    src.cursor_commands.current_state = sample_state
    
    # Demonstrate different formats
    formats = ["pretty", "json", "table", "compact"]
    
    for fmt in formats:
        print(f"\n--- Format: {fmt} ---")
        result = command_inspect_rich_state(format=fmt)
        print(result)
    
    # Demonstrate field inspection
    fields = ["user.name", "data.items", "session", "nonexistent.field"]
    
    for field in fields:
        print(f"\n--- Field: {field} ---")
        result = command_inspect_rich_state(field=field)
        print(result)

def demo_rich_graph_visualization():
    """Demonstrate rich graph visualization"""
    print("\n===== Rich Graph Visualization =====")
    
    # Create sample graph and execution history
    history, graph = create_sample_execution_history()
    
    # Set the graph and history in cursor_commands
    src.cursor_commands.current_graph = graph
    src.cursor_commands.current_execution_history = history
    
    # Demonstrate different visualization types
    print("\n--- Basic Graph Visualization ---")
    result = command_visualize_rich_graph(type="basic")
    print(result)
    
    print("\n--- Execution Graph Visualization ---")
    result = command_visualize_rich_graph(type="execution")
    print(result)
    
    print("\n--- Timing Graph Visualization ---")
    result = command_visualize_rich_graph(type="timing")
    print(result)
    
    print("\n--- Focused Graph Visualization ---")
    result = command_visualize_rich_graph(type="focus", focus="validate_data")
    print(result)

def demo_rich_diff_visualization():
    """Demonstrate rich diff visualization"""
    print("\n===== Rich Diff Visualization =====")
    
    # Create two sample states with differences
    state1 = create_sample_state()
    state2 = state1.copy()
    
    # Make some modifications to state2
    state2["user"]["preferences"]["theme"] = "light"
    state2["errors"] = ["Minor warning"]
    state2["data"]["items"].append({"id": 4, "name": "Item 4", "price": 14.99})
    state2["data"]["count"] = 4
    state2["data"]["total_price"] = 74.96
    state2["session"]["active"] = False
    state2["session"]["end_time"] = "2024-06-05T12:30:45"
    
    # Add these states to the execution history
    history = [
        {"node_name": "state1", "state": state1},
        {"node_name": "state2", "state": state2}
    ]
    src.cursor_commands.current_execution_history = history
    
    # Demonstrate different visualization formats
    print("\n--- Color Diff Visualization ---")
    result = command_diff_rich_states(state1=0, state2=1, format="color")
    print(result)
    
    print("\n--- Table Diff Visualization ---")
    result = command_diff_rich_states(state1=0, state2=1, format="table")
    print(result)
    
    print("\n--- Side-by-Side Diff Visualization ---")
    result = command_diff_rich_states(state1=0, state2=1, format="side-by-side")
    print(result)

def demo_execution_replay():
    """Demonstrate execution replay"""
    print("\n===== Execution Replay =====")
    
    # Create sample execution history
    history, graph = create_sample_execution_history()
    
    # Set the history and graph in cursor_commands
    src.cursor_commands.current_execution_history = history
    src.cursor_commands.current_graph = graph
    
    # Replay at different steps
    steps = [0, 2, 4, 6]
    
    for step in steps:
        print(f"\n--- Replay at Step {step} ---")
        result = command_execution_replay(step=step)
        print(result)
    
    # Demonstrate graphical format
    print("\n--- Graphical Replay ---")
    result = command_execution_replay(step=3, format="graphical")
    print(result)

def demo_command_handling():
    """Demonstrate handling commands through the command interface"""
    print("\n===== Command Handling Demo =====")
    
    # Setup test environment
    history, graph = create_sample_execution_history()
    src.cursor_commands.current_graph = graph
    src.cursor_commands.current_execution_history = history
    src.cursor_commands.current_state = history[3]["state"]
    
    # Test commands
    commands = [
        "/lg inspect-rich --format table",
        "/lg inspect-rich --field user.preferences",
        "/lg visualize-rich --type execution",
        "/lg visualize-rich --focus validate_data",
        "/lg diff-rich --state1 0 --state2 4",
        "/lg replay --step 2",
        "/lg timeline-rich --format detailed"
    ]
    
    for cmd in commands:
        print(f"\n>>> {cmd}")
        result = handle_command(cmd)
        print(result)

def run_all_demos():
    """Run all demonstration functions"""
    demo_rich_state_inspection()
    demo_rich_graph_visualization()
    demo_rich_diff_visualization()
    demo_execution_replay()
    demo_command_handling()

if __name__ == "__main__":
    print("=== Rich Visualizations Demo for Cursor AI Command Palette ===")
    run_all_demos()
    print("\nDemo completed. Sample visualizations have been saved to the current directory.") 