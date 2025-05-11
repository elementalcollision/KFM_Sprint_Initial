# Graph Visualization System

The KFM framework includes a comprehensive graph visualization system that helps you understand, debug, and optimize your LangGraph applications. This system provides multiple visualization types, from simple static images to rich interactive HTML visualizations.

## Basic Usage

```python
from src.visualization import visualize_graph

# Simple graph visualization
fig = visualize_graph(graph, layout='hierarchical', title="My Graph")
fig.savefig("my_graph.png", dpi=300)
```

## Visualization Types

### Basic Graph Visualization

Visualize the structure of your graph with different layout algorithms:

```python
from src.visualization import visualize_graph

# Basic visualization with hierarchical layout
fig = visualize_graph(graph, layout='hierarchical')

# Try different layouts
fig = visualize_graph(graph, layout='circular')
fig = visualize_graph(graph, layout='force')
```

### Execution Path Visualization

Visualize how your graph was executed, highlighting completed nodes and execution paths:

```python
from src.visualization import visualize_graph_with_execution

# Create a list of executed node names in order
execution_path = ["start", "process", "decision", "loop", "process", "decision", "finish"]

# Visualize the execution path
fig = visualize_graph_with_execution(graph, execution_path)

# You can also highlight the current node and any error nodes
fig = visualize_graph_with_execution(
    graph, 
    execution_path,
    current_node="process",
    error_nodes=["loop"]
)
```

### Performance Visualization

Visualize execution timing to identify performance bottlenecks:

```python
from src.visualization import visualize_graph_with_timing, visualize_performance_hotspots

# Create execution data with timing information
execution_data = [
    {"node": "start", "duration": 0.05, "success": True},
    {"node": "process", "duration": 1.2, "success": True},
    {"node": "decision", "duration": 0.1, "success": True},
    # ... more execution data
]

# Visualize timing information
fig = visualize_graph_with_timing(graph, execution_data)

# Highlight performance hotspots (nodes taking longer than 0.5 seconds)
fig = visualize_performance_hotspots(
    graph, 
    execution_data, 
    highlight_threshold=0.5
)
```

### Error Visualization

Visualize errors in your graph execution:

```python
from src.visualization import visualize_graph_with_errors

# Create error data (mapping node names to error information)
error_data = {
    "process": "Invalid input format",
    "loop": {"type": "RuntimeError", "message": "Maximum iterations exceeded"}
}

# Visualize errors
fig = visualize_graph_with_errors(graph, error_data)
```

### Breakpoint Visualization

Visualize breakpoints set in your graph:

```python
from src.visualization import visualize_breakpoints

# Create breakpoint data
breakpoints = [
    {"id": "bp1", "node": "process", "enabled": True, "condition": None},
    {"id": "bp2", "node": "decision", "enabled": True, "condition": "state['counter'] > 3"}
]

# Visualize breakpoints
fig = visualize_breakpoints(graph, breakpoints)
```

## Interactive Visualization

For more detailed exploration, you can create interactive HTML visualizations:

```python
from src.visualization import create_interactive_visualization

# Create interactive visualization
html_path = create_interactive_visualization(
    graph,
    execution_path=execution_path,
    error_nodes=["loop"],
    node_timings={"process": 1.2, "decision": 0.1},
    output_path="graph_visualization.html",
    title="Interactive Graph Visualization"
)

# Most visualization functions also have an interactive mode
html_path = visualize_graph_with_errors(
    graph,
    error_data,
    interactive=True,
    output_path="interactive_errors.html"
)
```

Interactive visualizations provide:
- Zooming and panning
- Node tooltips with detailed information
- Color coding for execution status, timings, and errors
- Interactive graph physics for easy exploration

## Customization Options

The visualization system supports many customization options:

```python
fig = visualize_graph(
    graph,
    layout='hierarchical',     # Layout algorithm
    title="My Graph",          # Title for the visualization
    node_size=1000,            # Size of nodes
    node_colors={              # Custom color mapping
        'normal': '#77AADD',
        'executed': '#99DD99'
    },
    show_labels=True,          # Whether to show node labels
    label_font_size=12,        # Font size for labels
    figsize=(16, 10),          # Figure size (width, height)
    dpi=150                    # Resolution
)
```

## Saving Visualizations

Save visualizations to different formats:

```python
# Save as PNG (default)
fig.savefig("graph.png", dpi=300, bbox_inches='tight')

# Save as SVG (vector format, good for publication)
fig.savefig("graph.svg", format="svg", bbox_inches='tight')

# Save as PDF
fig.savefig("graph.pdf", format="pdf", bbox_inches='tight')

# Save interactive HTML directly from visualization functions
html_path = create_interactive_visualization(
    graph,
    output_path="graph.html"
)
```

## Example Script

For a complete example, see the demonstration script at `examples/visualization_demo.py`:

```bash
# Run with default options
python examples/visualization_demo.py

# Generate interactive HTML visualizations
python examples/visualization_demo.py --interactive

# Use different layout algorithms
python examples/visualization_demo.py --layout circular
python examples/visualization_demo.py --layout force
```

## Advanced Features

### Custom Layouts

Create custom layouts for your graph:

```python
import networkx as nx
from src.visualization import visualize_graph

# Extract graph structure
G = visualize_graph.extract_graph_structure(graph)

# Create a custom layout (x, y positions for each node)
custom_layout = {
    "start": (0, 0),
    "process": (1, 0),
    "decision": (2, 0),
    # ... positions for other nodes
}

# Use custom layout
fig = visualize_graph(graph, layout=custom_layout)
```

### Combining with Debugging Features

The visualization system integrates with the debugging system:

```python
from src.debugging import step_through_execution_with_history
from src.visualization import visualize_execution_path

# Execute graph with history tracking
result, trace_history = step_through_execution_with_history(graph, initial_state)

# Visualize the execution path from trace history
fig = visualize_execution_path(trace_history, graph)
```

For more details on the available visualization functions and options, see the API documentation for the `src.visualization` module. 