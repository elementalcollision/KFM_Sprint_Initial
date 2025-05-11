# Rich Visualization Helpers for Cursor AI

This document provides comprehensive documentation for the rich visualization capabilities in Cursor AI for LangGraph debugging.

## Overview

The rich visualization helpers extend the basic Cursor AI command palette with enhanced visualization capabilities for:

1. **Rich State Inspection** - Advanced state formatting with different visualization modes
2. **Enhanced Graph Visualization** - Improved graph rendering with multiple visualization types
3. **State Difference Highlighting** - Visual comparisons between states with highlighted changes
4. **Execution Replay** - Interactive replay of execution history with visualization

## Rich State Inspection

### Commands

* **`/lg inspect-rich [--field <field_path>] [--format <format>] [--depth <depth>]`**
  
  Display current state with rich formatting and visualization options.

  Options:
  - `--field <field_path>`: Show only a specific field using dot notation (e.g., `user.preferences.theme`)
  - `--format <format>`: Display format, one of: `pretty` (default), `json`, `table`, or `compact`
  - `--depth <depth>`: Maximum depth to display for nested objects (default: 3)

  Examples:
  ```
  /lg inspect-rich
  /lg inspect-rich --field user.preferences
  /lg inspect-rich --format table
  /lg inspect-rich --format pretty --depth 2
  ```

* **`/lg search-rich --term <search_term> [--field <field_path>] [--format <format>]`**
  
  Search state history with rich formatted results.

  Options:
  - `--term <search_term>`: Required. Term to search for
  - `--field <field_path>`: Optional field path to restrict the search
  - `--format <format>`: Display format for results

  Examples:
  ```
  /lg search-rich --term "error"
  /lg search-rich --term "John" --field user.name
  /lg search-rich --term "error" --format table
  ```

### State Formatting Types

The rich state inspection supports multiple formatting types:

1. **Pretty Format** (`pretty`):
   - Hierarchical indented view
   - Color-coded values by type
   - Truncation of large collections
   - Best for viewing complex nested state

2. **JSON Format** (`json`):
   - Standard JSON formatting with indentation
   - No color coding or special formatting
   - Complete representation of the state
   - Useful for copying/pasting state data

3. **Table Format** (`table`):
   - Tabular view with key-value pairs
   - Shows top-level keys and summarizes nested objects
   - Fixed-width columns for easier reading
   - Good for overview of state properties

4. **Compact Format** (`compact`):
   - Single-line representation
   - Summarizes collections and nested objects
   - Shows key counts for nested structures
   - Ideal for quick state snapshots with minimal space

## Enhanced Graph Visualization

### Commands

* **`/lg visualize-rich [--type <type>] [--output <file_path>] [--interactive] [--focus <node_name>]`**
  
  Create enhanced visualizations of the graph structure and execution.

  Options:
  - `--type <type>`: Visualization type, one of: `basic` (default), `execution`, `timing`, `focus`
  - `--output <file_path>`: Path to save the visualization (default is auto-generated)
  - `--interactive`: Create an interactive HTML visualization instead of static image
  - `--focus <node_name>`: Node to focus on (especially useful with `--type focus`)

  Examples:
  ```
  /lg visualize-rich
  /lg visualize-rich --type execution
  /lg visualize-rich --type timing --output graph.png
  /lg visualize-rich --type focus --focus process_data
  /lg visualize-rich --interactive
  ```

### Visualization Types

1. **Basic Visualization** (`basic`):
   - Shows the complete graph structure
   - All nodes and edges with standard styling
   - Clear node labels and structure
   - Best for understanding the full graph topology

2. **Execution Visualization** (`execution`):
   - Highlights the execution path through the graph
   - Shows the flow of execution with special styling
   - Displays the current node (if applicable)
   - Ideal for seeing how execution progressed

3. **Timing Visualization** (`timing`):
   - Color-codes nodes based on execution time
   - Shows duration information for each node
   - Highlights performance hotspots
   - Best for performance analysis

4. **Focus Visualization** (`focus`):
   - Centers on a specific node and its connections
   - Highlights the focused node and direct neighbors
   - Simplifies complex graphs by showing relevant parts
   - Useful for debugging specific node behavior

### Interactive Mode

The `--interactive` flag creates an HTML-based interactive visualization with:

- Pan and zoom controls
- Node hovering for details
- Draggable nodes for custom arrangement
- Tooltip information for nodes and edges

## State Difference Highlighting

### Commands

* **`/lg diff-rich --state1 <id_or_index> --state2 <id_or_index> [--mode <mode>] [--format <format>]`**
  
  Create rich visual comparisons between two states.

  Options:
  - `--state1 <id_or_index>`: First state to compare (required)
  - `--state2 <id_or_index>`: Second state to compare (required)
  - `--mode <mode>`: Comparison mode, one of: `detailed` (default), `basic`, `structural`
  - `--format <format>`: Display format, one of: `color` (default), `table`, `side-by-side`

  Examples:
  ```
  /lg diff-rich --state1 0 --state2 1
  /lg diff-rich --state1 abc-123 --state2 def-456 --mode detailed
  /lg diff-rich --state1 0 --state2 1 --format side-by-side
  /lg diff-rich --state1 0 --state2 1 --mode basic --format table
  ```

### Diff Formats

1. **Color Format** (`color`):
   - Color-coded changes (green for additions, red for removals, yellow for modifications)
   - Hierarchical view showing nested changes
   - Complete path information for each change
   - Best for detailed inspection of differences

2. **Table Format** (`table`):
   - Tabular view with paths, change types, and values
   - Structured format for easy scanning
   - Summary statistics for changes
   - Good for overview of all changes

3. **Side-by-Side Format** (`side-by-side`):
   - Two-column view showing both states
   - Direct comparison of values
   - Highlighted differences
   - Ideal for comparing complex structures

### Comparison Modes

1. **Detailed Mode** (`detailed`):
   - Shows all differences including nested structures
   - Provides complete path information
   - Includes both old and new values for modifications
   - Best for thorough analysis

2. **Basic Mode** (`basic`):
   - Shows top-level changes only
   - Summarizes nested changes
   - Less verbose than detailed mode
   - Good for quick overview

3. **Structural Mode** (`structural`):
   - Focuses on structure rather than values
   - Shows where keys/items were added or removed
   - Ignores value changes if structure is unchanged
   - Useful for schema/structure changes

## Execution Replay

### Commands

* **`/lg replay [--step <step_number>] [--show-state <true/false>] [--format <text/graphical>]`**
  
  Replay the execution history with visualization.

  Options:
  - `--step <step_number>`: Execution step to display (default: 0)
  - `--show-state <true/false>`: Whether to show state information (default: true)
  - `--format <format>`: Display format, one of: `text` (default) or `graphical`

  Examples:
  ```
  /lg replay
  /lg replay --step 5
  /lg replay --format graphical
  /lg replay --show-state false
  ```

* **`/lg timeline-rich [--width <characters>] [--include-states] [--format <format>]`**
  
  Show execution timeline with rich formatting.

  Options:
  - `--width <characters>`: Width of the timeline in characters (default: 80)
  - `--include-states <true/false>`: Whether to include state information (default: false)
  - `--format <format>`: Display format, one of: `standard` (default) or `detailed`

  Examples:
  ```
  /lg timeline-rich
  /lg timeline-rich --width 100 --include-states
  /lg timeline-rich --format detailed
  ```

### Replay Features

The execution replay functionality includes:

1. **Timeline Visualization**:
   - Visual representation of progress through execution
   - Position indicator showing current step
   - Step navigation controls

2. **State Display**:
   - Rich formatted state at the current execution point
   - Configurable detail level
   - Option to hide for cleaner display

3. **Execution Path**:
   - Shows the sequence of nodes executed
   - Highlights the current node
   - Provides context for the current step

4. **Graphical Mode**:
   - Creates graph visualization at current step
   - Highlights execution path and current node
   - Saves image for external viewing

## Integration with Existing Commands

The rich visualization commands extend the basic commands with enhanced capabilities but work seamlessly with the existing command set. You can mix and match basic and rich commands as needed.

For example:
- Use `/lg breakpoint` to set breakpoints
- Use `/lg inspect-rich` to view state with rich formatting
- Use `/lg visualize-rich` to create enhanced graph visualizations
- Use `/lg diff-rich` to compare states

## Example Usage Scenarios

### Debugging a Complex State Structure

```
# Set a breakpoint and run until hit
/lg breakpoint --node validate_data --condition "state['errors'] != []"

# When breakpoint is hit, inspect state
/lg inspect-rich
/lg inspect-rich --field data.validation_results --format table

# Check what changed from the previous state
/lg diff-rich --state1 prev --state2 current --format side-by-side
```

### Analyzing Performance Issues

```
# Visualize execution timing
/lg visualize-rich --type timing

# Focus on a specific slow node
/lg visualize-rich --type focus --focus slow_node

# Check state changes around the slow node
/lg diff-rich --state1 before_slow --state2 after_slow
```

### Reviewing Execution Flow

```
# Show execution timeline
/lg timeline-rich --format detailed

# Replay execution step by step
/lg replay --step 0
/lg replay --step 1
/lg replay --step 2

# Create a visualization of the full execution
/lg visualize-rich --type execution --interactive
```

## Custom Integration

The rich visualization helpers can be extended or customized for specific needs. The core functionality is in the `src/rich_visualizations.py` module, which provides:

- `format_rich_state` - For rich state formatting
- `format_field_path` - For accessing and formatting specific fields
- `create_rich_graph_visualization` - For enhanced graph visualization
- `create_rich_diff_visualization` - For state difference visualization
- `create_execution_replay_visualization` - For execution replay

These functions can be called directly or used to create additional custom commands. 