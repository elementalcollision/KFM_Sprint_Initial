# Getting Started with KFM Debugging Tools

This guide will help you get started with the KFM debugging toolkit for LangGraph applications. We'll cover installation, basic setup, and your first debugging session.

## Installation

### Prerequisites

Before installing the KFM debugging tools, make sure you have:

- Python 3.9 or higher
- LangGraph installed (0.0.43 or higher)

### Installing the Package

Install the KFM debugging toolkit using pip:

```bash
pip install kfm-debugging-tools
```

Or add it to your project's requirements:

```bash
pip install -e /path/to/kfm-debugging-tools
```

## Basic Setup

### Importing the Debugger

To use the KFM debugging tools in your project, import the necessary components:

```python
from kfm_debugging import Debugger, LogLevel, VisualizationMode
```

### Creating a Debugger Instance

Initialize a debugger instance with your LangGraph:

```python
from langgraph.graph import StateGraph

# Define your StateGraph
graph = StateGraph(...)

# Create a debugger with default settings
debugger = Debugger(graph)

# Or customize your debugger
debugger = Debugger(
    graph,
    log_level=LogLevel.INFO,
    visualization_mode=VisualizationMode.RICH,
    enable_breakpoints=True,
    state_tracking=True
)
```

## Basic Usage

### Running Your Graph with Debugging

Once the debugger is configured, execute your graph with debugging enabled:

```python
# Initialize input state
state = {"input": "Your input here"}

# Run graph with debugging enabled
result = debugger.run(state)

# Access the execution result
print(result)
```

### Viewing Execution Logs

By default, logs are printed to stdout. You can customize the log destination:

```python
debugger.configure_logger(
    log_file="debug_output.log",
    console_output=True
)
```

### Visualizing the Graph

Visualize your graph structure:

```python
# Generate a simple visualization
debugger.visualize_graph()

# Save to a file
debugger.visualize_graph(output_file="graph.png")

# Use rich visualization mode
debugger.visualize_graph(rich=True)
```

### Tracking State Changes

Monitor how state changes during execution:

```python
# Enable state tracking
debugger.enable_state_tracking()

# After running your graph
debugger.show_state_history()

# Compare states between steps
debugger.show_state_diff(step_index=2)  # Show diff between steps 1 and 2
```

## Using Breakpoints

Control execution with breakpoints:

```python
# Add a simple breakpoint at a specific node
debugger.add_breakpoint("node_name")

# Add a conditional breakpoint
debugger.add_breakpoint(
    "node_name",
    condition=lambda state: "error" in state,
    action=lambda state: print(f"Breakpoint hit with state: {state}")
)

# Run with breakpoints enabled
debugger.run(state)
```

## Error Handling

Leverage enhanced error handling:

```python
try:
    result = debugger.run(state)
except Exception as e:
    # Get contextual error information and suggestions
    error_context = debugger.get_error_context(e)
    print(f"Error suggestions: {error_context.suggestions}")
    
    # View the state at the time of the error
    print(f"State at error: {error_context.state}")
```

## Next Steps

Now that you have the basics, you can explore more advanced features:

- [Logger Configuration](logger_configuration.md) for customizing log output
- [State Difference Visualization](state_diff_visualization.md) for detailed state analysis
- [Breakpoint System](breakpoint_system.md) for advanced execution control
- [Graph Visualization](graph_visualization.md) for rich graph visualizations
- [Error Suggestions](error_suggestions.md) for intelligent troubleshooting

Check out the [Examples](../examples/index.md) section for practical demonstrations of these features. 