# Performance Optimization Tutorial

This tutorial demonstrates how to use the KFM debugging tools to identify and resolve performance issues in LangGraph applications. You'll learn a systematic approach to profiling, analyzing, and optimizing graph execution.

## Prerequisites

Before starting this tutorial, make sure you have:

- Completed the [Basic Debugging Tutorial](basic_debugging_tutorial.md)
- Familiarity with [Performance Profiling](../user_guides/performance_profiling.md) concepts
- Python 3.9 or higher installed
- LangGraph 0.0.43 or higher installed
- The KFM debugging tools installed (`pip install kfm-debugging-tools`)

## Step 1: Creating a Performance Test Graph

First, let's create a LangGraph application with various performance characteristics to optimize:

```python
# performance_test_graph.py
from langgraph.graph import StateGraph, END
import time
import random
import json

# State model
state_model = {
    "input": "",
    "processed_data": {},
    "analysis_results": [],
    "cache": {},
    "response": "",
    "metadata": {}
}

# Simulate an expensive operation
def simulate_work(duration, variability=0.2):
    """Simulate work taking a specific duration with some variability."""
    actual_duration = duration * (1 + random.uniform(-variability, variability))
    time.sleep(actual_duration)

# Node functions
def input_parser(state):
    """Parse and validate the input."""
    simulate_work(0.05)  # 50ms operation
    
    input_text = state["input"]
    state["processed_data"]["tokens"] = input_text.split()
    state["processed_data"]["char_count"] = len(input_text)
    state["processed_data"]["word_count"] = len(state["processed_data"]["tokens"])
    
    # Add unnecessary deep copying of data
    state["metadata"]["input_stats"] = json.loads(json.dumps(state["processed_data"]))
    
    return state

def data_processor(state):
    """Process the data with some inefficiencies."""
    simulate_work(0.2)  # 200ms operation
    
    # Inefficient string concatenation
    result = ""
    for word in state["processed_data"]["tokens"]:
        result += word.upper() + " "
    
    state["processed_data"]["processed_text"] = result
    
    # Unnecessary repeated calculations
    for i in range(5):
        temp = []
        for word in state["processed_data"]["tokens"]:
            temp.append(len(word))
        state["processed_data"]["word_lengths"] = temp
    
    return state

def heavy_analysis(state):
    """Perform a complex analysis with memory issues."""
    simulate_work(0.3)  # 300ms operation
    
    # Create a large, unnecessary data structure
    large_structure = []
    for i in range(10000):
        large_structure.append({
            "index": i,
            "value": random.random(),
            "text": state["processed_data"].get("processed_text", "")[:100]
        })
    
    # Simplified result
    state["analysis_results"] = [
        {"sentiment": random.uniform(-1, 1)},
        {"complexity": random.uniform(0, 1)},
        {"relevance": random.uniform(0, 1)}
    ]
    
    # Unnecessary storage of intermediate results
    state["metadata"]["analysis_intermediate"] = large_structure[:100]
    
    return state

def response_generator(state):
    """Generate a response with caching issues."""
    simulate_work(0.15)  # 150ms operation
    
    # Cache could be used but isn't checked efficiently
    cache_key = state["input"][:20]  # Inefficient cache key
    
    if cache_key in state["cache"]:
        # Simulate still doing some work even when using cache
        simulate_work(0.1)
        state["response"] = state["cache"][cache_key]
    else:
        # Generate response
        response = f"Analysis complete! Found {len(state['analysis_results'])} insights."
        state["response"] = response
        state["cache"][cache_key] = response
    
    # Add all intermediate data to metadata (unnecessary)
    state["metadata"]["full_process_record"] = {
        "input_data": state["processed_data"],
        "analysis": state["analysis_results"],
        "timestamp": time.time()
    }
    
    return state

# Define the graph
def build_graph():
    graph = StateGraph(state_model)
    
    # Add nodes
    graph.add_node("input_parser", input_parser)
    graph.add_node("data_processor", data_processor)
    graph.add_node("heavy_analysis", heavy_analysis)
    graph.add_node("response_generator", response_generator)
    
    # Add edges
    graph.add_edge("input_parser", "data_processor")
    graph.add_edge("data_processor", "heavy_analysis")
    graph.add_edge("heavy_analysis", "response_generator")
    graph.add_edge("response_generator", END)
    
    # Set entry point
    graph.set_entry_point("input_parser")
    
    return graph

# Run the graph
if __name__ == "__main__":
    graph = build_graph()
    
    # Process a sample input
    result = graph.invoke({"input": "This is a sample input text for performance testing. It contains enough words to demonstrate various performance characteristics and optimization opportunities."})
    
    print("Response:", result["response"])
```

## Step 2: Initial Profiling

Let's profile the graph to identify performance issues:

```python
# performance_optimization.py
from performance_test_graph import build_graph
from kfm_debugging import Debugger, ProfilingLevel, LogLevel

# Create the graph
graph = build_graph()

# Initialize the debugger with profiling
debugger = Debugger(
    graph,
    log_level=LogLevel.INFO,
    enable_profiling=True,
    profiling_level=ProfilingLevel.DETAILED,
    state_tracking=True
)

def run_profiling():
    """Run a profiling session and show results."""
    # Sample input
    initial_state = {
        "input": "This is a sample input text for performance testing. It contains enough words to demonstrate various performance characteristics and optimization opportunities."
    }
    
    # Run the graph
    result = debugger.run(initial_state)
    
    # Show profile report
    print("\n===== Performance Profile =====")
    debugger.show_profile_report()
    
    # Identify bottlenecks
    print("\n===== Performance Bottlenecks =====")
    bottlenecks = debugger.identify_bottlenecks(threshold_percent=10)
    for node, stats in bottlenecks.items():
        print(f"Node: {node}")
        print(f"  Time: {stats['execution_time']:.2f}ms ({stats['percentage']:.1f}%)")
    
    # Show memory usage
    print("\n===== Memory Usage =====")
    debugger.show_memory_profile()
    
    # Show state size analysis
    print("\n===== State Size Analysis =====")
    debugger.show_state_size_analysis()
    
    # Show node state impact
    print("\n===== Node State Impact =====")
    debugger.show_node_state_impact()
    
    # Visualize performance
    debugger.visualize_performance_heatmap(
        metric="execution_time", 
        output_file="performance_heatmap_before.png"
    )
    
    # Generate suggestions
    print("\n===== Optimization Suggestions =====")
    suggestions = debugger.get_optimization_suggestions(bottlenecks)
    for node, suggestion in suggestions.items():
        print(f"Node: {node}")
        print(f"  Issue: {suggestion['issue']}")
        print(f"  Suggestion: {suggestion['suggestion']}")
    
    return result

if __name__ == "__main__":
    print("Running initial profiling...")
    run_profiling()
```

Run this script to get baseline performance metrics:

```bash
python performance_optimization.py
```

## Step 3: Optimization Strategy

Based on the profiling results, let's implement optimizations one by one:

### Optimization 1: Fixing Input Parser

```python
# optimized_performance_graph.py (first version)
# Import from the original graph
from performance_test_graph import (
    build_graph as build_original_graph,
    state_model, simulate_work, 
    data_processor, heavy_analysis, response_generator
)

# Optimized input parser
def optimized_input_parser(state):
    """Optimized version of input parser."""
    simulate_work(0.05)  # Same base operation time
    
    input_text = state["input"]
    tokens = input_text.split()
    
    # Store processed data efficiently
    state["processed_data"] = {
        "tokens": tokens,
        "char_count": len(input_text),
        "word_count": len(tokens)
    }
    
    # Use direct reference instead of deep copying
    state["metadata"]["input_stats"] = {
        "char_count": state["processed_data"]["char_count"],
        "word_count": state["processed_data"]["word_count"]
    }
    
    return state

# Build the graph with the optimized function
def build_graph():
    # Start with the original graph
    graph = build_original_graph()
    
    # Replace the input parser node
    graph.update_node("input_parser", optimized_input_parser)
    
    return graph
```

### Optimization 2: Improving Data Processor

```python
# Add to optimized_performance_graph.py

# Optimized data processor
def optimized_data_processor(state):
    """Optimized version of data processor."""
    simulate_work(0.2)  # Same base operation time
    
    # Efficient string handling
    tokens = state["processed_data"]["tokens"]
    state["processed_data"]["processed_text"] = " ".join([word.upper() for word in tokens])
    
    # Calculate word lengths once
    state["processed_data"]["word_lengths"] = [len(word) for word in tokens]
    
    return state

# Update the build_graph function
def build_graph():
    # Start with the original graph
    graph = build_original_graph()
    
    # Replace both optimized nodes
    graph.update_node("input_parser", optimized_input_parser)
    graph.update_node("data_processor", optimized_data_processor)
    
    return graph
```

### Optimization 3: Fixing Heavy Analysis

```python
# Add to optimized_performance_graph.py

# Optimized heavy analysis
def optimized_heavy_analysis(state):
    """Optimized version of heavy analysis."""
    simulate_work(0.3)  # Same base operation time
    
    # Skip creating the large, unnecessary data structure
    # Just create the results directly
    state["analysis_results"] = [
        {"sentiment": random.uniform(-1, 1)},
        {"complexity": random.uniform(0, 1)},
        {"relevance": random.uniform(0, 1)}
    ]
    
    # Store minimal metadata if needed
    state["metadata"]["analysis_summary"] = {
        "timestamp": time.time(),
        "analysis_count": len(state["analysis_results"])
    }
    
    return state

# Update the build_graph function
def build_graph():
    # Need to import random for this function
    import random
    
    # Start with the original graph
    graph = build_original_graph()
    
    # Replace all optimized nodes
    graph.update_node("input_parser", optimized_input_parser)
    graph.update_node("data_processor", optimized_data_processor)
    graph.update_node("heavy_analysis", optimized_heavy_analysis)
    
    return graph
```

### Optimization 4: Improving Response Generator

```python
# Add to optimized_performance_graph.py

# Optimized response generator
def optimized_response_generator(state):
    """Optimized version of response generator."""
    simulate_work(0.15)  # Same base operation time
    
    # Create a more efficient cache key
    input_text = state["input"]
    cache_key = hash(input_text)  # Better cache key
    
    if cache_key in state["cache"]:
        # If using cache, return immediately
        state["response"] = state["cache"][cache_key]
    else:
        # Generate response
        response = f"Analysis complete! Found {len(state['analysis_results'])} insights."
        state["response"] = response
        state["cache"][cache_key] = response
    
    # Add only essential metadata
    state["metadata"]["completion_time"] = time.time()
    
    return state

# Update the build_graph function
def build_graph():
    # Need to import random and time for these functions
    import random
    import time
    
    # Start with the original graph
    graph = build_original_graph()
    
    # Replace all optimized nodes
    graph.update_node("input_parser", optimized_input_parser)
    graph.update_node("data_processor", optimized_data_processor)
    graph.update_node("heavy_analysis", optimized_heavy_analysis)
    graph.update_node("response_generator", optimized_response_generator)
    
    return graph
```

## Step 4: Testing the Optimizations

Let's update our script to test the optimized graph:

```python
# Add to performance_optimization.py

# Import the optimized graph
from optimized_performance_graph import build_graph as build_optimized_graph

def compare_performance():
    """Compare original and optimized graph performance."""
    # Sample input
    initial_state = {
        "input": "This is a sample input text for performance testing. It contains enough words to demonstrate various performance characteristics and optimization opportunities."
    }
    
    # Create both graphs
    original_graph = build_graph()
    optimized_graph = build_optimized_graph()
    
    # Setup debuggers
    original_debugger = Debugger(
        original_graph,
        enable_profiling=True,
        profiling_level=ProfilingLevel.DETAILED
    )
    
    optimized_debugger = Debugger(
        optimized_graph,
        enable_profiling=True,
        profiling_level=ProfilingLevel.DETAILED
    )
    
    # Run benchmarks
    print("\n===== Running Benchmarks =====")
    
    # Create benchmark configuration
    benchmark_config = {
        "runs": 5,
        "configs": [
            {"name": "original", "debugger": original_debugger},
            {"name": "optimized", "debugger": optimized_debugger}
        ],
        "test_cases": [
            {"input": initial_state, "id": "default"}
        ]
    }
    
    # Run benchmarks and collect results
    results = {
        "original": {"times": [], "memory": []},
        "optimized": {"times": [], "memory": []}
    }
    
    for config in benchmark_config["configs"]:
        debugger = config["debugger"]
        config_name = config["name"]
        print(f"Running benchmark for {config_name}...")
        
        for i in range(benchmark_config["runs"]):
            # Run the graph
            start_time = time.time()
            result = debugger.run(initial_state)
            end_time = time.time()
            
            # Get execution time
            execution_time = (end_time - start_time) * 1000  # Convert to ms
            results[config_name]["times"].append(execution_time)
            
            # Get memory usage
            memory_profile = debugger.get_memory_profile()
            results[config_name]["memory"].append(memory_profile["peak_memory"])
    
    # Calculate averages
    for config_name, data in results.items():
        avg_time = sum(data["times"]) / len(data["times"])
        avg_memory = sum(data["memory"]) / len(data["memory"])
        data["avg_time"] = avg_time
        data["avg_memory"] = avg_memory
    
    # Show comparison
    print("\n===== Performance Comparison =====")
    original_time = results["original"]["avg_time"]
    optimized_time = results["optimized"]["avg_time"]
    time_improvement = (original_time - optimized_time) / original_time * 100
    
    original_memory = results["original"]["avg_memory"]
    optimized_memory = results["optimized"]["avg_memory"]
    memory_improvement = (original_memory - optimized_memory) / original_memory * 100
    
    print(f"Original execution time: {original_time:.2f}ms")
    print(f"Optimized execution time: {optimized_time:.2f}ms")
    print(f"Time improvement: {time_improvement:.1f}%")
    
    print(f"\nOriginal peak memory: {original_memory:.2f}MB")
    print(f"Optimized peak memory: {optimized_memory:.2f}MB")
    print(f"Memory improvement: {memory_improvement:.1f}%")
    
    # Visualize the comparison
    import matplotlib.pyplot as plt
    
    # Time comparison
    plt.figure(figsize=(10, 6))
    plt.bar(["Original", "Optimized"], [original_time, optimized_time])
    plt.title("Execution Time Comparison")
    plt.ylabel("Time (ms)")
    plt.savefig("time_comparison.png")
    
    # Memory comparison
    plt.figure(figsize=(10, 6))
    plt.bar(["Original", "Optimized"], [original_memory, optimized_memory])
    plt.title("Memory Usage Comparison")
    plt.ylabel("Memory (MB)")
    plt.savefig("memory_comparison.png")
    
    print("\nComparison visualizations saved to time_comparison.png and memory_comparison.png")
    
    # Run final profiling for the optimized graph
    print("\n===== Final Profiling of Optimized Graph =====")
    optimized_debugger.show_profile_report()
    
    # Visualize optimized performance
    optimized_debugger.visualize_performance_heatmap(
        metric="execution_time", 
        output_file="performance_heatmap_after.png"
    )
    
    return results

if __name__ == "__main__":
    print("Running initial profiling...")
    run_profiling()
    
    print("\n" + "="*50)
    print("Running optimization comparison...")
    compare_performance()
```

Run the updated script to see the performance improvements:

```bash
python performance_optimization.py
```

## Step 5: Advanced Optimization Techniques

Let's add a section demonstrating more advanced optimization techniques:

```python
# Add to performance_optimization.py

def advanced_optimization_demo():
    """Demonstrate more advanced optimization techniques."""
    print("\n===== Advanced Optimization Techniques =====")
    
    # Import optimized graph
    from optimized_performance_graph import build_graph as build_optimized_graph
    optimized_graph = build_optimized_graph()
    
    # Initialize debugger
    debugger = Debugger(
        optimized_graph,
        enable_profiling=True,
        profiling_level=ProfilingLevel.COMPREHENSIVE,
        state_tracking=True
    )
    
    # Sample input
    initial_state = {
        "input": "This is a sample input text for performance testing. It contains enough words to demonstrate various performance characteristics and optimization opportunities."
    }
    
    # 1. Parallel processing demonstration
    print("\n1. Parallel Processing")
    print("---------------------")
    
    # Configure parallel execution
    debugger.configure_execution(enable_parallel=True)
    
    # Run with parallel execution
    result = debugger.run(initial_state)
    debugger.show_execution_timing()
    
    # 2. Selective state tracking
    print("\n2. Selective State Tracking")
    print("-------------------------")
    
    # Configure selective state tracking
    debugger.configure_state_tracking(
        include_paths=["processed_data", "response"],
        exclude_paths=["metadata", "cache"]
    )
    
    # Run with selective tracking
    result = debugger.run(initial_state)
    debugger.show_state_size_analysis()
    
    # 3. Continuous profiling
    print("\n3. Continuous Profiling")
    print("---------------------")
    
    # Enable continuous profiling
    debugger.enable_continuous_profiling(
        metrics=["execution_time", "memory_usage"],
        log_file="continuous_profile.log"
    )
    
    # Run multiple times
    for i in range(3):
        result = debugger.run(initial_state)
    
    # Show profiling trends
    debugger.show_profiling_trends()
    
    # 4. Custom optimization metrics
    print("\n4. Custom Optimization Metrics")
    print("---------------------------")
    
    # Define a custom metric
    def tokens_per_millisecond(node_stats, execution_stats):
        if node_stats["node"] == "data_processor":
            tokens = execution_stats.get("word_count", 0)
            time_ms = node_stats["execution_time"]
            return tokens / time_ms if time_ms > 0 else 0
        return 0
    
    # Register the custom metric
    debugger.register_performance_metric(
        "tokens_per_ms", 
        tokens_per_millisecond
    )
    
    # Run and show custom metric
    result = debugger.run(initial_state)
    custom_metrics = debugger.get_performance_metrics()
    print("Custom metric (tokens/ms):", custom_metrics["tokens_per_ms"])
    
    return "Advanced optimization techniques demonstrated"

if __name__ == "__main__":
    print("Running initial profiling...")
    run_profiling()
    
    print("\n" + "="*50)
    print("Running optimization comparison...")
    compare_performance()
    
    print("\n" + "="*50)
    print("Demonstrating advanced techniques...")
    advanced_optimization_demo()
```

## Summary

In this tutorial, you've learned:

1. **Performance Profiling**
   - How to profile a LangGraph application
   - Identifying execution bottlenecks
   - Analyzing memory usage and state size

2. **Optimization Strategies**
   - Efficient data handling and avoiding deep copies
   - Optimizing string operations
   - Preventing unnecessary computations
   - Improving cache effectiveness
   - Reducing memory footprint

3. **Measuring Improvements**
   - Comparing before and after performance
   - Visualizing performance gains
   - Running benchmarks for reliable comparisons

4. **Advanced Techniques**
   - Parallel processing
   - Selective state tracking
   - Continuous profiling
   - Custom performance metrics

## Best Practices for Performance Optimization

1. **Profile First**: Always profile before optimizing to identify actual bottlenecks
2. **Optimize Incrementally**: Make one change at a time and measure the impact
3. **Focus on Hotspots**: Spend time optimizing the nodes consuming the most resources
4. **Minimize State Size**: Keep the state as small as possible
5. **Avoid Unnecessary Operations**: Eliminate redundant computations
6. **Use Efficient Data Structures**: Choose appropriate data structures for your operations
7. **Implement Smart Caching**: Cache results of expensive operations
8. **Document Optimizations**: Keep track of optimizations and their impacts

## Next Steps

- [Performance Profiling](../user_guides/performance_profiling.md) for more profiling techniques
- [Graph Execution Monitoring](../user_guides/graph_execution_monitoring.md) for monitoring execution patterns
- [Custom Debugging Extensions](../user_guides/custom_debugging_extensions.md) for creating custom profiling tools 