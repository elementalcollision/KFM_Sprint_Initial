# Breakpoint System

This guide explains how to use the breakpoint system in the KFM debugging tools to control and inspect the execution of your LangGraph applications.

## Overview

The breakpoint system allows you to pause graph execution at specific points, inspect the current state, and make decisions about how to proceed. Key features include:

- **Node breakpoints** - Pause execution when a specific node is reached
- **Conditional breakpoints** - Pause execution when a condition is met
- **Custom actions** - Execute custom actions when a breakpoint is hit
- **Step-by-step execution** - Control execution flow by stepping through nodes
- **State inspection** - Examine and modify state at breakpoints

## Basic Usage

### Enabling Breakpoints

First, enable breakpoints in your debugger configuration:

```python
from kfm_debugging import Debugger

# Enable breakpoints during initialization
debugger = Debugger(graph, enable_breakpoints=True)

# Or enable them after initialization
debugger.enable_breakpoints()
```

### Setting Simple Breakpoints

Add a breakpoint at a specific node:

```python
# Add a breakpoint at the "process_input" node
debugger.add_breakpoint("process_input")

# Run the graph with breakpoints enabled
result = debugger.run(initial_state)
```

When the graph execution reaches the "process_input" node, it will pause and provide a breakpoint prompt in the console.

### Breakpoint Prompt

When a breakpoint is hit, you'll see a prompt like this:

```
Breakpoint hit at node: process_input
Current state: {'input': 'user input', ...}

Options:
[c] Continue execution
[s] Step to next node
[q] Quit execution
[i] Inspect state
[m] Modify state
[h] Help
> 
```

Enter a command to control execution:

- `c` - Continue execution until the next breakpoint or completion
- `s` - Step to the next node in the execution path
- `q` - Quit execution and return the current state
- `i` - Inspect the current state in detail
- `m` - Modify the current state
- `h` - Show help information

## Advanced Features

### Conditional Breakpoints

Add breakpoints that pause execution only when specific conditions are met:

```python
# Pause when the state contains an error
debugger.add_breakpoint(
    "process_result",
    condition=lambda state: "error" in state
)

# Pause when a specific value exceeds a threshold
debugger.add_breakpoint(
    "calculate_score",
    condition=lambda state: state.get("score", 0) > 0.8
)
```

### Custom Actions

Execute custom actions when a breakpoint is hit:

```python
# Log state when the breakpoint is hit
debugger.add_breakpoint(
    "analyze_data",
    action=lambda state: print(f"State at breakpoint: {state}")
)

# Save state to a file when the breakpoint is hit
def save_state_snapshot(state):
    import json
    with open(f"state_snapshot_{id(state)}.json", "w") as f:
        json.dump(state, f, indent=2)

debugger.add_breakpoint(
    "critical_node",
    action=save_state_snapshot
)
```

### Multiple Breakpoint Conditions

Combine multiple conditions for complex breakpoint behavior:

```python
def complex_condition(state):
    # Check multiple conditions
    has_error = "error" in state
    high_confidence = state.get("confidence", 0) > 0.9
    critical_stage = state.get("stage") == "critical"
    
    # Break only if there's an error in a critical stage
    # or if we have high confidence
    return (has_error and critical_stage) or high_confidence

debugger.add_breakpoint(
    "decision_node", 
    condition=complex_condition
)
```

### Programmatic Control

Programmatically control the debugger's execution:

```python
# Run with programmatic breakpoint handling
debugger.run(
    initial_state,
    breakpoint_handler=lambda node, state, options: "continue"  # Always continue
)

# Create a custom breakpoint handler
def custom_breakpoint_handler(node, state, options):
    print(f"Custom handler at node: {node}")
    
    # Save state to file
    with open(f"breakpoint_{node}.json", "w") as f:
        json.dump(state, f, indent=2)
    
    # Always step to the next node
    return "step"

# Run with the custom handler
debugger.run(initial_state, breakpoint_handler=custom_breakpoint_handler)
```

## Breakpoint Management

### Listing Breakpoints

List all breakpoints:

```python
# Get all breakpoints
breakpoints = debugger.get_breakpoints()

# Print breakpoint information
for node, bp_info in breakpoints.items():
    condition = "Conditional" if bp_info.get("condition") else "Unconditional"
    has_action = "With action" if bp_info.get("action") else "No action"
    print(f"Node: {node}, {condition}, {has_action}")
```

### Removing Breakpoints

Remove breakpoints when they're no longer needed:

```python
# Remove a specific breakpoint
debugger.remove_breakpoint("process_input")

# Remove all breakpoints at once
debugger.clear_breakpoints()
```

### Disabling and Enabling Breakpoints

Temporarily disable and enable breakpoints:

```python
# Disable a specific breakpoint
debugger.disable_breakpoint("process_input")

# Enable a previously disabled breakpoint
debugger.enable_breakpoint("process_input")

# Disable all breakpoints
debugger.disable_all_breakpoints()

# Enable all breakpoints
debugger.enable_all_breakpoints()
```

## Interactive State Inspection and Modification

When a breakpoint is hit, you can interactively inspect and modify the state:

### Inspecting State

In the breakpoint prompt, enter `i` to inspect the state:

```
> i
State at node: process_input
{
  "input": "user query",
  "timestamp": "2023-08-15T10:30:00",
  "processed": false
}

Path to inspect (or Enter to return): processed
Value: false

Path to inspect (or Enter to return):
```

You can navigate the state hierarchy by entering paths to inspect.

### Modifying State

In the breakpoint prompt, enter `m` to modify the state:

```
> m
State at node: process_input
{
  "input": "user query",
  "timestamp": "2023-08-15T10:30:00",
  "processed": false
}

Path to modify (or Enter to return): processed
Current value: false
New value: true

Path to modify (or Enter to return):
```

Enter the path to the value you want to modify and provide a new value.

## Advanced Breakpoint Patterns

### Step-Through Debugging

To inspect every node in a graph:

```python
# Set breakpoints on all nodes
for node in graph.nodes:
    debugger.add_breakpoint(node)

# Run and step through each node
debugger.run(initial_state)
```

### Conditional Debugging

Focus debugging on a specific condition:

```python
# Debug only when a specific error occurs
error_condition = lambda state: state.get("error_type") == "validation_error"

# Add breakpoints to relevant nodes
for node in ["validate_input", "process_validation", "handle_errors"]:
    debugger.add_breakpoint(node, condition=error_condition)
```

### Debugging Complex Workflows

For complex workflows, combine breakpoints with state inspection:

```python
# Track execution path
execution_path = []

def path_tracker(state):
    node = debugger.current_node
    execution_path.append(node)
    return False  # Don't actually break

# Add trackers to all nodes
for node in graph.nodes:
    debugger.add_breakpoint(node, condition=path_tracker)

# Add real breakpoint at the end
debugger.add_breakpoint(
    "final_node",
    action=lambda state: print(f"Execution path: {' -> '.join(execution_path)}")
)
```

## Integration with Other Debugging Features

### Combining with State Diff Visualization

Use breakpoints with state diff visualization:

```python
# Store states at key points
states = {}

# Capture state at specific nodes
def capture_state(state):
    node = debugger.current_node
    states[node] = state.copy()
    return False  # Don't break execution

# Add capture points
for node in ["node1", "node2", "node3"]:
    debugger.add_breakpoint(node, condition=capture_state)

# Run the graph
result = debugger.run(initial_state)

# Compare states between key points
debugger.show_states_comparison(states["node1"], states["node2"])
```

### Combining with Logging

Enhance logging with breakpoint information:

```python
# Configure detailed logging
debugger.configure_logger(log_level=LogLevel.DEBUG)

# Add logging at breakpoints
def enhanced_logging(state):
    node = debugger.current_node
    debugger.logger.info(f"Breakpoint reached at {node}")
    debugger.logger.debug(f"State at {node}: {state}")
    
    # Log execution time
    import time
    debugger.logger.info(f"Execution time: {time.time() - debugger.start_time:.2f}s")
    
    return False  # Don't break execution

# Add to all nodes
for node in graph.nodes:
    debugger.add_breakpoint(node, condition=enhanced_logging)
```

## Best Practices

- **Be selective with breakpoints**: Too many breakpoints can slow down debugging
- **Use conditional breakpoints**: Filter when breakpoints are triggered to focus on specific scenarios
- **Combine with state tracking**: Use state history and diffs to understand what changed
- **Add actionable context**: Custom actions can provide additional information
- **Remove unnecessary breakpoints**: Clear breakpoints when they're no longer needed
- **Group related nodes**: Consider debugging related nodes together

## Troubleshooting

Common issues and solutions:

- **Breakpoints not triggering**: Check that breakpoints are enabled in the debugger configuration
- **Condition never evaluated**: Verify that the node is actually executed in the graph
- **Performance issues**: Reduce the number of breakpoints or use more specific conditions
- **State modification errors**: Ensure new values are of the correct type and format
- **Execution termination**: Use `try/except` around `debugger.run()` to handle early termination

## Next Steps

- [State History Tracking](state_history_tracking.md) for tracking state changes over time
- [Error Handling and Recovery](error_handling.md) for managing errors in your graph
- [Advanced Debugging Tutorial](../examples/advanced_debugging_tutorial.md) for more complex debugging scenarios

For a practical example of using the breakpoint system, see the [Breakpoint System Example](../examples/breakpoint_system_example.md). 