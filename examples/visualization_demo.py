"""
Graph Visualization Demo

This script demonstrates the various graph visualization capabilities
of the KFM framework, including:

1. Basic graph visualization with different layouts
2. Execution path visualization
3. Performance timing visualization
4. Error visualization
5. Interactive visualization
"""

import sys
import os
import time
import random
import argparse
from typing import Dict, List, Any

# Add src directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END

from src.visualization import (
    visualize_graph,
    visualize_graph_with_execution,
    visualize_graph_with_timing,
    visualize_graph_with_errors,
    create_interactive_visualization,
    visualize_performance_hotspots,
    visualize_breakpoints,
)

# Define a simple example graph for demonstration
def create_demo_graph():
    """Create a sample graph for demonstration purposes."""
    # Define nodes
    def start_node(state):
        state["counter"] = 0
        state["path"] = ["start"]
        return {"counter": state["counter"], "path": state["path"]}
    
    def process_node(state):
        state["counter"] += 1
        state["path"].append("process")
        return {"counter": state["counter"], "path": state["path"]}
    
    def decision_node(state):
        # Simple routing logic
        if state.get("counter", 0) > 2:
            state["path"].append("decision")
            return "finish"
        else:
            state["path"].append("decision")
            return "loop"
    
    def loop_node(state):
        state["counter"] += 1
        state["path"].append("loop")
        return {"counter": state["counter"], "path": state["path"]}
    
    def finish_node(state):
        state["path"].append("finish")
        return {"counter": state["counter"], "path": state["path"]}
    
    # Build the graph
    builder = StateGraph(state_type=Dict)
    
    # Add nodes
    builder.add_node("start", start_node)
    builder.add_node("process", process_node)
    builder.add_node("decision", decision_node)
    builder.add_node("loop", loop_node)
    builder.add_node("finish", finish_node)
    
    # Add edges
    builder.set_entry_point("start")
    builder.add_edge("start", "process")
    builder.add_edge("process", "decision")
    builder.add_conditional_edges("decision", decision_node)
    builder.add_edge("loop", "process")
    builder.add_edge("finish", END)
    
    # Compile
    return builder.compile()

def simulate_execution(graph, include_timing=True, add_error=False):
    """
    Simulate graph execution and return execution data.
    
    Args:
        graph: The graph to execute
        include_timing: Whether to include timing data
        add_error: Whether to simulate an error during execution
        
    Returns:
        List of execution data entries
    """
    execution_data = []
    state = {}
    
    # Get the nodes from the graph
    nodes = list(graph.graph.nodes)
    nodes = [node for node in nodes if node != END]
    
    # Keep track of visited nodes (to prevent loops in demo)
    visited = set()
    current = graph.get_entry_point()
    
    while current and current != END:
        # Skip if already visited 3 times (to prevent infinite loops)
        if current in visited and len([e for e in execution_data if e["node"] == current]) >= 3:
            break
            
        visited.add(current)
        
        # Create execution entry
        entry = {"node": current}
        
        if include_timing:
            # Simulate execution timing (random for demo)
            start_time = time.time()
            
            # Simulate work (longer for process node)
            if current == "process":
                time.sleep(0.2)
            else:
                time.sleep(0.05)
                
            # Record duration
            duration = time.time() - start_time
            entry["duration"] = duration
        
        # Simulate random error if requested
        if add_error and current == "loop" and random.random() < 0.7:
            entry["success"] = False
            entry["error"] = {
                "type": "RuntimeError",
                "message": "Simulated error in loop node"
            }
            execution_data.append(entry)
            break
        
        # Add to execution data
        entry["success"] = True
        execution_data.append(entry)
        
        # Get next node
        try:
            # Use simple simulation for demo purposes
            if current == "start":
                current = "process"
            elif current == "process":
                current = "decision"
            elif current == "decision":
                if len([e for e in execution_data if e["node"] == "process"]) > 2:
                    current = "finish"
                else:
                    current = "loop"
            elif current == "loop":
                current = "process"
            elif current == "finish":
                current = END
            else:
                current = None
        except Exception as e:
            # Add error entry
            entry = {
                "node": current,
                "success": False,
                "error": str(e)
            }
            execution_data.append(entry)
            break
    
    return execution_data

def create_sample_breakpoints():
    """Create sample breakpoints for demonstration."""
    return [
        {
            "id": "bp1",
            "node": "process",
            "enabled": True,
            "condition": None
        },
        {
            "id": "bp2",
            "node": "decision",
            "enabled": True,
            "condition": "state['counter'] > 1"
        }
    ]

def main():
    parser = argparse.ArgumentParser(description="Demonstration of graph visualization capabilities")
    parser.add_argument("--output-dir", default="examples/visual_output", help="Directory to save visualizations")
    parser.add_argument("--interactive", action="store_true", help="Generate interactive HTML visualizations")
    parser.add_argument("--show-all", action="store_true", help="Generate all visualization types")
    parser.add_argument("--layout", default="hierarchical", choices=["hierarchical", "circular", "force"], 
                        help="Layout algorithm for graph visualization")
    
    args = parser.parse_args()
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Create demo graph
    graph = create_demo_graph()
    
    # Basic visualization
    print(f"Generating basic graph visualization with {args.layout} layout...")
    fig = visualize_graph(graph, layout=args.layout, title=f"Demo Graph ({args.layout} layout)")
    output_path = os.path.join(args.output_dir, f"basic_graph_{args.layout}.png")
    fig.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Basic visualization saved to {output_path}")
    
    # Execution path visualization
    print("Generating execution path visualization...")
    execution_data = simulate_execution(graph, include_timing=False)
    execution_path = [entry["node"] for entry in execution_data]
    fig = visualize_graph_with_execution(
        graph, 
        execution_path,
        layout=args.layout,
        title="Graph Execution Path"
    )
    output_path = os.path.join(args.output_dir, f"execution_path_{args.layout}.png")
    fig.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Execution path visualization saved to {output_path}")
    
    # Performance timing visualization
    print("Generating performance timing visualization...")
    execution_data_with_timing = simulate_execution(graph, include_timing=True)
    fig = visualize_graph_with_timing(
        graph,
        execution_data_with_timing,
        layout=args.layout,
        title="Graph Execution Timing"
    )
    output_path = os.path.join(args.output_dir, f"timing_{args.layout}.png")
    fig.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Timing visualization saved to {output_path}")
    
    # Error visualization
    print("Generating error visualization...")
    execution_data_with_error = simulate_execution(graph, include_timing=True, add_error=True)
    error_data = {}
    for entry in execution_data_with_error:
        if entry.get("success") is False:
            error_data[entry["node"]] = entry.get("error", "Unknown error")
    
    fig = visualize_graph_with_errors(
        graph,
        error_data,
        layout=args.layout,
        title="Graph with Errors"
    )
    output_path = os.path.join(args.output_dir, f"errors_{args.layout}.png")
    fig.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Error visualization saved to {output_path}")
    
    # Breakpoint visualization
    print("Generating breakpoint visualization...")
    breakpoints = create_sample_breakpoints()
    fig = visualize_breakpoints(
        graph,
        breakpoints,
        layout=args.layout,
        title="Graph with Breakpoints"
    )
    output_path = os.path.join(args.output_dir, f"breakpoints_{args.layout}.png")
    fig.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Breakpoint visualization saved to {output_path}")
    
    # Performance hotspots visualization
    print("Generating performance hotspots visualization...")
    fig = visualize_performance_hotspots(
        graph,
        execution_data_with_timing,
        layout=args.layout,
        title="Performance Hotspots",
        highlight_threshold=0.1
    )
    output_path = os.path.join(args.output_dir, f"hotspots_{args.layout}.png")
    fig.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Hotspots visualization saved to {output_path}")
    
    # Generate interactive visualizations if requested
    if args.interactive:
        print("Generating interactive visualizations...")
        
        # Interactive basic visualization
        html_path = create_interactive_visualization(
            graph,
            output_path=os.path.join(args.output_dir, "interactive_basic.html"),
            title="Interactive Graph Visualization"
        )
        print(f"Interactive basic visualization saved to {html_path}")
        
        # Interactive execution path visualization
        html_path = create_interactive_visualization(
            graph,
            execution_path=execution_path,
            output_path=os.path.join(args.output_dir, "interactive_execution.html"),
            title="Interactive Execution Path Visualization"
        )
        print(f"Interactive execution path visualization saved to {html_path}")
        
        # Interactive timing visualization
        node_timings = {entry["node"]: entry["duration"] for entry in execution_data_with_timing if "duration" in entry}
        html_path = create_interactive_visualization(
            graph,
            execution_path=execution_path,
            node_timings=node_timings,
            output_path=os.path.join(args.output_dir, "interactive_timing.html"),
            title="Interactive Timing Visualization"
        )
        print(f"Interactive timing visualization saved to {html_path}")
        
        # Interactive error visualization with both approaches
        html_path = create_interactive_visualization(
            graph,
            execution_path=execution_path,
            error_nodes=[k for k in error_data.keys()],
            output_path=os.path.join(args.output_dir, "interactive_errors.html"),
            title="Interactive Error Visualization"
        )
        print(f"Interactive error visualization saved to {html_path}")
        
        html_path = visualize_graph_with_errors(
            graph,
            error_data,
            interactive=True,
            output_path=os.path.join(args.output_dir, "interactive_errors_detailed.html"),
            title="Interactive Detailed Error Visualization"
        )
        print(f"Interactive detailed error visualization saved to {html_path}")
    
    print("\nAll visualizations generated successfully!")
    print(f"Output directory: {os.path.abspath(args.output_dir)}")

if __name__ == "__main__":
    main() 