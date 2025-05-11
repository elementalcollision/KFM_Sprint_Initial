# Performance Profiling

This guide explains how to use the performance profiling features in the KFM debugging tools to optimize the execution speed and resource usage of your LangGraph applications.

## Overview

Performance profiling helps you identify bottlenecks and inefficiencies in your graph execution. Key benefits include:

- **Node timing analysis** - Measure execution time of individual nodes
- **Memory usage tracking** - Monitor memory consumption during execution
- **Resource utilization** - Track CPU, GPU, and network usage
- **Bottleneck identification** - Pinpoint performance-limiting components
- **Optimization suggestions** - Get actionable recommendations for improvement

## Basic Usage

### Enabling Performance Profiling

Enable profiling during debugger initialization:

```python
from kfm_debugging import Debugger, ProfilingLevel

# Enable basic profiling during initialization
debugger = Debugger(graph, enable_profiling=True)

# Or with a specific profiling level
debugger = Debugger(graph, profiling_level=ProfilingLevel.DETAILED)

# Enable profiling after initialization
debugger.enable_profiling(level=ProfilingLevel.BASIC)
```

Available profiling levels:
- `ProfilingLevel.BASIC` - Track execution time only
- `ProfilingLevel.STANDARD` - Track execution time and memory usage
- `ProfilingLevel.DETAILED` - Track execution time, memory, and resource utilization
- `ProfilingLevel.COMPREHENSIVE` - Track all available metrics with high resolution

### Running with Profiling

Run your graph with profiling enabled:

```python
# Run the graph
initial_state = {"input": "Your input here"}
result = debugger.run(initial_state)

# Show basic profiling results
debugger.show_profile_report()
```

Example output:
```
Performance Profile:
Total execution time: 235.67ms

Node Execution Times:
- input_parser: 12.34ms (5.2%)
- calculator: 189.45ms (80.4%)
- responder: 33.88ms (14.4%)

Memory Usage:
Initial: 45.6MB
Peak: 67.8MB
Final: 52.3MB
```

## Advanced Features

### Detailed Node Timing

Analyze detailed timing information for nodes:

```python
# Show detailed timing for all nodes
debugger.show_node_timing(detailed=True)

# Show timing for specific nodes
debugger.show_node_timing(nodes=["calculator", "responder"])

# Export timing data
debugger.export_timing_data(output_file="timing_data.json")
```

Example detailed output:
```
Node: calculator
- Total time: 189.45ms
  - Setup: 2.31ms
  - Computation: 184.67ms
  - State update: 2.47ms
- Called: 1 time
- Average time: 189.45ms
- Percentage of total: 80.4%
```

### Memory Profiling

Track and analyze memory usage:

```python
# Show memory profile
debugger.show_memory_profile()

# Track memory over time
debugger.show_memory_timeline()

# Show memory usage by node
debugger.show_node_memory_usage()
```

Example memory profile:
```
Memory Profile:
Initial memory: 45.6MB
Peak memory: 67.8MB (at node: calculator)
Final memory: 52.3MB
Memory growth: +6.7MB

Node Memory Impact:
- input_parser: +1.2MB
- calculator: +18.9MB (peak: +22.2MB)
- responder: -13.3MB
```

### Resource Utilization

Monitor CPU, GPU, and network usage:

```python
# Show overall resource utilization
debugger.show_resource_utilization()

# Show CPU usage by node
debugger.show_cpu_usage()

# Show GPU utilization (if available)
debugger.show_gpu_usage()

# Show network traffic
debugger.show_network_usage()
```

### State Size Analysis

Analyze the size and complexity of the state:

```python
# Show state size analysis
debugger.show_state_size_analysis()

# Track state size over time
debugger.show_state_size_timeline()

# Show state size by node
debugger.show_node_state_impact()
```

## Visualization and Reporting

### Performance Graphs

Generate visual performance reports:

```python
# Generate a timeline graph
debugger.visualize_performance_timeline(output_file="performance_timeline.png")

# Generate a node comparison chart
debugger.visualize_node_comparison(
    metric="execution_time",
    output_file="time_comparison.png"
)

# Generate a memory usage chart
debugger.visualize_memory_usage(output_file="memory_usage.png")
```

### Heat Maps

Create heat maps to identify hotspots:

```python
# Generate a execution time heat map
debugger.visualize_performance_heatmap(
    metric="execution_time",
    output_file="time_heatmap.png"
)

# Generate a memory usage heat map
debugger.visualize_performance_heatmap(
    metric="memory_usage",
    output_file="memory_heatmap.png"
)
```

### Comprehensive Reports

Generate detailed performance reports:

```python
# Generate a comprehensive HTML report
debugger.generate_performance_report(
    output_file="performance_report.html",
    include_visualizations=True
)

# Generate a summary report
debugger.generate_performance_summary(output_file="performance_summary.md")
```

## Advanced Profiling Techniques

### Benchmarking

Compare performance across different runs or configurations:

```python
# Create a benchmark configuration
benchmark_config = {
    "runs": 5,  # Number of runs
    "configs": [
        {"name": "baseline", "cache_enabled": False},
        {"name": "with_cache", "cache_enabled": True}
    ],
    "test_cases": [
        {"input": "Small input", "id": "small"},
        {"input": "Medium size input with more data", "id": "medium"},
        {"input": "Large input " + "with lots of data " * 50, "id": "large"}
    ]
}

# Run the benchmark
benchmark_results = debugger.run_benchmark(benchmark_config)

# Show benchmark results
debugger.show_benchmark_results(benchmark_results)

# Compare specific configurations
debugger.compare_benchmark_configs("baseline", "with_cache")
```

### Continuous Profiling

Track performance changes over time:

```python
# Enable continuous profiling
debugger.enable_continuous_profiling(
    log_file="continuous_profile.log",
    metrics=["execution_time", "memory_usage"]
)

# Run multiple times as needed
for i in range(10):
    result = debugger.run(get_test_input(i))

# Show continuous profiling trends
debugger.show_profiling_trends()
```

### Custom Metrics

Define and track custom performance metrics:

```python
# Define a custom metric function
def tokens_per_second(node_stats, execution_stats):
    tokens = execution_stats.get("total_tokens", 0)
    time_seconds = node_stats["execution_time"] / 1000  # ms to seconds
    return tokens / time_seconds if time_seconds > 0 else 0

# Register the custom metric
debugger.register_performance_metric("tokens_per_second", tokens_per_second)

# Run the graph
result = debugger.run(initial_state)

# Show custom metric results
debugger.show_performance_metric("tokens_per_second")
```

## Optimization Strategies

### Automatic Bottleneck Detection

Automatically identify performance bottlenecks:

```python
# Identify bottlenecks
bottlenecks = debugger.identify_bottlenecks()

# Show detailed bottleneck analysis
debugger.analyze_bottlenecks(bottlenecks)

# Get optimization suggestions
suggestions = debugger.get_optimization_suggestions(bottlenecks)
for node, suggestion in suggestions.items():
    print(f"Node: {node}")
    print(f"Issue: {suggestion['issue']}")
    print(f"Suggestion: {suggestion['suggestion']}")
```

### Optimization Experiments

Test potential optimizations:

```python
# Define optimization strategies
strategies = {
    "baseline": {},  # No optimizations
    "caching": {"enable_caching": True},
    "parallel": {"enable_parallel": True},
    "reduced_state": {"minimize_state": True}
}

# Run optimization experiments
results = debugger.run_optimization_experiments(
    initial_state,
    strategies=strategies,
    runs_per_strategy=3
)

# Show experiment results
debugger.show_optimization_experiments(results)

# Get the recommended strategy
best_strategy = debugger.get_recommended_strategy(results)
print(f"Recommended strategy: {best_strategy}")
```

## Practical Applications

### Identifying Slow Nodes

Find and fix slow nodes in your graph:

```python
# Enable detailed profiling
debugger.enable_profiling(level=ProfilingLevel.DETAILED)

# Run the graph
result = debugger.run(initial_state)

# Identify slow nodes
slow_nodes = debugger.identify_slow_nodes(threshold_percent=10)
print(f"Slow nodes: {slow_nodes}")

# Get detailed analysis of the slowest node
slowest_node = debugger.get_slowest_node()
debugger.analyze_node_performance(slowest_node)

# Get optimization suggestions
suggestions = debugger.get_node_optimization_suggestions(slowest_node)
print(f"Suggestions: {suggestions}")
```

### Memory Leak Detection

Identify potential memory leaks:

```python
# Enable memory tracking
debugger.enable_profiling(level=ProfilingLevel.DETAILED)

# Run multiple iterations
for i in range(10):
    result = debugger.run(initial_state)
    
    # Check for memory growth
    memory_growth = debugger.analyze_memory_growth()
    print(f"Iteration {i}: Memory growth: {memory_growth}MB")

# Check for memory leaks
potential_leaks = debugger.detect_memory_leaks()
if potential_leaks:
    print("Potential memory leaks detected:")
    for node, leak_info in potential_leaks.items():
        print(f"Node: {node}, Accumulated: {leak_info['accumulated']}MB")
```

### Performance Regression Testing

Track performance across code changes:

```python
# Define a performance baseline
debugger.save_performance_baseline(
    "baseline_v1.0",
    metrics=["execution_time", "memory_usage"]
)

# Later, after code changes
result = debugger.run(initial_state)

# Compare with baseline
comparison = debugger.compare_with_baseline("baseline_v1.0")
print("Performance changes:")
for metric, change in comparison.items():
    print(f"{metric}: {change['percent_change']}% change")

# Check for regressions
regressions = debugger.check_performance_regressions("baseline_v1.0")
if regressions:
    print("Performance regressions detected:")
    for metric, regression in regressions.items():
        print(f"{metric}: {regression['percent_change']}% worse")
```

## Best Practices

- **Profile in realistic environments**: Profile with production-like data and conditions
- **Focus on critical paths**: Prioritize optimizing nodes in the most common execution paths
- **Establish baselines**: Create performance baselines to measure improvements
- **Test changes incrementally**: Test the performance impact of each change separately
- **Balance tradeoffs**: Consider memory vs. speed tradeoffs in optimizations
- **Interpret with context**: Understand that some nodes may be intentionally slow due to their purpose
- **Profile before and after**: Always measure performance before and after optimization

## Troubleshooting

Common profiling issues and solutions:

- **Profiling overhead**: Lower the profiling level for production environments
- **Inconsistent results**: Run multiple profiling sessions to account for variability
- **Memory tracking issues**: Ensure the debugger has permissions to access system memory stats
- **Missing GPU metrics**: Verify GPU libraries are installed and accessible
- **High CPU usage during profiling**: Reduce profiling frequency or detail level
- **Misleading bottlenecks**: Distinguish between inherent complexity and inefficiency

## Next Steps

- [Graph Execution Monitoring](graph_execution_monitoring.md) for execution flow analysis
- [Advanced Debugging Tutorial](../examples/advanced_debugging_tutorial.md) for comprehensive examples
- [Performance Optimization Tutorial](../examples/performance_optimization_tutorial.md) for optimization techniques

For a practical example of performance profiling, see the [Performance Profiling Example](../examples/performance_profiling_example.md). 