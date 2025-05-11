# Graph Execution Monitoring

This guide explains how to use the graph execution monitoring features in the KFM debugging tools to track and analyze the execution flow of your LangGraph applications.

## Overview

Graph execution monitoring provides real-time insights into how your graph is executing, including:

- **Execution path tracking** - Visualize and analyze the exact path taken through the graph
- **Node execution timing** - Measure performance of individual nodes and transitions
- **Execution history** - Review previous executions and compare different runs
- **Conditional branch analysis** - Understand why specific paths were taken
- **Loop detection** - Identify and analyze repetitive execution patterns

## Basic Usage

### Enabling Execution Monitoring

Enable execution monitoring during debugger initialization:

```python
from kfm_debugging import Debugger

# Enable execution monitoring during initialization
debugger = Debugger(graph, execution_monitoring=True)

# Or enable it after initialization
debugger.enable_execution_monitoring()
```

### Viewing Execution Path

After running your graph, view the execution path:

```python
# Run your graph
initial_state = {"input": "Your input here"}
result = debugger.run(initial_state)

# Show the execution path
debugger.show_execution_path()
```

Example output:
```
Execution Path:
start → input_parser → calculator → responder → end
```

### Visualizing Execution Flow

Create a visual representation of the execution flow:

```python
# Visualize the execution path on the graph
debugger.visualize_execution_path(output_file="execution_path.png")

# Visualize with timing information
debugger.visualize_execution_path(
    output_file="execution_path_with_timing.png",
    show_timing=True
)
```

## Advanced Features

### Execution Timing Analysis

Analyze the execution time of nodes and transitions:

```python
# Show execution timing for all nodes
debugger.show_execution_timing()

# Show timing for specific nodes
debugger.show_execution_timing(nodes=["calculator", "responder"])

# Get detailed timing data
timing_data = debugger.get_execution_timing_data()
for node, data in timing_data.items():
    print(f"Node: {node}, Time: {data['execution_time']:.2f}ms")
```

### Execution History

Track and compare multiple executions:

```python
# Store execution with an identifier
debugger.store_execution("example_1")

# Run with different input
result2 = debugger.run({"input": "Different input"})
debugger.store_execution("example_2")

# Compare executions
debugger.compare_executions("example_1", "example_2")

# List stored executions
executions = debugger.list_stored_executions()
print(f"Stored executions: {executions}")
```

### Conditional Branch Analysis

Understand why specific execution paths were taken:

```python
# Enable branch analysis
debugger.enable_branch_analysis()

# Run the graph
result = debugger.run(initial_state)

# Show branch analysis
debugger.show_branch_analysis()
```

Example output:
```
Branch Analysis:
Node: conditional_router
- Branch: process_text
  - Condition: state["input_type"] == "text"
  - Condition result: True
  - State at decision: {"input_type": "text", ...}

Node: error_handler
- Branch: retry
  - Condition: state["retry_count"] < 3
  - Condition result: True
  - State at decision: {"retry_count": 1, ...}
```

### Loop Detection and Analysis

Identify and analyze loops in execution:

```python
# Enable loop detection
debugger.enable_loop_detection()

# Run the graph
result = debugger.run(initial_state)

# Show loop analysis
debugger.show_loop_analysis()
```

Example output:
```
Loop Analysis:
Loop #1:
- Nodes: process_input → validate → retry → process_input
- Iterations: 3
- Exit condition: validation_passed == True
- Total time in loop: 156.3ms
```

## Visualizing Complex Execution Flows

### Timeline Visualization

Create a timeline visualization of the execution:

```python
# Show execution timeline
debugger.show_execution_timeline()

# Export timeline visualization
debugger.export_execution_timeline(output_file="execution_timeline.html")
```

### Heatmap Visualization

Create a heatmap to identify hotspots in your graph:

```python
# Generate a heatmap based on execution count
debugger.visualize_execution_heatmap(
    metric="count",
    output_file="execution_count_heatmap.png"
)

# Generate a heatmap based on execution time
debugger.visualize_execution_heatmap(
    metric="time",
    output_file="execution_time_heatmap.png"
)
```

### Flow Diagram

Generate a detailed flow diagram with execution data:

```python
# Create a flow diagram with execution statistics
debugger.visualize_execution_flow(
    output_file="detailed_flow.png",
    show_stats=True,
    highlight_bottlenecks=True
)
```

## Monitoring Specific Execution Patterns

### Node Entry and Exit Events

Listen for node entry and exit events:

```python
# Define entry and exit handlers
def on_node_entry(node, state):
    print(f"Entering node: {node}")
    print(f"State: {state}")

def on_node_exit(node, state, result):
    print(f"Exiting node: {node}")
    print(f"Result: {result}")

# Register the handlers
debugger.on_node_entry(on_node_entry)
debugger.on_node_exit(on_node_exit)

# Run the graph
result = debugger.run(initial_state)
```

### Custom Execution Metrics

Define and track custom execution metrics:

```python
# Define a custom metric function
def token_count_metric(node, state, result):
    # Count tokens in input and output
    input_tokens = len(state.get("input", "").split())
    output_tokens = len(result.get("output", "").split())
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens
    }

# Register the custom metric
debugger.register_execution_metric("token_count", token_count_metric)

# Run the graph
result = debugger.run(initial_state)

# Show custom metric results
debugger.show_execution_metrics("token_count")
```

## Integration with Logging

Enhance logging with execution information:

```python
# Configure execution-aware logging
debugger.configure_logger(
    log_level=LogLevel.INFO,
    include_execution_path=True
)

# Log entries will include the current execution path
# Example: [2023-08-15 10:30:00] [INFO] [start → input_parser → calculator] Calculating result...
```

## Practical Applications

### Debugging Execution Flow Issues

Identify issues in the execution flow:

```python
# Enable comprehensive monitoring
debugger.enable_execution_monitoring()
debugger.enable_branch_analysis()
debugger.enable_loop_detection()

# Run the graph with problematic input
try:
    result = debugger.run(problematic_input)
except Exception as e:
    # Show execution path up to the error
    debugger.show_execution_path()
    
    # Show branch decisions leading to the error
    debugger.show_branch_analysis()
    
    # Get context about the error
    error_context = debugger.get_error_context(e)
    print(f"Error in node: {error_context.node}")
```

### Performance Optimization

Identify performance bottlenecks:

```python
# Enable timing analysis
debugger.enable_execution_monitoring()

# Run multiple test cases
for test_case in test_cases:
    debugger.run(test_case)
    debugger.store_execution(f"test_{test_case['id']}")

# Show timing statistics across all runs
debugger.show_aggregate_timing()

# Identify the slowest nodes
slow_nodes = debugger.identify_bottlenecks(threshold_ms=100)
print(f"Performance bottlenecks: {slow_nodes}")
```

## Best Practices

- **Focus on critical paths**: Monitor the most important execution paths first
- **Combine with state tracking**: Use state tracking alongside execution monitoring for complete visibility
- **Set performance baselines**: Establish baseline timing for comparison
- **Create visual reports**: Generate visualizations for team communication
- **Monitor over time**: Track execution patterns across versions to spot regressions
- **Use custom metrics**: Define metrics relevant to your specific application

## Troubleshooting

Common execution monitoring issues and solutions:

- **High memory usage**: Limit history storage or disable persistent history
- **Performance impact**: Use selective monitoring for production environments
- **Missing execution data**: Ensure monitoring was enabled before running
- **Complex visualizations**: Filter nodes or use simplified views for large graphs
- **Inconsistent timing**: Run multiple executions to get average timing data

## Next Steps

- [Performance Profiling](performance_profiling.md) for detailed performance analysis
- [State Difference Visualization](state_diff_visualization.md) for tracking state changes
- [Advanced Debugging Tutorial](../examples/advanced_debugging_tutorial.md) for comprehensive examples

For a practical example of execution monitoring, see the [Execution Monitoring Example](../examples/execution_monitoring_example.md). 