"""
Breakpoint Demonstration Script

This script demonstrates the breakpoint system for LangGraph execution.
It shows how to:
1. Set breakpoints on specific nodes
2. Set conditional breakpoints
3. Use the interactive debugging session
4. Step forward, backward and run to specific nodes
"""

import sys
import os
import json

# Add src directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END
from src.debugging import (
    set_breakpoint,
    clear_all_breakpoints,
    list_breakpoints,
    run_with_breakpoints,
    interactive_debug,
    configure_debug_level
)

# Configure more verbose debug output
configure_debug_level("DEBUG")

# Define a simple demo graph
def create_demo_graph():
    """Create a simple graph for demonstration."""
    
    # Define the nodes
    def node_a(state):
        """First node that adds a greeting."""
        print("Executing node_a")
        state["greeting"] = "Hello"
        return state
    
    def node_b(state):
        """Second node that adds a name."""
        print("Executing node_b")
        state["name"] = "World"
        return state
    
    def node_c(state):
        """Third node that combines greeting and name."""
        print("Executing node_c")
        state["message"] = f"{state['greeting']}, {state['name']}!"
        return state
    
    def node_d(state):
        """Fourth node that adds an exclamation."""
        print("Executing node_d")
        state["excited_message"] = f"{state['message']} How exciting!"
        return state
    
    def node_e(state):
        """Fifth node that adds a farewell."""
        print("Executing node_e")
        state["farewell"] = f"Goodbye, {state['name']}!"
        return state
    
    # Create graph
    graph = StateGraph(nodes={"node_a": node_a, "node_b": node_b, "node_c": node_c, 
                             "node_d": node_d, "node_e": node_e})
    
    # Add edges
    graph.add_edge("node_a", "node_b")
    graph.add_edge("node_b", "node_c")
    graph.add_edge("node_c", "node_d")
    graph.add_edge("node_d", "node_e")
    graph.add_edge("node_e", END)
    
    # Compile graph
    return graph.compile()

def demo_basic_breakpoints():
    """Demonstrate basic breakpoint functionality."""
    print("\n===== Basic Breakpoint Demo =====")
    
    # Clear any existing breakpoints
    clear_all_breakpoints()
    
    # Create graph
    graph = create_demo_graph()
    
    # Set breakpoints
    set_breakpoint("node_b", description="Stop at node_b")
    set_breakpoint("node_d", description="Stop at node_d")
    
    # List breakpoints
    print("\nConfigured breakpoints:")
    bp_list = list_breakpoints()
    for bp in bp_list:
        status = "enabled" if bp["enabled"] else "disabled"
        print(f"- {bp['node_name']}: {status} ({bp['description']})")
    
    # Define a simple step handler
    def step_handler(node_name, index, state):
        print(f"\n🛑 Breakpoint hit at {node_name}")
        print(f"Current state: {json.dumps(state, indent=2)}")
        
        action = input("Press Enter to continue, or type 'quit' to stop: ")
        if action.lower() == "quit":
            return "quit"
        return "continue"
    
    # Run with breakpoints
    print("\nStarting execution with breakpoints...")
    initial_state = {}
    final_state = run_with_breakpoints(graph, initial_state, step_handler)
    
    # Show final state
    if final_state:
        print("\nExecution completed!")
        print(f"Final state: {json.dumps(final_state, indent=2)}")
    else:
        print("\nExecution was terminated or failed.")

def demo_conditional_breakpoints():
    """Demonstrate conditional breakpoints."""
    print("\n===== Conditional Breakpoint Demo =====")
    
    # Clear any existing breakpoints
    clear_all_breakpoints()
    
    # Create graph
    graph = create_demo_graph()
    
    # Set conditional breakpoints
    set_breakpoint(
        "node_c", 
        condition="state.get('name') == 'World'", 
        description="Break when name is 'World'"
    )
    
    set_breakpoint(
        "node_e", 
        condition="'excited_message' in state and len(state['excited_message']) > 20", 
        description="Break when excited_message is long"
    )
    
    # List breakpoints
    print("\nConfigured conditional breakpoints:")
    bp_list = list_breakpoints()
    for bp in bp_list:
        status = "enabled" if bp["enabled"] else "disabled"
        print(f"- {bp['node_name']}: {status}")
        print(f"  Condition: {bp['condition']}")
        print(f"  Description: {bp['description']}")
    
    # Define a simple step handler
    def step_handler(node_name, index, state):
        print(f"\n🛑 Conditional breakpoint hit at {node_name}")
        print(f"Current state: {json.dumps(state, indent=2)}")
        
        action = input("Press Enter to continue, or type 'quit' to stop: ")
        if action.lower() == "quit":
            return "quit"
        return "continue"
    
    # Run with breakpoints
    print("\nStarting execution with conditional breakpoints...")
    initial_state = {}
    final_state = run_with_breakpoints(graph, initial_state, step_handler)
    
    # Show final state
    if final_state:
        print("\nExecution completed!")
        print(f"Final state: {json.dumps(final_state, indent=2)}")
    else:
        print("\nExecution was terminated or failed.")

def demo_interactive_debugging():
    """Demonstrate full interactive debugging session."""
    print("\n===== Interactive Debugging Demo =====")
    
    # Clear any existing breakpoints
    clear_all_breakpoints()
    
    # Create graph
    graph = create_demo_graph()
    
    # Set one initial breakpoint
    set_breakpoint("node_b", description="Initial breakpoint for demo")
    
    print("\nStarting interactive debugging session...")
    print("Type 'help' at the prompt to see available commands.")
    
    # Start interactive debugging
    initial_state = {}
    final_state = interactive_debug(graph, initial_state)
    
    # Show final state
    if final_state:
        print("\nInteractive debugging completed!")
        print(f"Final state: {json.dumps(final_state, indent=2)}")
    else:
        print("\nInteractive debugging was terminated or failed.")

if __name__ == "__main__":
    # Choose which demo to run
    print("Breakpoint Demonstration Script")
    print("1. Basic Breakpoints")
    print("2. Conditional Breakpoints")
    print("3. Interactive Debugging")
    
    choice = input("Enter your choice (1-3): ")
    
    if choice == "1":
        demo_basic_breakpoints()
    elif choice == "2":
        demo_conditional_breakpoints()
    elif choice == "3":
        demo_interactive_debugging()
    else:
        print("Invalid choice. Running all demos...")
        demo_basic_breakpoints()
        demo_conditional_breakpoints()
        demo_interactive_debugging() 