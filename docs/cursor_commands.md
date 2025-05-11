# LangGraph Cursor AI Command Palette

This document provides comprehensive documentation for the Cursor AI command palette integration with LangGraph.

## Overview

The Cursor AI command palette allows you to use special slash commands (`/lg`) to debug, visualize, and inspect your LangGraph applications directly from the Cursor AI interface.

## Available Commands

### General Commands

* **`/lg help`** - Display a list of all available commands
* **`/lg help <command>`** - Get detailed help for a specific command

### Breakpoint Commands

* **`/lg breakpoint --node <node_name> [--condition <condition>]`** - Set a breakpoint on a specific node
* **`/lg breakpoints`** - List all currently set breakpoints
* **`/lg clear-breakpoint [--node <node_name>] [--all]`** - Clear specific or all breakpoints

### Inspection Commands

* **`/lg inspect [--field <field_path>] [--format <format>]`** - Inspect current state
* **`/lg compare --state1 <state_id> --state2 <state_id> [--format <format>]`** - Compare two states
* **`/lg timeline [--limit <n>] [--node <node_name>]`** - Show execution timeline
* **`/lg search --term <search_term> [--case-sensitive]`** - Search state history

### Visualization Commands

* **`/lg visualize [--type <type>] [--output <file_path>] [--interactive]`** - Create graph visualizations

## Interactive Debugging Commands

The Cursor AI command palette provides comprehensive interactive debugging capabilities for LangGraph applications.

### Starting and Controlling Debug Sessions

* **`/lg debug <graph_name> [--state <initial_state_json>]`** - Start interactive debugging session for a graph
* **`/lg step [--into] [--over] [--out]`** - Execute the next node in the graph
* **`/lg continue [--all]`** - Continue execution until next breakpoint or completion
* **`/lg back [--steps <number>]`** - Step backward to previous node
* **`/lg run-to --node <node_name>`** - Run execution until a specific node is reached
* **`/lg run-to-condition --condition <condition_expression>`** - Run until a condition is met

### State Manipulation

* **`/lg modify-state --field <field_path> --value <json_value>`** - Modify a value in the current state
* **`/lg watch --field <field_path> [--condition <expression>]`** - Set a watch expression on a state field
* **`/lg watches`** - List all active watches
* **`/lg clear-watch --id <watch_id>`** - Clear a watch by ID
* **`/lg clear-all-watches`** - Clear all watches

### Session Management

* **`/lg save-session [--name <session_name>]`** - Save current debugging session
* **`/lg load-session --name <session_name>`** - Load a saved debugging session
* **`/lg list-sessions`** - List saved debugging sessions

## Command Details

### Visualization

The visualization command creates visual representations of your LangGraph execution.

```
/lg visualize [--type <type>] [--output <file_path>] [--interactive]
```

#### Arguments

* `--type` - Type of visualization (valid options: `basic`, `execution`, `timing`)
* `--output` - Custom file path for saving the visualization (default: auto-generated based on type)
* `--interactive` - Create an interactive visualization (default: false)

#### Examples

```
/lg visualize
/lg visualize --type execution
/lg visualize --type timing --output timing_graph.png
/lg visualize --interactive
```

#### Features

* **Robust Error Handling** - The visualizer will always attempt to produce a useful visualization, even when:
  * The graph structure can't be properly extracted
  * The graph object is missing expected attributes
  * The layout algorithm encounters errors
  * The execution history is empty

* **Fallback Mechanisms** - When issues are encountered:
  * Creates a simplified graph structure based on available information
  * Falls back to spring layout if hierarchical layout fails
  * Generates helpful error messages that explain visualization limitations
  * Always produces a visualization rather than failing with an error

* **Detailed Edge Information** - Shows edge conditions when available
* **Automatic Node Styling** - Colors nodes based on their function (start, normal, end)

## Integration

The command palette is automatically initialized when you import and use the LangGraph debugging modules. All commands are prefixed with `/lg` to avoid conflicts with other commands.

## Debugging Workflow

1. Start with `/lg help` to see available commands
2. Set breakpoints using `/lg breakpoint --node <node_name>`
3. Run your LangGraph application
4. Use `/lg inspect` to examine state when execution pauses
5. Continue execution after inspection
6. After execution, use `/lg timeline` to view the execution path
7. Use `/lg visualize` to create a visualization of the execution
8. Use `/lg search` to find specific values in the execution history

## Examples

### Debugging a Failing Node

```python
# Set a breakpoint on the node that's failing
/lg breakpoint --node process_data --condition "state.get('error') is not None"

# Run your LangGraph application
# When the breakpoint is hit, inspect the state
/lg inspect

# Look at the error field specifically
/lg inspect --field error

# Continue execution
# After execution completes, visualize the execution path
/lg visualize --type execution
```

### Comparing States

```python
# Show the execution timeline
/lg timeline

# Compare states from different points in the execution
/lg compare --state1 2 --state2 3
```

### Visualizing Performance

```python
# Create a timing visualization
/lg visualize --type timing --output performance.png
```

### Interactive Debugging Workflow

Here's an example of an interactive debugging session:

```
/lg debug my_graph --state '{"input": "test data"}'
/lg breakpoint --node process_data
/lg continue
/lg inspect
/lg modify-state --field config.timeout --value 30
/lg step
/lg back
/lg run-to --node analyze_results
/lg watch --field results.error --condition "len(error) > 0"
/lg save-session --name debug_1
```

### State Modification

Manipulate the state during debugging:

```
/lg modify-state --field user.preferences.theme --value "dark"
/lg modify-state --field config.enabled --value true
/lg modify-state --field data.items --value '[1, 2, 3]'
```

### Watch Expressions

Set watches on state fields:

```
/lg watch --field user.score
/lg watch --field errors --condition "len(errors) > 0"
/lg watch --field performance.latency --condition "latency > 100"
```

## Troubleshooting

If you encounter issues:

1. Check that your LangGraph application has been run at least once before using visualization commands
2. Ensure your graph is properly initialized and accessible
3. If visualization doesn't show all expected nodes, check that they were executed in your run
4. For complex graphs, consider using `--type basic` for a simpler visualization

For additional assistance, please refer to the LangGraph documentation or use the `/lg help` command. 