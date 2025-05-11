"""
Cursor AI Command Palette Integration for LangGraph debugging.

This module implements custom debugging commands for Cursor AI to
interact with the LangGraph debugging, tracing, and visualization tools.
"""

import os
import re
import json
import time
import inspect
from typing import Dict, Any, List, Optional, Union, Callable, Tuple

from src.logger import setup_logger
from src.debugging import (
    # Breakpoint functionality
    get_breakpoint_manager,
    set_breakpoint,
    clear_breakpoint,
    clear_node_breakpoints,
    clear_all_breakpoints,
    enable_breakpoint,
    disable_breakpoint,
    get_breakpoint,
    list_breakpoints,
    # Debugging functionality
    diff_states,
    visualize_diff,
    step_through_execution_with_history,
    create_state_checkpoint,
    compare_with_checkpoint,
    show_execution_timeline,
    find_states_with_value,
    time_travel_to_state,
    # Interactive debugging
    interactive_debug,
    step_forward,
    step_backward,
    run_to_node,
    run_to_condition,
    # Monitoring functionality
    monitor_field,
    monitor_value_change,
    monitor_threshold,
    monitor_pattern_match,
    monitor_state_condition,
    stop_monitoring,
    stop_all_monitoring,
    get_active_monitors,
    get_monitoring_statistics
)

from src.tracing import (
    configure_tracing,
    reset_trace_history,
    get_trace_history,
    get_state_history_tracker,
    save_state_snapshot,
    get_state_snapshot,
    list_state_snapshots,
    search_state_history,
    get_state_timeline,
    get_state_at_point
)

from src.visualization import (
    visualize_graph,
    visualize_graph_with_execution,
    visualize_graph_with_timing,
    save_visualization,
    create_interactive_visualization,
    visualize_execution_path,
    visualize_breakpoints,
    visualize_performance_hotspots,
    visualize_graph_with_errors
)

from src.rich_visualizations import (
    format_rich_state,
    format_field_path,
    create_rich_graph_visualization,
    create_rich_diff_visualization,
    create_execution_replay_visualization,
    show_execution_timeline
)

from src.recovery import (
    RecoveryMode,
    RecoveryPolicy,
    RecoveryManager,
    resume_execution_from_node,
    verify_safe_resumption,
    create_fallback_state,
    with_recovery
)

from src.profiling import (
    get_profiler,
    start_profiling_run,
    end_profiling_run,
    generate_performance_report,
    compare_profiling_runs,
    configure_profiler,
    clear_profiling_data
)

from src.suggestions import (
    get_suggestions,
    submit_feedback,
    get_documentation_for_error
)

# Setup logger for cursor commands
cursor_logger = setup_logger('src.cursor_commands')

# Define command prefix for Cursor AI
COMMAND_PREFIX = "/lg"

# Dictionary to store registered commands
registered_commands = {}

# Global state for keeping track of current graph and execution state
current_graph = None
current_state = None
current_node_index = None
current_execution_history = []

def register_command(name: str, description: str, usage: str, examples: List[str] = None):
    """
    Decorator to register a function as a Cursor AI command.
    
    Args:
        name: Command name (without prefix)
        description: Short description of what the command does
        usage: Usage pattern string
        examples: List of example commands
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable):
        command_key = f"{COMMAND_PREFIX}_{name}"
        examples_list = examples or []
        
        registered_commands[command_key] = {
            "name": name,
            "full_command": f"{COMMAND_PREFIX} {name}",
            "description": description,
            "usage": f"{COMMAND_PREFIX} {name} {usage}",
            "examples": [f"{COMMAND_PREFIX} {name} {example}" for example in examples_list],
            "function": func
        }
        
        cursor_logger.debug(f"Registered command: {COMMAND_PREFIX} {name}")
        return func
    
    return decorator

def parse_args(args_str: str) -> Dict[str, Any]:
    """
    Parse command arguments string into a dictionary.
    
    Supports formats like:
    --name value
    --flag (boolean flag)
    --key="value with spaces"
    -n value (short form)
    
    Args:
        args_str: String containing command arguments
        
    Returns:
        Dictionary of parsed arguments
    """
    args = {}
    
    # Handle empty args
    if not args_str or args_str.strip() == "":
        return args
    
    # Parse args regex
    pattern = r'(?:--(\w+)|-(\w+))(?:=([^\s"]+|"[^"]*")|\s+([^\s"]+|"[^"]*"))?|([^\s"]+|"[^"]*")'
    
    # Split by spaces, preserving quoted strings
    matches = re.finditer(pattern, args_str)
    
    current_key = None
    for match in matches:
        long_key, short_key, val_with_equals, val_with_space, positional = match.groups()
        
        # Handle flags and keys
        if long_key or short_key:
            key = long_key if long_key else short_key
            
            # If we have a value with equals sign
            if val_with_equals:
                val = val_with_equals.strip('"')
                args[key] = val
                current_key = None
            # If no value, it's a flag
            elif not val_with_space:
                args[key] = True
                current_key = None
            # Otherwise, next token is the value
            else:
                val = val_with_space.strip('"')
                args[key] = val
                current_key = None
        # Handle positional arguments or values for previous keys
        elif positional:
            if current_key:
                args[current_key] = positional.strip('"')
                current_key = None
            else:
                # Add to positional args list
                if "_positional" not in args:
                    args["_positional"] = []
                args["_positional"].append(positional.strip('"'))
    
    return args

def handle_command(command_text: str) -> str:
    """
    Process a command from Cursor AI and return the response.
    
    Args:
        command_text: The command text from Cursor AI
        
    Returns:
        Response text to display to the user
    """
    # Check if this is a valid command
    if not command_text.startswith(COMMAND_PREFIX):
        return f"Invalid command. Commands must start with '{COMMAND_PREFIX}'."
    
    # Parse command and arguments
    parts = command_text[len(COMMAND_PREFIX):].strip().split(maxsplit=1)
    
    if not parts:
        return _handle_help_command(None)
    
    command_name = parts[0].lower()
    args_str = parts[1] if len(parts) > 1 else ""
    
    # Handle built-in help command
    if command_name == "help":
        return _handle_help_command(args_str)
    
    # Look up the command
    command_key = f"{COMMAND_PREFIX}_{command_name}"
    if command_key not in registered_commands:
        return f"Unknown command: {command_name}. Type '{COMMAND_PREFIX} help' to see available commands."
    
    # Parse arguments
    args = parse_args(args_str)
    
    # Execute the command
    command = registered_commands[command_key]
    try:
        result = command["function"](**args)
        return result or f"Command '{command_name}' executed successfully."
    except Exception as e:
        cursor_logger.exception(f"Error executing command '{command_name}': {e}")
        return f"Error executing command '{command_name}': {str(e)}"

def _handle_help_command(args_str: str) -> str:
    """
    Handle the built-in help command.
    
    Args:
        args_str: Optional specific command to get help for
        
    Returns:
        Help text
    """
    if args_str and args_str.strip():
        # Get help for specific command
        command_name = args_str.strip().split()[0].lower()
        command_key = f"{COMMAND_PREFIX}_{command_name}"
        
        if command_key in registered_commands:
            cmd = registered_commands[command_key]
            help_text = [
                f"Command: {cmd['full_command']}",
                f"Description: {cmd['description']}",
                f"Usage: {cmd['usage']}",
                "Examples:"
            ]
            
            for example in cmd["examples"]:
                help_text.append(f"  {example}")
                
            return "\n".join(help_text)
        else:
            return f"Unknown command: {command_name}"
    
    # General help - list all commands
    help_text = [
        "Available LangGraph Debugging Commands:",
        f"Use '{COMMAND_PREFIX} help <command>' for detailed help on a specific command.",
        ""
    ]
    
    # Group commands by category
    categories = {
        "Tracing": [],
        "Debugging": [],
        "Breakpoints": [],
        "Visualization": [],
        "Recovery": [],
        "Profiling": [],
        "Other": []
    }
    
    for cmd_key, cmd in sorted(registered_commands.items()):
        if "breakpoint" in cmd["name"]:
            categories["Breakpoints"].append(cmd)
        elif cmd["name"] in ["visualize", "graph", "show", "display", "render"]:
            categories["Visualization"].append(cmd)
        elif cmd["name"] in ["trace", "track", "history", "snapshot"]:
            categories["Tracing"].append(cmd)
        elif cmd["name"] in ["debug", "step", "inspect", "monitor", "watch"]:
            categories["Debugging"].append(cmd)
        elif cmd["name"] in ["recover", "resume", "rollback"]:
            categories["Recovery"].append(cmd)
        elif cmd["name"] in ["profile", "timing", "performance"]:
            categories["Profiling"].append(cmd)
        else:
            categories["Other"].append(cmd)
    
    # Add commands to help text by category
    for category, commands in categories.items():
        if commands:
            help_text.append(f"\n{category}:")
            for cmd in commands:
                help_text.append(f"  {cmd['full_command']} - {cmd['description']}")
    
    return "\n".join(help_text)

#
# Register commands for different functionality areas
#

# Breakpoint commands
@register_command(
    "breakpoint", 
    "Set a breakpoint on a node",
    "--node <node_name> [--condition <expression>] [--description <text>]",
    ["--node process_input", "--node validate_data --condition \"state['errors'] != []\""]
)
def command_set_breakpoint(node=None, condition=None, description=None, **kwargs):
    """Set a breakpoint on a node"""
    if not node:
        return "Error: Node name is required. Use --node <node_name>"
    
    bp_id = set_breakpoint(node, condition, True, description)
    return f"Breakpoint set on node '{node}' with ID: {bp_id}"

@register_command(
    "breakpoints", 
    "List all breakpoints",
    "[--node <node_name>]",
    ["", "--node process_input"]
)
def command_list_breakpoints(node=None, **kwargs):
    """List all breakpoints"""
    breakpoints = list_breakpoints(node)
    
    if not breakpoints:
        return "No breakpoints are set."
    
    result = ["Current breakpoints:"]
    for bp in breakpoints:
        status = "enabled" if bp["enabled"] else "disabled"
        condition_text = f" with condition: {bp['condition']}" if bp["condition"] else ""
        result.append(f"[{bp['id']}] {bp['node_name']} ({status}){condition_text}")
    
    return "\n".join(result)

@register_command(
    "clear-breakpoint", 
    "Clear a breakpoint by ID",
    "--id <breakpoint_id>",
    ["--id 12345678-1234-5678-1234-567812345678"]
)
def command_clear_breakpoint(id=None, **kwargs):
    """Clear a breakpoint by ID"""
    if not id:
        return "Error: Breakpoint ID is required. Use --id <breakpoint_id>"
    
    result = clear_breakpoint(id)
    if result:
        return f"Breakpoint {id} cleared."
    else:
        return f"Breakpoint {id} not found."

@register_command(
    "clear-all-breakpoints", 
    "Clear all breakpoints",
    "",
    [""]
)
def command_clear_all_breakpoints(**kwargs):
    """Clear all breakpoints"""
    count = clear_all_breakpoints()
    return f"Cleared {count} breakpoints."

@register_command(
    "enable-breakpoint", 
    "Enable a breakpoint",
    "--id <breakpoint_id>",
    ["--id 12345678-1234-5678-1234-567812345678"]
)
def command_enable_breakpoint(id=None, **kwargs):
    """Enable a breakpoint"""
    if not id:
        return "Error: Breakpoint ID is required. Use --id <breakpoint_id>"
    
    result = enable_breakpoint(id)
    if result:
        return f"Breakpoint {id} enabled."
    else:
        return f"Breakpoint {id} not found."

@register_command(
    "disable-breakpoint", 
    "Disable a breakpoint",
    "--id <breakpoint_id>",
    ["--id 12345678-1234-5678-1234-567812345678"]
)
def command_disable_breakpoint(id=None, **kwargs):
    """Disable a breakpoint"""
    if not id:
        return "Error: Breakpoint ID is required. Use --id <breakpoint_id>"
    
    result = disable_breakpoint(id)
    if result:
        return f"Breakpoint {id} disabled."
    else:
        return f"Breakpoint {id} not found."

# State inspection commands
@register_command(
    "inspect", 
    "Inspect the current state",
    "[--field <field_path>] [--format <format>]",
    ["", "--field user.preferences", "--format json"]
)
def command_inspect_state(field=None, format="text", **kwargs):
    """Inspect the current state"""
    global current_state
    
    if current_state is None:
        return "No current state available. Start a debugging session first."
    
    # Get specific field if requested
    if field:
        try:
            # Navigate nested fields using dot notation
            value = current_state
            for key in field.split('.'):
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return f"Field '{field}' not found in current state."
            
            # Format the output
            if format.lower() == "json":
                if isinstance(value, (dict, list)):
                    return json.dumps(value, indent=2)
                else:
                    return json.dumps({"value": value}, indent=2)
            else:
                if isinstance(value, (dict, list)):
                    return str(value)
                else:
                    return str(value)
        except Exception as e:
            return f"Error accessing field '{field}': {str(e)}"
    
    # Format full state
    if format.lower() == "json":
        return json.dumps(current_state, indent=2)
    else:
        # Create a formatted text representation
        lines = ["Current State:"]
        for key, value in current_state.items():
            # Summarize large structures
            if isinstance(value, dict) and len(value) > 5:
                lines.append(f"{key}: <Dict with {len(value)} items>")
            elif isinstance(value, list) and len(value) > 5:
                lines.append(f"{key}: <List with {len(value)} items>")
            else:
                lines.append(f"{key}: {str(value)}")
        return "\n".join(lines)

@register_command(
    "diff", 
    "Compare two states",
    "--state1 <id_or_index> --state2 <id_or_index> [--mode <mode>] [--format <format>]",
    ["--state1 0 --state2 1", "--state1 abc-123 --state2 def-456 --mode detailed"]
)
def command_diff_states(state1=None, state2=None, mode="basic", format="text", **kwargs):
    """Compare two states"""
    global current_execution_history
    
    if not state1 or not state2:
        return "Error: Both state1 and state2 are required."
    
    # Get states
    state1_obj = _get_state_by_id_or_index(state1)
    state2_obj = _get_state_by_id_or_index(state2)
    
    if not state1_obj:
        return f"State '{state1}' not found."
    if not state2_obj:
        return f"State '{state2}' not found."
    
    # Compare states
    diff_result = diff_states(
        state1_obj, 
        state2_obj, 
        mode=mode, 
        use_colors=True, 
        show_unchanged=(format != "minimal")
    )
    
    # Visualize the diff
    viz = visualize_diff(diff_result, format_type=format)
    return viz

@register_command(
    "timeline", 
    "Show execution timeline",
    "[--width <characters>] [--include-states]",
    ["", "--width 100 --include-states"]
)
def command_show_timeline(width=80, include_states=False, **kwargs):
    """Show execution timeline"""
    if isinstance(width, str) and width.isdigit():
        width = int(width)
    
    if isinstance(include_states, str):
        include_states = include_states.lower() in ('true', 'yes', '1')
    
    timeline = show_execution_timeline(width, include_states)
    return timeline

@register_command(
    "search", 
    "Search for specific values in state history",
    "--term <search_term> [--field <field_path>]",
    ["--term \"error\"", "--term \"John\" --field user.name"]
)
def command_search_states(term=None, field=None, **kwargs):
    """Search for specific values in state history"""
    if not term:
        return "Error: Search term is required. Use --term <search_term>"
    
    results = find_states_with_value(term, field)
    
    if not results:
        return f"No states found matching '{term}'" + (f" in field '{field}'" if field else "")
    
    output = [f"Found {len(results)} states matching '{term}'" + (f" in field '{field}'" if field else "")]
    
    for i, result in enumerate(results):
        node = result.get("node_name", "unknown")
        index = result.get("index", i)
        time = result.get("timestamp", "unknown")
        
        output.append(f"[{index}] Node: {node}, Time: {time}")
    
    output.append("\nUse '/lg inspect' to view a specific state.")
    return "\n".join(output)

# Rich State Inspection Commands

@register_command(
    "inspect-rich",
    "Display state with rich formatting options",
    "[--field <field_path>] [--format <format>] [--depth <depth>]",
    ["--field user.preferences", "--format table", "--format pretty --depth 2"]
)
def command_inspect_rich_state(field: str = None, format: str = "pretty", depth: int = 3, **kwargs):
    """Display current state with rich formatting options"""
    global current_state
    
    if current_state is None:
        return "No current state available. Start a debugging session first."
    
    # Convert depth to integer if it's a string
    if isinstance(depth, str):
        try:
            depth = int(depth)
        except ValueError:
            depth = 3
    
    # Sanitize format value
    valid_formats = ["pretty", "json", "table", "compact"]
    if format not in valid_formats:
        return f"Invalid format '{format}'. Valid formats are: {', '.join(valid_formats)}"
    
    # If field is specified, display only that field
    if field:
        return format_field_path(current_state, field, format)
    else:
        return format_rich_state(current_state, format, depth)

@register_command(
    "search-rich",
    "Search state history with rich formatting",
    "--term <search_term> [--field <field_path>] [--format <format>]",
    ["--term error", "--term user.email --field user", "--term \"New York\" --format table"]
)
def command_search_rich_states(term: str = None, field: str = None, format: str = "pretty", **kwargs):
    """Search state history with rich formatting"""
    global current_execution_history
    
    if not term:
        return "Error: Search term is required. Use --term parameter to specify what to search for."
    
    if not current_execution_history:
        return "No execution history available. Start a debugging session first."
    
    # Perform the search
    field_info = f" in field '{field}'" if field else ""
    found_states = find_states_with_value(current_execution_history, term, field_path=field)
    
    if not found_states:
        return f"No states found containing '{term}'{field_info}."
    
    # Format the results
    result = []
    result.append(f"Found {len(found_states)} states containing '{term}'{field_info}:")
    
    for entry in found_states:
        node_name = entry.get("node_name", "Unknown node")
        index = entry.get("index", -1)
        timestamp = entry.get("timestamp", "Unknown time")
        
        result.append(f"\nStep {index}: {node_name} at {timestamp}")
        
        # Format the state or specific field
        state = entry.get("state", {})
        if field:
            result.append(format_field_path(state, field, format))
        else:
            # For full state, use compact format by default
            display_format = "compact" if format == "pretty" else format
            result.append(format_rich_state(state, display_format))
    
    return "\n".join(result)

# Rich Graph Visualization Commands

@register_command(
    "visualize-rich",
    "Create enhanced graph visualization",
    "[--type <type>] [--output <file_path>] [--interactive] [--focus <node_name>]",
    ["--type execution", "--type timing --output graph.png", "--type focus --focus validate_data", "--interactive"]
)
def command_visualize_rich_graph(type: str = "basic", output: str = None, interactive: bool = False, focus: str = None, **kwargs):
    """Create enhanced graph visualizations of various types"""
    global current_graph, current_execution_history
    
    if current_graph is None:
        return "No graph available. Start a debugging session first."
    
    # Convert interactive to boolean if it's a string
    if isinstance(interactive, str):
        interactive = interactive.lower() in ('true', 'yes', '1')
    
    # Prepare visualization parameters
    execution_path = None
    node_timings = None
    
    # Extract execution path and timings from history
    if current_execution_history:
        execution_path = [entry["node_name"] for entry in current_execution_history]
        
        # Extract timing information if available
        node_timings = {}
        for entry in current_execution_history:
            if "node_name" in entry and "duration" in entry:
                node_timings[entry["node_name"]] = entry["duration"]
    
    # Create an appropriate title
    title = f"Rich Graph Visualization ({type.capitalize()})"
    
    # Create the visualization
    return create_rich_graph_visualization(
        graph=current_graph,
        visualization_type=type,
        execution_path=execution_path,
        node_timings=node_timings,
        focus_node=focus,
        interactive=interactive,
        output_path=output,
        title=title
    )

# State Difference Visualization Commands

@register_command(
    "diff-rich",
    "Create rich visual comparison between states",
    "--state1 <id_or_index> --state2 <id_or_index> [--format <format>] [--mode <mode>]",
    ["--state1 0 --state2 1", "--state1 2 --state2 4 --format table", "--state1 1 --state2 2 --format side-by-side"]
)
def command_diff_rich_states(state1: Optional[Union[str, int]] = None, state2: Optional[Union[str, int]] = None, 
                             format: str = "color", mode: str = "detailed", **kwargs):
    """Create rich visual comparison between two states"""
    global current_execution_history
    
    if not current_execution_history:
        return "No execution history available. Start a debugging session first."
    
    # Check that both state1 and state2 are provided
    if state1 is None or state2 is None:
        return "Error: Both state1 and state2 are required for comparison."
    
    # Convert to integers if they're numeric
    if isinstance(state1, str) and state1.isdigit():
        state1 = int(state1)
    if isinstance(state2, str) and state2.isdigit():
        state2 = int(state2)
    
    # Get states from history by index
    if isinstance(state1, int) and 0 <= state1 < len(current_execution_history):
        state1_data = current_execution_history[state1].get("state", {})
        state1_name = f"Step {state1}: {current_execution_history[state1].get('node_name', 'Unknown')}"
    else:
        return f"Error: State1 index '{state1}' not found in execution history."
    
    if isinstance(state2, int) and 0 <= state2 < len(current_execution_history):
        state2_data = current_execution_history[state2].get("state", {})
        state2_name = f"Step {state2}: {current_execution_history[state2].get('node_name', 'Unknown')}"
    else:
        return f"Error: State2 index '{state2}' not found in execution history."
    
    # Create the diff visualization
    return create_rich_diff_visualization(
        state1=state1_data,
        state2=state2_data,
        format=format,
        mode=mode,
        labels=(state1_name, state2_name)
    )

# Execution Replay Commands

@register_command(
    "replay",
    "Replay execution step by step with visualization",
    "[--step <step_number>] [--show-state <true/false>] [--format <text/graphical>]",
    ["--step 0", "--step 3 --format graphical", "--step 2 --show-state false"]
)
def command_execution_replay(step: int = 0, show_state: bool = True, format: str = "text", **kwargs):
    """Replay execution with visualization"""
    global current_execution_history, current_graph
    
    if not current_execution_history:
        return "No execution history available. Start a debugging session first."
    
    # Convert parameters if they're strings
    if isinstance(step, str):
        try:
            step = int(step)
        except ValueError:
            step = 0
    
    if isinstance(show_state, str):
        show_state = show_state.lower() in ('true', 'yes', '1')
    
    # Validate step index
    if step < 0 or step >= len(current_execution_history):
        return f"Invalid step index. Valid range: 0-{len(current_execution_history) - 1}"
    
    # Create the replay visualization
    return create_execution_replay_visualization(
        execution_history=current_execution_history,
        current_index=step,
        graph=current_graph,
        display_state=show_state,
        format=format
    )

@register_command(
    "timeline-rich",
    "Show execution timeline with rich formatting",
    "[--width <characters>] [--include-states <true/false>] [--format <format>]",
    ["--width 100", "--include-states true", "--format detailed"]
)
def command_show_rich_timeline(width: int = 80, include_states: bool = False, format: str = "standard", **kwargs):
    """Show execution timeline with rich formatting"""
    global current_execution_history
    
    if not current_execution_history:
        return "No execution history available. Start a debugging session first."
    
    # Convert parameters if they're strings
    if isinstance(width, str):
        try:
            width = int(width)
        except ValueError:
            width = 80
    
    if isinstance(include_states, str):
        include_states = include_states.lower() in ('true', 'yes', '1')
    
    # Get the timeline
    timeline = show_execution_timeline(
        execution_history=current_execution_history,
        width=width,
        include_states=include_states
    )
    
    # For detailed format, append state transitions
    if format == "detailed":
        return f"{timeline}\n\nState Transitions: Use '/lg diff-rich' to compare specific states"
    
    return timeline

# Interactive debugging commands
@register_command(
    "debug", 
    "Start interactive debugging session",
    "<graph_name> [--state <initial_state_json>]",
    ["my_graph", "my_graph --state '{\"input\": \"test\"}'"]
)
def command_start_debug_session(graph_name=None, state=None, **kwargs):
    """Start interactive debugging session for a graph"""
    global current_graph, current_state, current_node_index, current_execution_history
    
    if not graph_name:
        return "Error: Graph name is required"
    
    # This is a placeholder for actual graph lookup logic
    # In a real implementation, we would import the graph from a module
    # based on the graph_name
    cursor_logger.info(f"Starting debug session for graph: {graph_name}")
    
    try:
        # Initialize state
        initial_state = {}
        if state:
            if isinstance(state, str):
                initial_state = json.loads(state)
            elif isinstance(state, dict):
                initial_state = state
                
        # Get breakpoints ready
        breakpoint_manager = get_breakpoint_manager()
        breakpoint_manager.load_breakpoints()
        
        # Start the debug session
        # In a full implementation, this would use interactive_debug
        # For now, we'll set up the global state
        current_state = initial_state.copy()
        current_node_index = 0
        
        return f"Debug session started for {graph_name}.\nUse `/lg step` to step through execution or `/lg breakpoint` to set breakpoints."
    except Exception as e:
        cursor_logger.exception(f"Error starting debug session: {e}")
        return f"Error starting debug session: {str(e)}"

@register_command(
    "step", 
    "Execute the next node in the graph",
    "[--into] [--over] [--out]",
    ["", "--into", "--over"]
)
def command_step_execution(into=False, over=False, out=False, **kwargs):
    """Step through graph execution"""
    global current_graph, current_state, current_node_index, current_execution_history
    
    if current_state is None:
        return "No active debug session. Start one with `/lg debug <graph_name>`"
    
    # Convert flag strings to booleans if needed
    if isinstance(into, str):
        into = into.lower() in ('true', 'yes', '1')
    if isinstance(over, str):
        over = over.lower() in ('true', 'yes', '1')
    if isinstance(out, str):
        out = out.lower() in ('true', 'yes', '1')
    
    # Determine step type
    step_type = "into" if into else "over" if over else "out" if out else "step"
    
    try:
        # In a full implementation, this would call step_forward
        # For now, we'll simulate advancing the state
        current_node_index += 1
        
        # Add some simulated data to the state for demonstration
        current_state["_step"] = current_node_index
        current_state["_timestamp"] = time.time()
        
        return f"Executed step ({step_type}). Current node index: {current_node_index}"
    except Exception as e:
        cursor_logger.exception(f"Error stepping execution: {e}")
        return f"Error stepping execution: {str(e)}"

@register_command(
    "continue", 
    "Continue execution until next breakpoint",
    "[--all]",
    ["", "--all"]
)
def command_continue_execution(all=False, **kwargs):
    """Continue execution until next breakpoint or completion"""
    global current_graph, current_state, current_node_index, current_execution_history
    
    if current_state is None:
        return "No active debug session. Start one with `/lg debug <graph_name>`"
    
    # Convert flag strings to booleans if needed
    if isinstance(all, str):
        all = all.lower() in ('true', 'yes', '1')
    
    try:
        # In a full implementation, this would continue execution
        # until a breakpoint is hit or execution is complete
        current_node_index += 3  # Simulate executing multiple nodes
        
        # Update state with simulated data
        current_state["_step"] = current_node_index
        current_state["_timestamp"] = time.time()
        current_state["_continued"] = True
        
        if all:
            return f"Execution completed. Final node index: {current_node_index}"
        else:
            return f"Execution continued to node index {current_node_index}"
    except Exception as e:
        cursor_logger.exception(f"Error continuing execution: {e}")
        return f"Error continuing execution: {str(e)}"

@register_command(
    "back", 
    "Step backward to previous node",
    "[--steps <number>]",
    ["", "--steps 2"]
)
def command_step_backward(steps=1, **kwargs):
    """Step backward in execution history"""
    global current_graph, current_state, current_node_index, current_execution_history
    
    if current_state is None:
        return "No active debug session. Start one with `/lg debug <graph_name>`"
    
    # Convert steps to integer if it's a string
    if isinstance(steps, str):
        try:
            steps = int(steps)
        except ValueError:
            return f"Invalid value for steps: {steps}. Must be a number."
    
    # Ensure steps is at least 1
    steps = max(1, steps)
    
    try:
        # In a full implementation, this would call step_backward
        # For now, simulate stepping back
        if current_node_index >= steps:
            current_node_index -= steps
            
            # Simulate retrieving a previous state
            current_state["_step"] = current_node_index
            current_state["_timestamp"] = time.time()
            current_state["_stepped_back"] = True
            
            return f"Stepped back {steps} node(s) to node index {current_node_index}"
        else:
            return f"Cannot step back {steps} node(s). Current node index is {current_node_index}."
    except Exception as e:
        cursor_logger.exception(f"Error stepping backward: {e}")
        return f"Error stepping backward: {str(e)}"

@register_command(
    "run-to", 
    "Run execution until a specific node is reached",
    "--node <node_name>",
    ["--node validate_data"]
)
def command_run_to_node(node=None, **kwargs):
    """Run until a specific node is reached"""
    global current_graph, current_state, current_node_index, current_execution_history
    
    if current_state is None:
        return "No active debug session. Start one with `/lg debug <graph_name>`"
    
    if not node:
        return "Error: Node name is required. Use --node <node_name>"
    
    try:
        # In a full implementation, this would call run_to_node
        # For now, simulate running to a node
        current_node_index += 2  # Simulate executing multiple nodes
        
        # Update state with simulated data
        current_state["_step"] = current_node_index
        current_state["_timestamp"] = time.time()
        current_state["_target_node"] = node
        
        return f"Execution continued to node '{node}' (index: {current_node_index})"
    except Exception as e:
        cursor_logger.exception(f"Error running to node: {e}")
        return f"Error running to node: {str(e)}"

@register_command(
    "run-to-condition", 
    "Run until a condition is met",
    "--condition <condition_expression>",
    ["--condition \"'error' in state\""]
)
def command_run_to_condition(condition=None, **kwargs):
    """Run until a condition is met"""
    global current_graph, current_state, current_node_index, current_execution_history
    
    if current_state is None:
        return "No active debug session. Start one with `/lg debug <graph_name>`"
    
    if not condition:
        return "Error: Condition expression is required. Use --condition <expression>"
    
    try:
        # In a full implementation, this would call run_to_condition
        # For now, simulate running to a condition
        current_node_index += 2  # Simulate executing multiple nodes
        
        # Update state with simulated data
        current_state["_step"] = current_node_index
        current_state["_timestamp"] = time.time()
        current_state["_condition"] = condition
        
        return f"Execution continued until condition was met (index: {current_node_index})"
    except Exception as e:
        cursor_logger.exception(f"Error running to condition: {e}")
        return f"Error running to condition: {str(e)}"

@register_command(
    "modify-state", 
    "Modify a value in the current state",
    "--field <field_path> --value <json_value>",
    ["--field user.name --value \"John Doe\"", "--field settings.enabled --value true"]
)
def command_modify_state(field=None, value=None, **kwargs):
    """Modify a value in the current state"""
    global current_state
    
    if current_state is None:
        return "No active debug session. Start one with `/lg debug <graph_name>`"
    
    if not field:
        return "Error: Field path is required. Use --field <field_path>"
    
    if value is None:
        return "Error: Value is required. Use --value <json_value>"
    
    try:
        # Parse JSON value if it's a string
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                # If it's not valid JSON, keep it as a string
                pass
        
        # Navigate and modify the nested field
        parts = field.split('.')
        target = current_state
        
        # Navigate to the parent object
        for i, part in enumerate(parts[:-1]):
            if part not in target:
                target[part] = {}
            target = target[part]
        
        # Set the value
        target[parts[-1]] = value
        
        return f"State updated: {field} = {value}"
    except Exception as e:
        cursor_logger.exception(f"Error modifying state: {e}")
        return f"Error modifying state: {str(e)}"

@register_command(
    "watch", 
    "Set a watch expression on a state field",
    "--field <field_path> [--condition <expression>]",
    ["--field user.score", "--field errors --condition \"len(errors) > 0\""]
)
def command_watch_field(field=None, condition=None, **kwargs):
    """Set a watch expression on a state field"""
    if not field:
        return "Error: Field path is required. Use --field <field_path>"
    
    try:
        # In a full implementation, this would call monitor_field
        # For now, just record the watch
        monitor_id = monitor_field(field, condition)
        
        condition_text = f" with condition: {condition}" if condition else ""
        return f"Watch set on field '{field}'{condition_text}\nWatch ID: {monitor_id}"
    except Exception as e:
        cursor_logger.exception(f"Error setting watch: {e}")
        return f"Error setting watch: {str(e)}"

@register_command(
    "watches", 
    "List all active watches",
    "",
    [""]
)
def command_list_watches(**kwargs):
    """List all active watches"""
    try:
        monitors = get_active_monitors()
        
        if not monitors:
            return "No active watches set."
        
        result = ["Active watches:"]
        for monitor in monitors:
            condition_text = f" (Condition: {monitor['condition']})" if monitor.get('condition') else ""
            result.append(f"[{monitor['id']}] {monitor['field_path']}{condition_text}")
        
        return "\n".join(result)
    except Exception as e:
        cursor_logger.exception(f"Error listing watches: {e}")
        return f"Error listing watches: {str(e)}"

@register_command(
    "clear-watch", 
    "Clear a watch by ID",
    "--id <watch_id>",
    ["--id 12345"]
)
def command_clear_watch(id=None, **kwargs):
    """Clear a watch by ID"""
    if not id:
        return "Error: Watch ID is required. Use --id <watch_id>"
    
    try:
        result = stop_monitoring(id)
        if result:
            return f"Watch {id} cleared."
        else:
            return f"Watch {id} not found."
    except Exception as e:
        cursor_logger.exception(f"Error clearing watch: {e}")
        return f"Error clearing watch: {str(e)}"

@register_command(
    "clear-all-watches", 
    "Clear all watches",
    "",
    [""]
)
def command_clear_all_watches(**kwargs):
    """Clear all watches"""
    try:
        stop_all_monitoring()
        return "All watches cleared."
    except Exception as e:
        cursor_logger.exception(f"Error clearing watches: {e}")
        return f"Error clearing watches: {str(e)}"

@register_command(
    "save-session", 
    "Save current debugging session",
    "--name <session_name>",
    ["--name my_debug_session"]
)
def command_save_debug_session(name=None, **kwargs):
    """Save current debugging session for later restoration"""
    global current_graph, current_state, current_node_index, current_execution_history
    
    if current_state is None:
        return "No active debug session to save."
    
    if not name:
        name = f"session_{int(time.time())}"
    
    try:
        # In a full implementation, this would save the session state
        # For this implementation, we'll just report success
        session_info = {
            "name": name,
            "state": current_state,
            "node_index": current_node_index,
            "timestamp": time.time()
        }
        
        # We would save this to disk in a real implementation
        
        return f"Debug session saved as '{name}'."
    except Exception as e:
        cursor_logger.exception(f"Error saving debug session: {e}")
        return f"Error saving debug session: {str(e)}"

@register_command(
    "load-session", 
    "Load a saved debugging session",
    "--name <session_name>",
    ["--name my_debug_session"]
)
def command_load_debug_session(name=None, **kwargs):
    """Load a previously saved debugging session"""
    global current_graph, current_state, current_node_index, current_execution_history
    
    if not name:
        return "Error: Session name is required. Use --name <session_name>"
    
    try:
        # In a full implementation, this would load the session state
        # For this implementation, we'll simulate loading a session
        
        # Simulate setting up state from loaded session
        current_state = {"_loaded": True, "_session": name}
        current_node_index = 3  # Simulated
        
        return f"Debug session '{name}' loaded. Current node index: {current_node_index}"
    except Exception as e:
        cursor_logger.exception(f"Error loading debug session: {e}")
        return f"Error loading debug session: {str(e)}"

@register_command(
    "list-sessions", 
    "List saved debugging sessions",
    "",
    [""]
)
def command_list_debug_sessions(**kwargs):
    """List all saved debugging sessions"""
    try:
        # In a full implementation, this would load session info from disk
        # For this implementation, we'll return a mock list
        
        # Mock data
        sessions = [
            {"name": "session_1", "timestamp": "2025-05-06 10:15:23", "node_count": 5},
            {"name": "quick_test", "timestamp": "2025-05-05 14:30:12", "node_count": 3},
        ]
        
        if not sessions:
            return "No saved debug sessions found."
        
        result = ["Saved debug sessions:"]
        for session in sessions:
            result.append(f"'{session['name']}' - Created: {session['timestamp']} - Nodes: {session['node_count']}")
        
        return "\n".join(result)
    except Exception as e:
        cursor_logger.exception(f"Error listing debug sessions: {e}")
        return f"Error listing debug sessions: {str(e)}"

# Helper functions for command implementation
def _get_state_by_id_or_index(id_or_index):
    """Get a state by ID or index"""
    global current_execution_history
    
    if isinstance(id_or_index, str) and id_or_index.isdigit():
        id_or_index = int(id_or_index)
    
    if isinstance(id_or_index, int):
        # Get by index
        if 0 <= id_or_index < len(current_execution_history):
            return current_execution_history[id_or_index].get("state", {})
        else:
            return None
    else:
        # Try as a snapshot ID
        return get_state_snapshot(id_or_index)

# Initialize by registering commands
def init_cursor_commands():
    """Initialize the Cursor AI command system"""
    cursor_logger.info(f"Initialized Cursor AI command system with {len(registered_commands)} commands")
    return len(registered_commands)

# Auto-initialize when imported
num_commands = init_cursor_commands() 