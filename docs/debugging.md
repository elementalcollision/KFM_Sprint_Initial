# Debugging Utilities

This document describes the debugging utilities available for tracking state changes, comparing states, and tracing execution in KFM applications.

## Available Debugging Functions

The `src.debugging` module provides various functions for debugging KFM applications:

- `debug_node_execution`: Track state changes in a node
- `diff_states`: Compare two states and return differences (Enhanced)
- `wrap_node_for_debug`: Wrap a node function to add debugging output
- `debug_graph_execution`: Trace execution through the entire graph
- `step_through_execution`: Step-by-step execution of the graph with manual intervention
- `extract_subgraph_for_debugging`: Extract a subgraph for targeted debugging

## Enhanced State Difference Visualization

The `diff_states` function has been enhanced to provide richer output and visual diffs of state changes between nodes.

### Usage

```python
from src.debugging import diff_states, visualize_diff

# Basic usage
result = diff_states(state_before, state_after)

# Advanced usage with all options
result = diff_states(
    state_before, 
    state_after, 
    mode='detailed',        # Use 'basic', 'detailed', or 'comprehensive'
    max_depth=10,           # Maximum recursion depth for nested structures
    use_colors=True,        # Use color coding in the output
    show_unchanged=False    # Whether to include unchanged fields
)

# Visualize the results in different formats
standard_view = visualize_diff(result)
table_view = visualize_diff(result, format_type='table')
json_view = visualize_diff(result, format_type='json')
```

### Comparison Modes

The diff_states function supports three different comparison modes:

1. **basic**: Simple comparison of top-level attributes. Does not generate visualization.
2. **detailed**: Recursive comparison of nested structures with path tracking.
3. **comprehensive**: Like detailed, but with additional information and the deepest comparison.

### Visualization Formats

The `visualize_diff` function supports three output formats:

1. **standard**: A human-readable format with symbols and indentation.
2. **table**: A tabular format showing path, before, and after values.
3. **json**: JSON format for machine processing or storing results.

### Color Coding and Symbols

The visualization uses symbols and color coding to indicate the type of change:

- `+` (Green): Added fields
- `-` (Red): Removed fields
- `~` (Yellow): Modified fields
- ` ` (Default): Unchanged fields

Colors are automatically disabled in non-terminal environments.

### Example Output

#### Standard Format

```
DIFF VISUALIZATION:
===================
+ user.new_field: "This is a new field"
- user.removed_field: "This field was removed"
~ user.modified_field: "old value" -> "new value"
~ user.count: 5 -> 10
```

#### Table Format

```
┌───────┬────────────────────────┬─────────────────────┬─────────────────────┐
│ Type  │ Path                   │ Before              │ After               │
├───────┼────────────────────────┼─────────────────────┼─────────────────────┤
│ +a    │ user.new_field         │                     │ This is a new field │
│ -r    │ user.removed_field     │ This field was rem… │                     │
│ ~m    │ user.modified_field    │ old value           │ new value           │
│ ~m    │ user.count             │ 5                   │ 10                  │
└───────┴────────────────────────┴─────────────────────┴─────────────────────┘
```

### Smart Truncation

Large objects are automatically truncated to avoid overwhelming output:

- Long strings are truncated with "... (truncated)" suffix
- Large lists show only the first N items followed by "... (X more items)"
- Large dictionaries show only the first N key-value pairs followed by a summary
- Large sets are converted to lists for display and truncated similarly

### Nested Structure Support

The enhanced diff function can handle:

- Deeply nested dictionaries with path tracking (e.g., `user.preferences.notifications.email`)
- Lists with index tracking (e.g., `user.history[2].action`)
- Sets with proper handling of additions and removals
- Mixed structures with arbitrary nesting

## Demo Script

A demonstration script is provided in `examples/state_diff_demo.py` that shows:

1. Basic state comparison
2. Nested structure comparison
3. Different visualization formats
4. Handling of large states with truncation
5. Comparison of complex KFM agent states

Run the demo with:

```bash
python examples/state_diff_demo.py
```

## Integration with Other Debugging Tools

The enhanced diff functionality is integrated with:

- `debug_node_execution`: Now uses the enhanced diff with visualization
- `debug_graph_execution`: Uses enhanced diff to show state changes between nodes
- `step_through_execution`: Uses enhanced diff to show state changes at each step 

## Breakpoint System

The KFM framework includes a comprehensive breakpoint system for debugging graph execution. This allows you to pause execution at specific nodes and examine or modify state before continuing.

### Setting Breakpoints

You can set breakpoints on specific nodes:

```python
from src.debugging import set_breakpoint, clear_breakpoint

# Set a simple breakpoint on a node
breakpoint_id = set_breakpoint("node_name", description="Stop at this node")

# Set a conditional breakpoint
breakpoint_id = set_breakpoint(
    "node_name",
    condition="state.get('key') == 'value'",
    description="Stop when condition is met"
)

# Clear a breakpoint
clear_breakpoint(breakpoint_id)

# Clear all breakpoints on a node
clear_node_breakpoints("node_name")

# Clear all breakpoints
clear_all_breakpoints()
```

### Breakpoint Conditions

Conditional breakpoints allow you to pause execution only when certain conditions are met:

- Conditions are Python expressions evaluated against the current state
- The state is available as the `state` variable in the expression
- A helper function `get(path, default=None)` is provided for safely accessing nested properties
- Example: `"state.get('metrics.score') > 0.8"`

### Running with Breakpoints

There are several ways to use breakpoints in your execution:

#### Basic Breakpoint Execution

```python
from src.debugging import run_with_breakpoints

def step_handler(node_name, index, state):
    print(f"Breakpoint hit at {node_name}")
    # Return control command
    return "continue"  # or "step", "run_to node_name", "step_back", "quit"

final_state = run_with_breakpoints(app, initial_state, step_handler)
```

#### Interactive Debugging Session

```python
from src.debugging import interactive_debug

# Start an interactive CLI debugging session
final_state = interactive_debug(app, initial_state)
```

The interactive session provides a command prompt with the following commands:

- `s, step` - Execute current node and pause
- `c, continue` - Continue execution until next breakpoint
- `r NODE, run_to NODE` - Run until specified node
- `b, back` - Step back to previous node
- `list` - List all nodes in the graph
- `bp NODE` - Set breakpoint on a node
- `bp NODE COND` - Set conditional breakpoint
- `bp clear [ID]` - Clear a breakpoint or all if no ID
- `bp list` - List all breakpoints
- `state` - Show current state
- `diff` - Show changes from previous node
- `timeline` - Show execution timeline
- `q, quit` - Terminate execution
- `help` - Show help message

### Execution Control Functions

For more programmatic control, you can use these functions:

```python
from src.debugging import step_forward, step_backward, run_to_node, run_to_condition

# Execute one node and get new state
new_state, new_index = step_forward(app, current_state, current_index)

# Go back to previous node
previous_state, previous_index = step_backward(current_state, current_index)

# Run until a specific node
new_state, new_index = run_to_node(app, current_state, current_index, "target_node")

# Run until a condition is met
new_state, new_index = run_to_condition(app, current_state, current_index, 
                                      "state.get('done') == True")
```

### Breakpoint Management

Additional functions for managing breakpoints:

```python
from src.debugging import list_breakpoints, get_breakpoint, enable_breakpoint, disable_breakpoint

# List all breakpoints
breakpoints = list_breakpoints()

# List breakpoints on a specific node
node_breakpoints = list_breakpoints("node_name")

# Get breakpoint details
bp = get_breakpoint(breakpoint_id)

# Enable/disable breakpoints
enable_breakpoint(breakpoint_id)
disable_breakpoint(breakpoint_id)
```

### Example Usage

A complete example showing how to use breakpoints:

```python
from src.debugging import set_breakpoint, clear_all_breakpoints, run_with_breakpoints

# Clear any existing breakpoints
clear_all_breakpoints()

# Set breakpoints
set_breakpoint("parse_query", description="Stop before parsing")
set_breakpoint("execute_search", condition="state.get('query_type') == 'complex'", 
              description="Stop on complex queries")

# Define step handler
def step_handler(node_name, index, state):
    print(f"Breakpoint hit at {node_name}")
    print(f"Current state: {state}")
    
    # Let user decide what to do
    action = input("Enter action (c=continue, s=step, q=quit): ")
    if action == "c":
        return "continue"
    elif action == "s":
        return "step"
    elif action == "q":
        return "quit"
    else:
        return "step"  # Default to step

# Run with breakpoints
final_state = run_with_breakpoints(graph, initial_state, step_handler)
```

For a more complete demonstration, see the example in `examples/breakpoint_demo.py`. 