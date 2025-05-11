# Basic Debugging Tutorial

This tutorial will guide you through a basic debugging session using the KFM debugging tools with a simple LangGraph application. By the end, you'll be familiar with the fundamental debugging techniques.

## Prerequisites

Before starting this tutorial, make sure you have:

- Python 3.9 or higher installed
- LangGraph 0.0.43 or higher installed
- The KFM debugging tools installed (`pip install kfm-debugging-tools`)

## Step 1: Setting Up a Simple Graph

First, let's create a simple LangGraph application that we can debug:

```python
# simple_graph.py
from langgraph.graph import StateGraph

# Define state model (simple dictionary in this example)
state_model = {}

# Define nodes/functions in the graph
def input_parser(state):
    """Parse the input and add a 'parsed_input' field."""
    state["parsed_input"] = state["input"].strip().lower()
    return state

def calculator(state):
    """Process the input as a calculation."""
    try:
        expression = state["parsed_input"]
        result = eval(expression)
        state["result"] = result
        state["is_calculation"] = True
    except:
        state["is_calculation"] = False
    return state

def responder(state):
    """Generate a response based on the calculation."""
    if state.get("is_calculation", False):
        state["response"] = f"The result is: {state['result']}"
    else:
        state["response"] = "I couldn't process that as a calculation."
    return state

# Define the graph
def build_graph():
    graph = StateGraph(state_model)
    
    # Add nodes
    graph.add_node("input_parser", input_parser)
    graph.add_node("calculator", calculator)
    graph.add_node("responder", responder)
    
    # Add edges
    graph.add_edge("input_parser", "calculator")
    graph.add_edge("calculator", "responder")
    
    # Set entry and exit points
    graph.set_entry_point("input_parser")
    graph.set_finish_point("responder")
    
    return graph

# Create the graph
graph = build_graph()

# Run the graph with a sample input
if __name__ == "__main__":
    result = graph.invoke({"input": "2 + 3"})
    print(result)
```

Save this file and run it to make sure it works:

```bash
python simple_graph.py
```

You should see output that includes: `{'input': '2 + 3', 'parsed_input': '2 + 3', 'result': 5, 'is_calculation': True, 'response': 'The result is: 5'}`

## Step 2: Adding Basic Debugging

Now, let's add the KFM debugging tools to this graph:

```python
# simple_graph_debug.py
# Import the original graph code
from simple_graph import build_graph

# Import the debugging tools
from kfm_debugging import Debugger, LogLevel

# Create the graph
graph = build_graph()

# Initialize the debugger
debugger = Debugger(
    graph,
    log_level=LogLevel.INFO,
    state_tracking=True
)

# Run the graph with debugging
if __name__ == "__main__":
    # Initial state
    initial_state = {"input": "2 + 3"}
    
    # Run with debugging
    result = debugger.run(initial_state)
    print("Final state:", result)
```

Run this script to see the basic debug output:

```bash
python simple_graph_debug.py
```

You should see log output for each step of the graph execution.

## Step 3: Visualizing State Changes

Let's examine how the state changes during execution:

```python
# Add to simple_graph_debug.py
if __name__ == "__main__":
    # Initial state
    initial_state = {"input": "2 + 3"}
    
    # Run with debugging
    result = debugger.run(initial_state)
    print("Final state:", result)
    
    # Show state history
    print("\n===== State History =====")
    debugger.show_state_history()
    
    # Show state differences between steps
    print("\n===== State Differences =====")
    debugger.show_state_diff(step_index=1)  # Diff between initial state and after input_parser
    debugger.show_state_diff(step_index=2)  # Diff between after input_parser and after calculator
    debugger.show_state_diff(step_index=3)  # Diff between after calculator and after responder
```

Run this modified script to see the state changes:

```bash
python simple_graph_debug.py
```

## Step 4: Visualizing the Graph

Let's visualize the graph structure:

```python
# Add to simple_graph_debug.py
if __name__ == "__main__":
    # ... existing code ...
    
    # Visualize the graph
    print("\n===== Visualizing Graph =====")
    debugger.visualize_graph(output_file="graph.png")
    print("Graph visualization saved to 'graph.png'")
```

Run the script and check the generated graph image:

```bash
python simple_graph_debug.py
```

## Step 5: Adding Breakpoints

Now, let's add breakpoints to control execution:

```python
# Add to simple_graph_debug.py
if __name__ == "__main__":
    # Add a simple breakpoint
    debugger.add_breakpoint("calculator")
    
    # Add a conditional breakpoint
    debugger.add_breakpoint(
        "responder",
        condition=lambda state: state.get("is_calculation", False) == False,
        action=lambda state: print(f"Breakpoint hit: Calculation failed")
    )
    
    # Initial state that will cause the calculation to fail
    initial_state = {"input": "2 + x"}
    
    # Run with breakpoints enabled
    print("\n===== Running with Breakpoints =====")
    result = debugger.run(initial_state)
    print("Final state:", result)
```

Run the script to see how breakpoints affect execution:

```bash
python simple_graph_debug.py
```

## Step 6: Capturing and Analyzing Errors

Let's introduce an error and see how the debugging tools help:

```python
# Create a new script for error testing
# error_graph_debug.py

from simple_graph import build_graph
from kfm_debugging import Debugger, LogLevel

# Create the graph
graph = build_graph()

# Initialize the debugger
debugger = Debugger(
    graph,
    log_level=LogLevel.DEBUG,  # More verbose logging
    state_tracking=True
)

# Modify the calculator function to introduce a potential error
def calculator_with_error(state):
    """Process the input as a calculation with potential errors."""
    expression = state["parsed_input"]
    
    # Intentional error: trying to access a key that doesn't exist
    if state["nonexistent_key"] == "something":
        pass
        
    result = eval(expression)
    state["result"] = result
    state["is_calculation"] = True
    return state

# Replace the calculator node with our error-prone version
graph.update_node("calculator", calculator_with_error)

# Run with error handling
if __name__ == "__main__":
    initial_state = {"input": "2 + 3"}
    
    try:
        result = debugger.run(initial_state)
        print("Final state:", result)
    except Exception as e:
        print(f"Error caught: {type(e).__name__}: {e}")
        
        # Get error context and suggestions
        error_context = debugger.get_error_context(e)
        print("\n===== Error Context =====")
        print(f"Error occurred in node: {error_context.node}")
        print(f"State at error: {error_context.state}")
        print("\n===== Error Suggestions =====")
        for suggestion in error_context.suggestions:
            print(f"- {suggestion}")
```

Run this script to see how errors are handled:

```bash
python error_graph_debug.py
```

## Step 7: Rich Visualization

Finally, let's use rich visualization for a better debugging experience:

```python
# rich_debug.py

from simple_graph import build_graph
from kfm_debugging import Debugger, LogLevel, VisualizationMode

# Create the graph
graph = build_graph()

# Initialize the debugger with rich visualization
debugger = Debugger(
    graph,
    log_level=LogLevel.INFO,
    state_tracking=True,
    visualization_mode=VisualizationMode.RICH
)

if __name__ == "__main__":
    # Initial state
    initial_state = {"input": "2 + 3"}
    
    # Run with debugging
    result = debugger.run(initial_state)
    
    # Show rich visualization of state history
    print("\n===== Rich State History =====")
    debugger.show_state_history()
    
    # Show rich visualization of state differences
    print("\n===== Rich State Differences =====")
    debugger.show_state_diff(step_index=2)  # Diff after calculator
    
    # Show execution timeline
    print("\n===== Execution Timeline =====")
    debugger.show_execution_timeline()
```

Run this script to see the rich visualizations:

```bash
python rich_debug.py
```

## Summary

In this tutorial, you've learned how to:

1. Set up basic debugging for a LangGraph application
2. Track and visualize state changes throughout execution
3. Visualize the graph structure
4. Use breakpoints to control execution
5. Handle and analyze errors with contextual information
6. Use rich visualizations for a better debugging experience

## Next Steps

Now that you're familiar with the basics, you might want to explore:

- [Advanced Debugging Tutorial](advanced_debugging_tutorial.md)
- [State History Tracking](../user_guides/state_history_tracking.md)
- [Breakpoint System](../user_guides/breakpoint_system.md)
- [Error Handling and Recovery](../user_guides/error_handling.md)

For more details on any specific feature, refer to the [User Guides](../user_guides/index.md). 