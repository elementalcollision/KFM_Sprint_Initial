# Advanced Debugging Tutorial

This tutorial demonstrates advanced debugging techniques using the KFM debugging tools with a more complex LangGraph application. You'll learn how to debug complex flows, handle errors effectively, and optimize performance.

## Prerequisites

Before starting this tutorial, make sure you have:

- Completed the [Basic Debugging Tutorial](basic_debugging_tutorial.md)
- Python 3.9 or higher installed
- LangGraph 0.0.43 or higher installed
- The KFM debugging tools installed (`pip install kfm-debugging-tools`)

## Setup: A Complex Multi-Agent Graph

First, let's create a more complex LangGraph application that simulates a multi-agent conversation system:

```python
# multi_agent_graph.py
from langgraph.graph import StateGraph, END
import random
import time

# State definition
state_model = {
    "messages": [],
    "current_agent": None,
    "context": {},
    "errors": [],
    "is_complete": False,
    "max_turns": 10,
    "turn_count": 0,
}

# Agent functions
def moderator(state):
    """Decides which agent should speak next or if the conversation should end."""
    state["turn_count"] += 1
    
    # Simulate processing time
    time.sleep(0.05)
    
    # Check if we've reached the maximum turns
    if state["turn_count"] >= state["max_turns"]:
        state["is_complete"] = True
        return {"is_complete": True}
    
    # Randomly choose the next agent
    agents = ["researcher", "critic", "creator"]
    state["current_agent"] = random.choice(agents)
    
    return {"current_agent": state["current_agent"]}

def researcher(state):
    """Simulates a research agent that provides information."""
    # Simulate processing time
    time.sleep(0.2)
    
    # Occasionally introduce an error
    if random.random() < 0.1:  # 10% chance of error
        raise ValueError("Research database unavailable")
    
    message = {
        "role": "researcher",
        "content": f"Research findings for turn {state['turn_count']}: Some simulated research data."
    }
    
    state["messages"].append(message)
    state["context"]["has_research"] = True
    
    return {"messages": state["messages"], "context": state["context"]}

def critic(state):
    """Simulates a critic agent that analyzes and evaluates."""
    # Simulate processing time
    time.sleep(0.1)
    
    # Check if there's research to critique
    if not state["context"].get("has_research", False):
        message = {
            "role": "critic",
            "content": "I need research to provide a critique."
        }
    else:
        message = {
            "role": "critic",
            "content": f"Critique for turn {state['turn_count']}: Analysis of the research."
        }
    
    state["messages"].append(message)
    state["context"]["has_critique"] = True
    
    return {"messages": state["messages"], "context": state["context"]}

def creator(state):
    """Simulates a creator agent that generates content."""
    # Simulate processing time
    time.sleep(0.15)
    
    # Generate based on available context
    has_research = state["context"].get("has_research", False)
    has_critique = state["context"].get("has_critique", False)
    
    if has_research and has_critique:
        content_quality = "high-quality"
    elif has_research or has_critique:
        content_quality = "moderate-quality"
    else:
        content_quality = "basic"
    
    message = {
        "role": "creator",
        "content": f"{content_quality} content for turn {state['turn_count']}."
    }
    
    state["messages"].append(message)
    
    return {"messages": state["messages"]}

def should_end(state):
    """Condition to check if we should end the conversation."""
    return state.get("is_complete", False)

# Define the graph
def build_graph():
    # Create the graph
    graph = StateGraph(state_model)
    
    # Add nodes
    graph.add_node("moderator", moderator)
    graph.add_node("researcher", researcher)
    graph.add_node("critic", critic)
    graph.add_node("creator", creator)
    
    # Add conditional edges
    graph.add_conditional_edges(
        "moderator",
        should_end,
        {
            True: END,
            False: lambda state: state.get("current_agent")
        }
    )
    
    # Connect all agents back to the moderator
    graph.add_edge("researcher", "moderator")
    graph.add_edge("critic", "moderator")
    graph.add_edge("creator", "moderator")
    
    # Set entry point
    graph.set_entry_point("moderator")
    
    return graph

# Create and run the graph
if __name__ == "__main__":
    graph = build_graph()
    result = graph.invoke({})
    print(f"Conversation completed in {result['turn_count']} turns")
    print(f"Total messages: {len(result['messages'])}")
```

Save this file and run it to make sure it works:

```bash
python multi_agent_graph.py
```

## Setting Up Advanced Debugging

Now, let's set up comprehensive debugging for this complex graph:

```python
# multi_agent_debug.py
from multi_agent_graph import build_graph
from kfm_debugging import Debugger, LogLevel, VisualizationMode, ProfilingLevel

# Create the graph
graph = build_graph()

# Initialize the debugger with advanced options
debugger = Debugger(
    graph,
    log_level=LogLevel.DEBUG,
    state_tracking=True,
    enable_breakpoints=True,
    visualization_mode=VisualizationMode.RICH,
    enable_profiling=True,
    profiling_level=ProfilingLevel.DETAILED,
    execution_monitoring=True
)

# Configure custom state diff formatting
debugger.configure_state_diff(
    show_unchanged=False,
    max_string_length=50
)

# Run the graph with initial state
if __name__ == "__main__":
    initial_state = {
        "max_turns": 5  # Limit to 5 turns for demonstration
    }
    
    try:
        result = debugger.run(initial_state)
        print("Execution completed successfully")
    except Exception as e:
        print(f"Execution failed: {type(e).__name__}: {e}")
```

## Advanced Technique 1: Flow Visualization and Analysis

Let's add flow visualization and analysis:

```python
# Add to multi_agent_debug.py
if __name__ == "__main__":
    # ... existing code ...
    
    # Visualize the graph structure
    debugger.visualize_graph(output_file="multi_agent_graph.png")
    
    # Visualize the execution flow
    debugger.visualize_execution_path(output_file="execution_flow.png")
    
    # Show execution timing
    print("\n===== Execution Timing =====")
    debugger.show_execution_timing()
    
    # Visualize state changes over time
    debugger.visualize_state_timeline(
        path=["messages", "context"],
        output_file="state_timeline.png"
    )
```

## Advanced Technique 2: Targeted Breakpoints

Let's add intelligent, conditional breakpoints:

```python
# Add to multi_agent_debug.py
if __name__ == "__main__":
    # Define a condition to break only when the creator agent lacks both research and critique
    def creator_lacks_context(state):
        if state.get("current_agent") != "creator":
            return False
        
        context = state.get("context", {})
        return not (context.get("has_research", False) or context.get("has_critique", False))
    
    # Add conditional breakpoint
    debugger.add_breakpoint(
        "creator",
        condition=creator_lacks_context,
        action=lambda state: print("BREAKPOINT: Creator lacks research and critique context")
    )
    
    # Add a breakpoint that will fire if a message has specific content
    def message_contains_error(state):
        messages = state.get("messages", [])
        if not messages:
            return False
        
        last_message = messages[-1]
        return "error" in last_message.get("content", "").lower()
    
    debugger.add_breakpoint(
        condition=message_contains_error,
        action=lambda state: print(f"BREAKPOINT: Error message detected: {state['messages'][-1]}")
    )
    
    # ... existing code ...
```

## Advanced Technique 3: Error Handling and Recovery

Let's add advanced error handling and recovery:

```python
# Add to multi_agent_debug.py
if __name__ == "__main__":
    # Configure error handling
    debugger.configure_error_handling(
        recover_from_errors=True,
        log_errors=True,
        max_retries=3
    )
    
    # Define custom error recovery strategies
    def researcher_error_recovery(error, state, node):
        """Custom recovery strategy for the researcher node."""
        print(f"Recovering from error in researcher: {error}")
        
        # Add a fallback message
        fallback_message = {
            "role": "researcher",
            "content": "Unable to access research database. Using cached data."
        }
        state["messages"].append(fallback_message)
        state["context"]["has_research"] = True
        state["errors"].append(str(error))
        
        return state
    
    # Register the recovery strategy
    debugger.register_error_recovery("researcher", researcher_error_recovery)
    
    # ... existing code ...
    
    try:
        result = debugger.run(initial_state)
        print("Execution completed successfully")
        
        # Analyze any errors that occurred but were recovered from
        if result.get("errors"):
            print("\n===== Recovered Errors =====")
            for i, error in enumerate(result["errors"]):
                print(f"Error {i+1}: {error}")
    except Exception as e:
        print(f"Execution failed: {type(e).__name__}: {e}")
        
        # Get detailed error context
        error_context = debugger.get_error_context(e)
        print(f"\nError occurred in node: {error_context.node}")
        print(f"State at error: {error_context.state}")
        print("\nSuggested fixes:")
        for suggestion in error_context.suggestions:
            print(f"- {suggestion}")
```

## Advanced Technique 4: Performance Profiling and Optimization

Let's add comprehensive performance profiling:

```python
# Add to multi_agent_debug.py
if __name__ == "__main__":
    # ... existing code ...
    
    # After running the graph, show performance analysis
    print("\n===== Performance Analysis =====")
    
    # Show basic profile report
    debugger.show_profile_report()
    
    # Identify bottlenecks
    bottlenecks = debugger.identify_bottlenecks(threshold_percent=20)
    print("\nPerformance Bottlenecks:")
    for node, stats in bottlenecks.items():
        print(f"- {node}: {stats['execution_time']:.2f}ms ({stats['percentage']:.1f}%)")
    
    # Show node state impact (memory usage)
    print("\nNode State Impact (Memory):")
    debugger.show_node_state_impact()
    
    # Generate performance visualization
    debugger.visualize_performance_heatmap(
        metric="execution_time",
        output_file="performance_heatmap.png"
    )
    
    # Get optimization suggestions
    suggestions = debugger.get_optimization_suggestions(bottlenecks)
    print("\nOptimization Suggestions:")
    for node, suggestion in suggestions.items():
        print(f"Node: {node}")
        print(f"- Issue: {suggestion['issue']}")
        print(f"- Suggestion: {suggestion['suggestion']}")
```

## Advanced Technique 5: State History Analysis

Let's add detailed state history analysis:

```python
# Add to multi_agent_debug.py
if __name__ == "__main__":
    # ... existing code ...
    
    # After running the graph, analyze state history
    print("\n===== State History Analysis =====")
    
    # Show state transitions for specific paths
    print("\nMessage Count History:")
    debugger.show_state_path_history(
        path=["messages"],
        map_function=lambda messages: len(messages)
    )
    
    # Show context evolution
    print("\nContext Evolution:")
    debugger.show_state_path_history(path=["context"])
    
    # Show agent sequencing
    print("\nAgent Sequence:")
    debugger.show_state_path_history(path=["current_agent"])
    
    # Analyze state growth
    print("\nState Size Growth:")
    debugger.show_state_size_timeline()
    
    # Find the step with the biggest state change
    biggest_change = debugger.find_biggest_state_change()
    print(f"\nBiggest state change occurred at step {biggest_change['step']} ({biggest_change['node']})")
    print(f"Change size: {biggest_change['change_size']} bytes")
    debugger.show_state_diff(step_index=biggest_change['step'])
```

## Advanced Technique 6: Integrating with External Tools

Let's add integration with external monitoring and notification tools:

```python
# Add to multi_agent_debug.py
from kfm_debugging.plugins import SlackNotifier, PrometheusMetricsExporter

if __name__ == "__main__":
    # Add Slack notifications for errors (commented out by default)
    """
    slack_plugin = SlackNotifier(
        webhook_url="https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
        options={
            "notify_on_error": True,
            "notify_on_completion": True,
            "include_state": True,
            "channel": "#debugging"
        }
    )
    debugger.register_plugin("slack", slack_plugin)
    """
    
    # Add metrics export for monitoring
    metrics_plugin = PrometheusMetricsExporter(
        metrics_file="debugging_metrics.prom",
        options={
            "record_node_timing": True,
            "record_state_size": True,
            "record_error_count": True
        }
    )
    debugger.register_plugin("metrics", metrics_plugin)
    
    # ... existing code ...
```

## Running the Advanced Debugging Session

When you run this script, you'll see comprehensive debugging information and visualizations:

```bash
python multi_agent_debug.py
```

## Summary of Advanced Techniques

In this tutorial, you've learned how to:

1. **Flow Visualization and Analysis**
   - Visualize graph structure and execution flow
   - Analyze node execution timing and sequencing
   - Create state change timelines

2. **Targeted Breakpoints**
   - Create conditional breakpoints based on state properties
   - Execute custom actions when breakpoints are hit
   - Debug specific error conditions

3. **Error Handling and Recovery**
   - Configure automatic error recovery strategies
   - Implement node-specific error handlers
   - Analyze recoverable errors

4. **Performance Profiling and Optimization**
   - Identify performance bottlenecks
   - Analyze memory usage impact
   - Get actionable optimization suggestions

5. **State History Analysis**
   - Track state evolution over time
   - Find significant state changes
   - Analyze relationships between state properties

6. **External Tool Integration**
   - Send notifications to external services
   - Export metrics for monitoring
   - Create custom debugging plugins

## Next Steps

Now that you've mastered advanced debugging techniques, you might want to explore:

- [Custom Debugging Extensions](../user_guides/custom_debugging_extensions.md)
- [Performance Profiling](../user_guides/performance_profiling.md)
- [Graph Execution Monitoring](../user_guides/graph_execution_monitoring.md)

You can also apply these techniques to your own LangGraph applications to solve complex debugging challenges and optimize performance. 