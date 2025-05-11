# Custom Debugging Extensions

This guide explains how to extend the KFM debugging tools with custom functionality to meet your specific debugging needs.

## Overview

The KFM debugging toolkit is designed to be extensible, allowing you to create custom components that integrate seamlessly with the core functionality. Key extension points include:

- **Custom visualizers** - Create specialized visualizations for your data
- **Custom analyzers** - Implement specialized analysis algorithms
- **Custom formatters** - Format data in ways specific to your application
- **Custom metrics** - Track application-specific performance and quality metrics
- **Integration plugins** - Connect to other tools and services

## Basic Extension Patterns

### Creating a Custom Visualizer

Custom visualizers allow you to display state or execution data in specialized ways:

```python
from kfm_debugging import Debugger, BaseVisualizer

# Define a custom visualizer
class NetworkGraphVisualizer(BaseVisualizer):
    """Visualizes state data as a network graph."""
    
    def __init__(self, options=None):
        super().__init__(options or {})
        self.options = {
            "node_size": 20,
            "edge_width": 2,
            "layout": "force-directed",
            **self.options
        }
    
    def visualize(self, data, output_file=None):
        """Visualize the data as a network graph."""
        # Implementation using NetworkX, Graphviz, or similar
        import networkx as nx
        import matplotlib.pyplot as plt
        
        # Create a graph from the data
        G = nx.Graph()
        
        # Add nodes and edges based on the data
        for key, value in data.items():
            if isinstance(value, dict):
                G.add_node(key)
                for subkey in value:
                    G.add_node(f"{key}.{subkey}")
                    G.add_edge(key, f"{key}.{subkey}")
        
        # Draw the graph
        plt.figure(figsize=(10, 8))
        nx.draw(
            G, 
            with_labels=True, 
            node_size=self.options["node_size"],
            width=self.options["edge_width"]
        )
        
        # Save or display
        if output_file:
            plt.savefig(output_file)
            return f"Graph saved to {output_file}"
        else:
            plt.show()
            return "Graph displayed"

# Register and use the custom visualizer
debugger = Debugger(graph)
debugger.register_visualizer("network", NetworkGraphVisualizer())

# Use the custom visualizer
result = debugger.run(initial_state)
debugger.visualize_state(
    visualizer="network",
    output_file="state_network.png"
)
```

### Creating a Custom Analyzer

Custom analyzers allow you to perform specialized analysis on state or execution data:

```python
from kfm_debugging import Debugger, BaseAnalyzer

# Define a custom analyzer
class SentimentAnalyzer(BaseAnalyzer):
    """Analyzes sentiment in text fields of the state."""
    
    def __init__(self, options=None):
        super().__init__(options or {})
        self.options = {
            "text_fields": ["message", "response", "content"],
            "threshold": 0.5,
            **self.options
        }
        
        # Initialize sentiment analysis model
        from transformers import pipeline
        self.sentiment_model = pipeline("sentiment-analysis")
    
    def analyze(self, state):
        """Analyze text fields in the state for sentiment."""
        results = {}
        
        # Extract and analyze text fields
        for field in self.options["text_fields"]:
            if field in state and isinstance(state[field], str):
                text = state[field]
                sentiment = self.sentiment_model(text)[0]
                results[field] = {
                    "text": text[:100] + "..." if len(text) > 100 else text,
                    "sentiment": sentiment["label"],
                    "score": sentiment["score"]
                }
        
        return results

# Register and use the custom analyzer
debugger = Debugger(graph)
debugger.register_analyzer("sentiment", SentimentAnalyzer())

# Use the custom analyzer
result = debugger.run(initial_state)
sentiment_analysis = debugger.analyze_state(analyzer="sentiment")
print("Sentiment Analysis:", sentiment_analysis)
```

### Creating a Custom Formatter

Custom formatters allow you to display data in specialized formats:

```python
from kfm_debugging import Debugger, BaseFormatter

# Define a custom formatter
class HighlightFormatter(BaseFormatter):
    """Formats state data with syntax highlighting and annotations."""
    
    def __init__(self, options=None):
        super().__init__(options or {})
        self.options = {
            "highlight_fields": ["query", "response"],
            "highlight_color": "yellow",
            "truncate_length": 200,
            **self.options
        }
    
    def format(self, data):
        """Format the data with highlights for specific fields."""
        from rich.console import Console
        from rich.syntax import Syntax
        from rich.panel import Panel
        
        console = Console(record=True)
        
        # Format each top-level item
        for key, value in data.items():
            if key in self.options["highlight_fields"]:
                # Highlight important fields
                if isinstance(value, str):
                    # Truncate if needed
                    if len(value) > self.options["truncate_length"]:
                        value = value[:self.options["truncate_length"]] + "..."
                    
                    # Display as syntax-highlighted text
                    syntax = Syntax(
                        value, 
                        "text", 
                        theme="monokai",
                        word_wrap=True
                    )
                    console.print(Panel(syntax, title=key, border_style=self.options["highlight_color"]))
                else:
                    # For non-string values
                    console.print(f"[bold]{key}[/bold]:", value)
            else:
                # Regular fields
                console.print(f"[dim]{key}[/dim]:", value)
        
        # Return the rendered output as a string
        return console.export_text()

# Register and use the custom formatter
debugger = Debugger(graph)
debugger.register_formatter("highlight", HighlightFormatter())

# Use the custom formatter
result = debugger.run(initial_state)
formatted_state = debugger.format_state(formatter="highlight")
print(formatted_state)
```

## Advanced Extension Patterns

### Creating a Custom Metric Tracker

Custom metric trackers allow you to monitor application-specific metrics:

```python
from kfm_debugging import Debugger, BaseMetricTracker

# Define a custom metric tracker
class LLMMetricTracker(BaseMetricTracker):
    """Tracks LLM-specific metrics like token usage and response quality."""
    
    def __init__(self, options=None):
        super().__init__(options or {})
        self.options = {
            "track_tokens": True,
            "track_latency": True,
            "track_quality": True,
            **self.options
        }
        self.metrics = {
            "prompt_tokens": [],
            "completion_tokens": [],
            "total_tokens": [],
            "latency": [],
            "quality_scores": []
        }
        
        # Initialize quality evaluation if needed
        if self.options["track_quality"]:
            try:
                from evaluate import load
                self.rouge = load("rouge")
            except ImportError:
                print("Warning: 'evaluate' package not installed. Quality tracking disabled.")
                self.options["track_quality"] = False
    
    def track(self, state, node, timestamp):
        """Track LLM metrics based on state at this node."""
        # Track token usage if present in state
        if self.options["track_tokens"]:
            if "usage" in state and isinstance(state["usage"], dict):
                usage = state["usage"]
                self.metrics["prompt_tokens"].append(usage.get("prompt_tokens", 0))
                self.metrics["completion_tokens"].append(usage.get("completion_tokens", 0))
                self.metrics["total_tokens"].append(usage.get("total_tokens", 0))
        
        # Track latency if timestamps available
        if self.options["track_latency"] and hasattr(self, "last_timestamp"):
            latency = timestamp - self.last_timestamp
            self.metrics["latency"].append(latency)
        
        # Store timestamp for next latency calculation
        self.last_timestamp = timestamp
        
        # Track quality if reference and prediction are available
        if (self.options["track_quality"] and 
            "reference" in state and 
            "prediction" in state):
            
            score = self.rouge.compute(
                predictions=[state["prediction"]],
                references=[state["reference"]]
            )
            self.metrics["quality_scores"].append(score["rouge1"])
        
        return self.metrics
    
    def get_report(self):
        """Generate a report with statistics about tracked metrics."""
        report = {}
        
        for metric_name, values in self.metrics.items():
            if values:
                report[metric_name] = {
                    "count": len(values),
                    "total": sum(values),
                    "min": min(values),
                    "max": max(values),
                    "avg": sum(values) / len(values) if values else 0
                }
        
        return report

# Register and use the custom metric tracker
debugger = Debugger(graph)
debugger.register_metric_tracker("llm", LLMMetricTracker())

# Enable the custom tracker
debugger.enable_metric_tracking(tracker="llm")

# Run the graph
result = debugger.run(initial_state)

# Get the metrics report
llm_metrics = debugger.get_metrics_report(tracker="llm")
print("LLM Metrics:", llm_metrics)
```

### Creating an Integration Plugin

Integration plugins allow you to connect the debugger to external tools and services:

```python
from kfm_debugging import Debugger, BaseIntegrationPlugin

# Define a custom integration plugin
class SlackNotifier(BaseIntegrationPlugin):
    """Sends notifications to Slack for important debugging events."""
    
    def __init__(self, webhook_url, options=None):
        super().__init__(options or {})
        self.webhook_url = webhook_url
        self.options = {
            "notify_on_error": True,
            "notify_on_completion": False,
            "include_state": False,
            "channel": "#debugging",
            **self.options
        }
        
        # Initialize Slack client
        import requests
        self.requests = requests
    
    def on_error(self, error, node, state):
        """Called when an error occurs during graph execution."""
        if not self.options["notify_on_error"]:
            return
        
        # Create the message
        message = {
            "channel": self.options["channel"],
            "username": "KFM Debugger",
            "text": f"⚠️ Error in graph execution: {type(error).__name__}",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Error in graph execution*\n\n*Node:* `{node}`\n*Error:* `{type(error).__name__}: {str(error)}`"
                    }
                }
            ]
        }
        
        # Add state if configured
        if self.options["include_state"]:
            import json
            state_str = json.dumps(state, indent=2)
            message["blocks"].append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*State at error:*\n```{state_str[:1000]}...```" if len(state_str) > 1000 else f"*State at error:*\n```{state_str}```"
                }
            })
        
        # Send to Slack
        self.requests.post(self.webhook_url, json=message)
    
    def on_completion(self, result, execution_time):
        """Called when graph execution completes successfully."""
        if not self.options["notify_on_completion"]:
            return
        
        # Create the message
        message = {
            "channel": self.options["channel"],
            "username": "KFM Debugger",
            "text": f"✅ Graph execution completed in {execution_time:.2f}ms",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Graph execution completed*\n\n*Execution time:* {execution_time:.2f}ms"
                    }
                }
            ]
        }
        
        # Send to Slack
        self.requests.post(self.webhook_url, json=message)

# Register and use the integration plugin
debugger = Debugger(graph)
slack_plugin = SlackNotifier(
    webhook_url="https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
    options={"notify_on_completion": True}
)
debugger.register_plugin("slack", slack_plugin)

# Run the graph
try:
    result = debugger.run(initial_state)
except Exception as e:
    # The plugin will automatically notify Slack about the error
    raise
```

## Creating Custom Debug Commands

Custom debug commands allow you to extend the debugger's interactive interface:

```python
from kfm_debugging import Debugger, BaseDebugCommand

# Define a custom debug command
class SaveStateCommand(BaseDebugCommand):
    """Command to save the current state to a file during debugging."""
    
    def get_command_info(self):
        """Return information about the command."""
        return {
            "name": "save",
            "description": "Save the current state to a file",
            "usage": "save [filename]",
            "aliases": ["s"]
        }
    
    def execute(self, args, state, debugger_instance):
        """Execute the command with the given arguments."""
        import json
        
        # Default filename if not provided
        filename = args[0] if args else f"state_{id(state)}.json"
        
        # Ensure it has a .json extension
        if not filename.endswith(".json"):
            filename += ".json"
        
        # Save the state to the file
        with open(filename, "w") as f:
            json.dump(state, f, indent=2)
        
        return f"State saved to {filename}"

# Register and use the custom debug command
debugger = Debugger(graph)
debugger.register_debug_command(SaveStateCommand())

# Now when debugging, you can use the 'save' command at the breakpoint prompt
# For example, when a breakpoint is hit, you can type:
# > save my_state.json
```

## Comprehensive Extension Example

Here's a more comprehensive example combining multiple custom extensions:

```python
from kfm_debugging import Debugger
from kfm_debugging.extensions import BaseVisualizer, BaseAnalyzer, BaseFormatter, BaseMetricTracker

# Custom visualizer for state structure
class StateStructureVisualizer(BaseVisualizer):
    # Implementation details...

# Custom analyzer for language quality
class LanguageQualityAnalyzer(BaseAnalyzer):
    # Implementation details...

# Custom formatter for JSON sequences
class JSONSequenceFormatter(BaseFormatter):
    # Implementation details...

# Custom metric tracker for API calls
class APICallTracker(BaseMetricTracker):
    # Implementation details...

# Create and configure the debugger with all extensions
debugger = Debugger(graph)

# Register the custom components
debugger.register_visualizer("structure", StateStructureVisualizer())
debugger.register_analyzer("language", LanguageQualityAnalyzer())
debugger.register_formatter("json_seq", JSONSequenceFormatter())
debugger.register_metric_tracker("api", APICallTracker())

# Enable the relevant tracking
debugger.enable_metric_tracking(tracker="api")

# Run the graph
result = debugger.run(initial_state)

# Use the custom extensions
structure_viz = debugger.visualize_state(
    visualizer="structure", 
    output_file="state_structure.png"
)

language_analysis = debugger.analyze_state(analyzer="language")

formatted_results = debugger.format_state(
    formatter="json_seq",
    include_history=True
)

api_metrics = debugger.get_metrics_report(tracker="api")
```

## Extension Development Guidelines

When creating custom extensions, follow these best practices:

### General Guidelines

- **Follow the base class interfaces**: Implement all required methods
- **Handle errors gracefully**: Catch and report exceptions
- **Use consistent naming**: Follow the debugger's naming conventions
- **Document your extensions**: Include docstrings and usage examples
- **Make options configurable**: Use an options dictionary for configuration
- **Validate inputs**: Check inputs for correct types and values
- **Provide sensible defaults**: Don't require configuration for basic functionality

### Extension-Specific Guidelines

#### For Visualizers

- Support both file output and in-memory visualization
- Handle large datasets gracefully (sampling, pagination)
- Use clear, accessible color schemes
- Provide legends and annotations
- Support customization of visual elements

#### For Analyzers

- Return structured analysis results
- Provide confidence scores where applicable
- Include actionable insights or recommendations
- Be computationally efficient for large states
- Allow granular analysis of specific state components

#### For Formatters

- Maintain all essential information
- Use consistent styling
- Support multiple output formats
- Handle complex nested structures
- Consider accessibility (e.g., screen readers)

#### For Metric Trackers

- Track metrics efficiently
- Provide statistical summaries
- Support time-series analysis
- Enable comparison between runs
- Export data in standard formats

## Sharing and Publishing Extensions

To share your custom extensions with others:

1. **Package your extensions**:
   ```python
   # my_extensions.py
   from kfm_debugging.extensions import BaseVisualizer, BaseAnalyzer

   class MyVisualizer(BaseVisualizer):
       # Implementation...

   class MyAnalyzer(BaseAnalyzer):
       # Implementation...
   ```

2. **Publish as a package**:
   ```
   setup.py
   my_kfm_extensions/
       __init__.py
       visualizers.py
       analyzers.py
       formatters.py
       metrics.py
   ```

3. **Document usage**:
   ```python
   # Usage example in README
   from kfm_debugging import Debugger
   from my_kfm_extensions import MyVisualizer, MyAnalyzer

   debugger = Debugger(graph)
   debugger.register_visualizer("custom", MyVisualizer())
   debugger.register_analyzer("custom", MyAnalyzer())
   ```

## Troubleshooting Extension Development

Common issues and solutions:

- **Extension not found**: Ensure proper registration and naming
- **Incompatible types**: Check input/output type compatibility
- **Performance issues**: Profile and optimize resource-intensive operations
- **Visualization errors**: Check output file permissions and formats
- **State access issues**: Verify state structure assumptions
- **Plugin conflicts**: Test compatibility with other extensions

## Next Steps

- [Debugging API Reference](../api/index.md) for details on the base classes
- [Graph Execution Monitoring](graph_execution_monitoring.md) for execution flow analysis
- [Performance Profiling](performance_profiling.md) for detailed performance analysis
- [Custom Extensions Example](../examples/custom_extensions_example.md) for a practical example

For more information on creating specific types of extensions, see the [Advanced Extensions Guide](../examples/advanced_extensions_guide.md). 