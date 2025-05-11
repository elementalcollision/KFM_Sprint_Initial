# State Difference Visualization

This guide explains how to use the state difference visualization features in the KFM debugging tools to effectively track and understand state changes during graph execution.

## Overview

State difference visualization is a powerful feature that helps you understand how state changes between steps in your graph execution. Key benefits include:

- **Identifying unexpected changes** - Spot state modifications that weren't intended
- **Debugging data flow** - Understand how data flows through your graph
- **Optimizing state manipulations** - Find inefficient state handling patterns
- **Localizing issues** - Pinpoint exactly where state becomes invalid

## Basic Usage

### Enabling State Tracking

Before you can visualize state differences, you need to enable state tracking:

```python
from kfm_debugging import Debugger

# Enable state tracking during initialization
debugger = Debugger(graph, state_tracking=True)

# Or enable it after initialization
debugger.enable_state_tracking()
```

### Visualizing State Differences

After running your graph with state tracking enabled, you can visualize state differences:

```python
# Run your graph
initial_state = {"input": "Your input here"}
result = debugger.run(initial_state)

# Show difference between two steps (e.g., steps 1 and 2)
debugger.show_state_diff(step_index=2)  # Shows diff between steps 1 and 2

# Show difference between arbitrary steps
debugger.show_state_diff(from_step=1, to_step=3)
```

### Understanding the Diff Display

The state diff visualization shows:

- **Added values** - New keys or values added to the state (highlighted in green)
- **Removed values** - Keys or values that were removed from the state (highlighted in red)
- **Modified values** - Values that changed from one step to another (highlighted in yellow)
- **Unchanged values** - Values that remained the same (displayed in normal text)

Example output:
```
State Diff (Step 1 → Step 2):
+ "answer": "42"           # Added
- "processing": true       # Removed
~ "confidence": 0.7 → 0.9  # Modified
  "input": "question"      # Unchanged
```

## Advanced Features

### Customizing Diff Display

Customize how diffs are displayed:

```python
# Customize diff display
debugger.show_state_diff(
    step_index=2,
    show_unchanged=False,   # Hide unchanged values
    depth=2,                # Limit nesting depth
    format="rich"           # Use rich formatting
)
```

Display options:
- `show_unchanged` - Whether to show unchanged values (default: True)
- `depth` - Maximum nesting depth to display (default: None, meaning unlimited)
- `format` - Display format: "text", "rich", or "json" (default: "rich")
- `max_string_length` - Maximum string length before truncation (default: 100)
- `max_collection_size` - Maximum number of items to display in lists/dicts (default: 50)

### Node-Specific Diffs

View state changes for specific nodes:

```python
# Show state diff for a specific node
debugger.show_node_state_diff("node_name")

# Compare state before and after a specific node
debugger.show_node_state_diff("node_name", include_before=True)
```

### Exporting Diffs

Export state diffs for external analysis or sharing:

```python
# Export state diff to a file
debugger.export_state_diff(
    step_index=2,
    output_file="state_diff.json",
    format="json"
)

# Get state diff as a structured object
diff_data = debugger.get_state_diff_data(step_index=2)
```

## Specialized Diff Visualizations

### Rich Terminal Visualizations

Use rich terminal visualizations for more detailed diffs:

```python
# Enable rich visualization
debugger.configure_visualization(mode="rich")

# Show rich diff
debugger.show_state_diff(step_index=2, format="rich")
```

The rich format provides:
- Color-coded differences
- Collapsible nested structures
- Syntax highlighting
- Better formatting of complex data types

### Side-by-Side Comparison

Compare states side by side:

```python
# Show side-by-side comparison
debugger.show_states_comparison(step1=1, step2=2)
```

### Diff Timeline

View a timeline of all state changes:

```python
# Show a timeline of all state changes
debugger.show_state_diff_timeline()
```

## Working with Complex Objects

### Custom Diff Logic for Complex Objects

Define custom diff logic for complex objects:

```python
# Define a custom differ for a specific type
class MyCustomObject:
    # Your custom object implementation
    pass

def my_custom_differ(obj1, obj2):
    # Return a diff representation for your custom objects
    return {
        "equal": obj1.value == obj2.value,
        "diff": f"{obj1.value} → {obj2.value}" if obj1.value != obj2.value else None
    }

# Register the custom differ
debugger.register_custom_differ(MyCustomObject, my_custom_differ)
```

### Deep Diffing Options

Configure deep diffing behavior:

```python
# Configure deep diffing options
debugger.configure_diff(
    ignore_private=True,      # Ignore keys starting with '_'
    max_depth=5,              # Maximum diffing depth
    diff_sets_as_list=True,   # Diff sets as if they were lists
    report_repetition=False   # Don't report repeated identical changes
)
```

## Practical Applications

### Debugging State Flow Issues

Use state diff to debug state flow issues:

```python
# Run with a test case that exhibits the issue
debugger.run(problematic_state)

# View complete state history
debugger.show_state_history()

# Identify the step where state becomes unexpected
debugger.show_state_diff(step_index=3)  # Assuming step 3 is suspect

# Focus on relevant parts of the state
debugger.show_state_diff(step_index=3, path=["results", "calculations"])
```

### Performance Optimization

Identify inefficient state manipulations:

```python
# Run with performance tracking
debugger.enable_performance_tracking()
result = debugger.run(state)

# Identify expensive state changes
debugger.show_performance_report()

# Examine state changes in expensive nodes
for node in debugger.get_expensive_nodes():
    debugger.show_node_state_diff(node)
```

## Best Practices

- **Focus on relevant changes**: Use filtering to focus on the parts of state you're interested in
- **Combine with breakpoints**: Use breakpoints to examine state at critical points
- **Track small steps**: Complex issues often manifest as small, subtle state changes
- **Use rich visualization**: For complex states, rich visualization provides better insight
- **Export for team collaboration**: Export diffs to share findings with your team
- **Path-based inspection**: Use path parameters to drill down into specific state sections

## Troubleshooting

Common state diff issues and solutions:

- **Overwhelming output**: Use `depth`, `show_unchanged=False`, or path filtering to reduce output
- **Missing changes**: Ensure state tracking is enabled and check if changes are in excluded paths
- **Performance issues**: Limit depth and collection sizes for large states
- **Custom object issues**: Implement custom differs for complex objects

## Next Steps

- [State History Tracking](state_history_tracking.md) for navigating through state history
- [Breakpoint System](breakpoint_system.md) for controlling execution at specific state conditions
- [Graph Visualization](graph_visualization.md) for visualizing graph structure and execution paths

For a practical example of state difference visualization, see the [State Diff Example](../examples/state_diff_example.md). 