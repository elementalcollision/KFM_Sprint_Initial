"""
Rich visualization helpers for Cursor AI command palette.

This module provides enhanced visualization capabilities for Cursor AI
to display state information, graph structures, state differences,
and execution replays in a visually rich format.
"""

import json
import re
import time
import os
import sys
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgba

from src.logger import setup_logger
from src.visualization import (
    visualize_graph,
    visualize_graph_with_execution,
    visualize_graph_with_timing,
    create_interactive_visualization,
    save_visualization
)
from src.debugging import diff_states, visualize_diff
from src.tracing import get_state_history_tracker

# Setup logger for rich visualizations
rich_viz_logger = setup_logger('src.rich_visualizations')

# Constants for rich formatting
COLORS = {
    'header': '\033[95m',     # Purple
    'blue': '\033[94m',       # Blue
    'green': '\033[92m',      # Green
    'yellow': '\033[93m',     # Yellow
    'red': '\033[91m',        # Red
    'bold': '\033[1m',        # Bold
    'underline': '\033[4m',   # Underline
    'end': '\033[0m'          # Reset
}

# Check if terminal supports colors
SUPPORTS_COLORS = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()

def colorize(text: str, color: str) -> str:
    """Apply color to text if terminal supports colors"""
    if not SUPPORTS_COLORS:
        return text
    return f"{COLORS.get(color, '')}{text}{COLORS['end']}"

def format_rich_state(state: Dict[str, Any], format_type: str = 'pretty', max_depth: int = 3) -> str:
    """
    Format state with rich visualization options.
    
    Args:
        state: The state to format
        format_type: The type of formatting to use ('pretty', 'json', 'table', 'compact')
        max_depth: Maximum depth to display for nested objects
        
    Returns:
        Formatted state as a string
    """
    if not state:
        return "Empty state"
    
    if format_type == 'json':
        return json.dumps(state, indent=2, sort_keys=True)
    
    elif format_type == 'table':
        # Create a table with key-value pairs
        table = []
        max_key_len = max(len(str(k)) for k in state.keys())
        table.append(f"{'Key':{max_key_len}} | Value")
        table.append(f"{'-' * max_key_len}-+{'-' * 50}")
        
        for key, value in state.items():
            if isinstance(value, dict):
                table.append(f"{str(key):{max_key_len}} | {{{len(value)} keys}}")
            elif isinstance(value, list):
                table.append(f"{str(key):{max_key_len}} | [{len(value)} items]")
            else:
                # Truncate long values
                value_str = str(value)
                if len(value_str) > 47:
                    value_str = value_str[:44] + "..."
                table.append(f"{str(key):{max_key_len}} | {value_str}")
                
        return "\n".join(table)
    
    elif format_type == 'compact':
        # Create a single-line compact representation
        parts = []
        
        for key, value in state.items():
            if isinstance(value, dict):
                parts.append(f"{key}:{{{len(value)} keys}}")
            elif isinstance(value, list):
                parts.append(f"{key}:[{len(value)} items]")
            else:
                # Truncate long primitive values
                value_str = str(value)
                if len(value_str) > 20:
                    value_str = value_str[:17] + "..."
                parts.append(f"{key}:{value_str}")
                
        return " | ".join(parts)
    
    else:  # Default is 'pretty'
        return _format_pretty(state, max_depth=max_depth)

def _format_pretty(obj: Any, indent: int = 0, max_depth: int = 3, current_depth: int = 0) -> str:
    """
    Format an object with pretty indentation and colors.
    
    Args:
        obj: The object to format
        indent: Current indentation level
        max_depth: Maximum depth to display
        current_depth: Current depth in the object tree
        
    Returns:
        Pretty formatted object as a string
    """
    indent_str = "  " * indent
    result = []
    
    # Handle depth limit
    if current_depth > max_depth:
        if isinstance(obj, dict):
            return f"{colorize('{...}', 'blue')} {colorize(f'(dict with {len(obj)} keys)', 'yellow')}"
        elif isinstance(obj, list):
            return f"{colorize('[...]', 'blue')} {colorize(f'(list with {len(obj)} items)', 'yellow')}"
        else:
            return str(obj)
    
    # Handle different types
    if isinstance(obj, dict):
        if not obj:
            result.append(f"{indent_str}{colorize('{}', 'blue')}")
        else:
            result.append(f"{indent_str}{colorize('{', 'blue')}")
            for key, value in obj.items():
                key_str = colorize(f'"{key}"', 'yellow')
                value_str = _format_pretty(value, indent + 1, max_depth, current_depth + 1)
                result.append(f"{indent_str}  {key_str}: {value_str},")
            result.append(f"{indent_str}{colorize('}', 'blue')}")
    
    elif isinstance(obj, list):
        if not obj:
            result.append(f"{indent_str}{colorize('[]', 'blue')}")
        else:
            result.append(f"{indent_str}{colorize('[', 'blue')}")
            
            # For large lists, show only the first few and last few items
            if len(obj) > 10:
                for i in range(3):
                    if i < len(obj):
                        item_str = _format_pretty(obj[i], indent + 1, max_depth, current_depth + 1)
                        result.append(f"{indent_str}  {item_str},")
                
                result.append(f"{indent_str}  {colorize('...', 'yellow')} {colorize(f'({len(obj) - 6} more items)', 'yellow')}")
                
                for i in range(len(obj) - 3, len(obj)):
                    if i >= 0:
                        item_str = _format_pretty(obj[i], indent + 1, max_depth, current_depth + 1)
                        result.append(f"{indent_str}  {item_str},")
            else:
                for item in obj:
                    item_str = _format_pretty(item, indent + 1, max_depth, current_depth + 1)
                    result.append(f"{indent_str}  {item_str},")
                    
            result.append(f"{indent_str}{colorize(']', 'blue')}")
    
    elif isinstance(obj, str):
        formatted_str = '"' + str(obj) + '"'
        result.append(f"{indent_str}{colorize(formatted_str, 'green')}")
    
    elif isinstance(obj, (int, float)):
        result.append(f"{indent_str}{colorize(str(obj), 'blue')}")
    
    elif isinstance(obj, bool):
        color = 'green' if obj else 'red'
        result.append(f"{indent_str}{colorize(str(obj), color)}")
    
    elif obj is None:
        result.append(f"{indent_str}{colorize('null', 'red')}")
    
    else:
        result.append(f"{indent_str}{str(obj)}")
    
    return "\n".join(result) if len(result) > 1 else result[0]

def format_field_path(state: Dict[str, Any], field_path: str, format_type: str = 'pretty') -> str:
    """
    Format a specific field from the state using dot notation path.
    
    Args:
        state: The state dictionary
        field_path: Path to the field using dot notation (e.g., 'user.preferences.theme')
        format_type: The type of formatting to use
        
    Returns:
        Formatted field value as a string
    """
    if not state:
        return "Empty state"
    
    if not field_path:
        return format_rich_state(state, format_type)
    
    # Split the path and navigate through the state
    parts = field_path.split('.')
    current = state
    path_so_far = []
    
    for part in parts:
        path_so_far.append(part)
        
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return f"Field '{field_path}' not found. Path '{'.'.join(path_so_far)}' does not exist."
    
    # Format the field value
    result = []
    result.append(f"Field: {colorize(field_path, 'yellow')}")
    result.append(f"Value: {format_rich_state(current, format_type) if isinstance(current, (dict, list)) else str(current)}")
    
    return "\n".join(result)

# State Inspection Helpers

def format_rich_state(state: Dict[str, Any], format_type: str = 'pretty', 
                     max_depth: int = 3, max_width: int = 80) -> str:
    """
    Format a state dictionary in a rich, readable format.
    
    Args:
        state: The state dictionary to format
        format_type: Format type ('pretty', 'json', 'table', 'compact')
        max_depth: Maximum depth for nested objects
        max_width: Maximum width for formatted output
        
    Returns:
        Formatted state as string
    """
    if format_type == 'json':
        return json.dumps(state, indent=2)
    
    elif format_type == 'table':
        return _format_state_as_table(state, max_width)
    
    elif format_type == 'compact':
        return _format_state_compact(state)
    
    else:  # Default to 'pretty'
        return _format_state_pretty(state, max_depth=max_depth)

def _format_state_pretty(state: Dict[str, Any], prefix: str = '', max_depth: int = 3, 
                        current_depth: int = 0) -> str:
    """Format state in a pretty hierarchical structure with syntax highlighting"""
    if current_depth > max_depth:
        return colorize(f"{prefix}...", 'blue')
    
    if not state:
        return colorize(f"{prefix}{{}}", 'blue')
    
    lines = []
    
    for key, value in state.items():
        key_str = colorize(f"{key}", 'yellow')
        
        if isinstance(value, dict):
            if not value:  # Empty dict
                lines.append(f"{prefix}{key_str}: {{}}")
            else:
                lines.append(f"{prefix}{key_str}:")
                nested = _format_state_pretty(value, prefix + '  ', max_depth, current_depth + 1)
                lines.append(nested)
        elif isinstance(value, list):
            if not value:  # Empty list
                lines.append(f"{prefix}{key_str}: []")
            elif len(value) <= 3:  # Short list
                value_str = _format_list_inline(value)
                lines.append(f"{prefix}{key_str}: {value_str}")
            else:  # Longer list
                lines.append(f"{prefix}{key_str}: [")
                for item in value[:3]:  # Show first 3 items
                    item_str = _format_value(item)
                    lines.append(f"{prefix}  {item_str},")
                if len(value) > 3:
                    lines.append(f"{prefix}  ... {len(value) - 3} more items")
                lines.append(f"{prefix}]")
        else:
            value_str = _format_value(value)
            lines.append(f"{prefix}{key_str}: {value_str}")
    
    return '\n'.join(lines)

def _format_state_as_table(state: Dict[str, Any], max_width: int = 80) -> str:
    """Format state as a table with key-value pairs"""
    if not state:
        return "Empty state {}"
    
    # Find the longest key for padding
    max_key_length = max(len(str(key)) for key in state.keys())
    
    # Calculate value column width
    value_width = max_width - max_key_length - 5  # 5 chars for padding and separator
    
    # Build the table
    header = f"{'Key':{max_key_length}} | Value"
    separator = f"{'-' * max_key_length}+{'-' * (max_width - max_key_length - 1)}"
    
    lines = [
        colorize(header, 'bold'),
        separator
    ]
    
    for key, value in state.items():
        key_str = colorize(f"{str(key):{max_key_length}}", 'yellow')
        
        if isinstance(value, dict):
            value_str = colorize(f"<dict with {len(value)} keys>", 'blue')
        elif isinstance(value, list):
            value_str = colorize(f"<list with {len(value)} items>", 'blue')
        else:
            value_str = _format_value_truncated(value, value_width)
        
        lines.append(f"{key_str} | {value_str}")
    
    return '\n'.join(lines)

def _format_state_compact(state: Dict[str, Any]) -> str:
    """Format state in a compact single-line representation"""
    parts = []
    
    for key, value in state.items():
        key_str = colorize(key, 'yellow')
        
        if isinstance(value, dict):
            value_str = colorize(f"{{{len(value)} keys}}", 'blue')
        elif isinstance(value, list):
            value_str = colorize(f"[{len(value)} items]", 'blue')
        else:
            value_str = _format_value_truncated(value, 20)
        
        parts.append(f"{key_str}:{value_str}")
    
    return "{" + ", ".join(parts) + "}"

def _format_value(value: Any) -> str:
    """Format a single value with appropriate color"""
    if value is None:
        return colorize("None", 'blue')
    elif isinstance(value, bool):
        return colorize(str(value), 'blue')
    elif isinstance(value, (int, float)):
        return colorize(str(value), 'green')
    elif isinstance(value, str):
        if len(value) > 50:
            return colorize(f'"{value[:47]}..."', 'red')
        return colorize(f'"{value}"', 'red')
    else:
        return str(value)

def _format_list_inline(items: List[Any]) -> str:
    """Format a list inline with appropriate colors"""
    formatted_items = [_format_value(item) for item in items]
    return f"[{', '.join(formatted_items)}]"

def _format_value_truncated(value: Any, max_width: int) -> str:
    """Format a value and truncate if necessary"""
    formatted = _format_value(value)
    if len(formatted) > max_width:
        return formatted[:max_width-3] + "..."
    return formatted

def format_field_path(state: Dict[str, Any], field_path: str) -> str:
    """
    Format a specific field from a state dictionary.
    
    Args:
        state: The state dictionary
        field_path: The path to the field (dot notation)
        
    Returns:
        Formatted field value
    """
    # Navigate nested fields using dot notation
    value = state
    path_parts = field_path.split('.')
    
    try:
        for part in path_parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
                value = value[int(part)]
            else:
                return f"Field '{field_path}' not found in state"
    except Exception as e:
        return f"Error accessing field '{field_path}': {str(e)}"
    
    # Format the result
    if isinstance(value, dict):
        return format_rich_state(value)
    elif isinstance(value, list):
        if len(value) <= 10:
            return _format_list_inline(value)
        else:
            result = [
                f"List with {len(value)} items:",
                "First 5 items:",
                *[f"  {i}: {_format_value(item)}" for i, item in enumerate(value[:5])],
                "...",
                "Last 5 items:",
                *[f"  {i}: {_format_value(item)}" for i, item in enumerate(value[-5:], len(value) - 5)]
            ]
            return '\n'.join(result)
    else:
        return _format_value(value)

# Graph Visualization Helpers

def create_rich_graph_visualization(
    graph: Union[nx.DiGraph, Any],
    visualization_type: str = 'basic',
    execution_path: Optional[List[str]] = None,
    node_timings: Optional[Dict[str, float]] = None,
    focus_node: Optional[str] = None,
    interactive: bool = False,
    output_path: Optional[str] = None,
    title: Optional[str] = None
) -> str:
    """
    Create enhanced graph visualization with various display options.
    
    Args:
        graph: The graph to visualize
        visualization_type: Type of visualization ('basic', 'execution', 'timing', 'focus')
        execution_path: List of nodes in execution order for path highlighting
        node_timings: Dictionary mapping node names to execution times
        focus_node: Node to focus on (for focus visualization)
        interactive: Whether to create interactive HTML visualization
        output_path: Path to save the visualization
        title: Title for the visualization
        
    Returns:
        Path to the saved visualization or ASCII graph for fallbacks
    """
    try:
        # Create the appropriate visualization based on type
        if visualization_type == 'execution' and execution_path:
            # Execution path visualization
            if not title:
                title = "Rich Graph Visualization (Execution)"
                
            fig = visualize_graph_with_execution(
                graph=graph,
                execution_path=execution_path,
                title=title,
                highlight_current=True,
                current_node_index=len(execution_path) - 1 if execution_path else 0
            )
        
        elif visualization_type == 'timing' and node_timings:
            # Timing visualization
            if not title:
                title = "Rich Graph Visualization (Timing)"
                
            fig = visualize_graph_with_timing(
                graph=graph,
                node_timings=node_timings,
                title=title
            )
        
        elif visualization_type == 'focus' and focus_node:
            # Focus visualization
            if not title:
                title = f"Rich Graph Visualization (Focus on {focus_node})"
                
            # Extract subgraph centered on focus node
            if isinstance(graph, nx.DiGraph):
                # Get predecessors and successors
                predecessors = list(graph.predecessors(focus_node)) if focus_node in graph.nodes else []
                successors = list(graph.successors(focus_node)) if focus_node in graph.nodes else []
                
                # Create focus node color mapping
                node_colors = {}
                for node in graph.nodes:
                    if node == focus_node:
                        node_colors[node] = 'red'  # Focus node
                    elif node in predecessors:
                        node_colors[node] = 'blue'  # Predecessors
                    elif node in successors:
                        node_colors[node] = 'green'  # Successors
                    else:
                        node_colors[node] = 'lightgray'  # Other nodes
                
                fig = visualize_graph(
                    graph=graph,
                    title=title,
                    node_colors=node_colors
                )
            else:
                # Fallback for non-networkx graphs
                if not title:
                    title = "Rich Graph Visualization (Basic)"
                fig = visualize_graph(graph, title=title)
        
        else:
            # Basic visualization
            if not title:
                title = "Rich Graph Visualization (Basic)"
                
            fig = visualize_graph(graph, title=title)
        
        # Create interactive visualization if requested
        if interactive:
            html_path = output_path if output_path else f"graph_interactive_{int(time.time())}.html"
            create_interactive_visualization(graph, html_path)
            return f"Interactive visualization created: {html_path}"
        
        # Save the visualization
        if output_path:
            output_file = save_visualization(fig, output_path)
        else:
            output_path = f"graph_{visualization_type}_{int(time.time())}.png"
            output_file = save_visualization(fig, output_path)
            
        # Handle case where save_visualization returns a boolean
        if isinstance(output_file, bool):
            return f"Visualization saved to: {output_path}" if output_file else "Failed to save visualization"
        else:
            return f"Visualization saved to: {output_file}"
    
    except Exception as e:
        # Fallback to ASCII graph visualization
        rich_viz_logger.error(f"Error creating rich graph visualization: {str(e)}")
        
        # Try to extract node names for ASCII representation
        if hasattr(graph, 'nodes'):
            nodes = list(graph.nodes)
        elif hasattr(graph, 'graph') and hasattr(graph.graph, 'nodes'):
            nodes = list(graph.graph.nodes)
        else:
            nodes = ["Unknown graph structure"]
            
        # Create simple ASCII representation
        ascii_graph = f"ASCII Graph Representation:\n"
        ascii_graph += f"Nodes: {', '.join(str(n) for n in nodes[:10])}"
        if len(nodes) > 10:
            ascii_graph += f" ... ({len(nodes) - 10} more)"
            
        return ascii_graph

# State Difference Visualization

def create_rich_diff_visualization(
    state1: Dict[str, Any],
    state2: Dict[str, Any],
    format: str = 'color',
    mode: str = 'detailed',
    labels: Tuple[str, str] = ('Before', 'After')
) -> str:
    """
    Create enhanced visualization of differences between two states.
    
    Args:
        state1: First state to compare
        state2: Second state to compare
        format: Display format ('color', 'table', 'side-by-side')
        mode: Comparison mode ('detailed', 'basic', 'structural')
        labels: Labels for the two states
        
    Returns:
        Formatted string showing the differences
    """
    # Get differences using existing diff_states function
    diff_result = diff_states(state1, state2)
    
    # Convert the diff_result to a standardized format
    standardized_diffs = []
    
    # Handle the case where diff_states returns a dict with 'changes' key (new format)
    if isinstance(diff_result, dict) and 'changes' in diff_result:
        changes = diff_result['changes']
        for path, change_info in changes.items():
            standardized_diffs.append({
                'path': path,
                'type': change_info.get('type', 'unknown'),
                'old_value': change_info.get('before'),
                'new_value': change_info.get('after'),
                'note': change_info.get('note', '')
            })
            
    # Handle the case where diff_states returns a dict mapping paths to change info (old format)
    elif isinstance(diff_result, dict) and all(isinstance(k, str) for k in diff_result.keys()):
        for path, change_info in diff_result.items():
            if isinstance(change_info, dict) and 'type' in change_info:
                standardized_diffs.append({
                    'path': path,
                    'type': change_info['type'],
                    'old_value': change_info.get('old_value'),
                    'new_value': change_info.get('new_value'),
                    'note': change_info.get('note', '')
                })
    
    if not standardized_diffs:
        return "No differences found between states."
    
    # Filter differences based on mode
    if mode == 'basic':
        # Only include top-level differences
        filtered_diffs = [d for d in standardized_diffs if '.' not in d['path']]
    elif mode == 'structural':
        # Only include structural differences (additions/deletions)
        filtered_diffs = [d for d in standardized_diffs if d['type'] in ('added', 'removed')]
    else:  # detailed is default
        filtered_diffs = standardized_diffs
    
    # Format based on selected format
    if format == 'table':
        return _format_diff_as_table(filtered_diffs, labels)
    elif format == 'side-by-side':
        return _format_diff_side_by_side(state1, state2, filtered_diffs, labels)
    else:  # color is default
        return _format_diff_with_color(filtered_diffs)

def _format_diff_with_color(differences: List[Dict[str, Any]]) -> str:
    """
    Format differences with color coding.
    
    Args:
        differences: List of difference dictionaries
        
    Returns:
        Color-coded string representation of differences
    """
    result = []
    result.append(colorize("Changes between states:", 'header'))
    
    for diff in differences:
        # Handle both string paths and direct path access
        path = diff['path'] if isinstance(diff['path'], str) else str(diff['path'])
        
        type_color = {
            'added': 'green',
            'removed': 'red',
            'changed': 'yellow'
        }.get(diff['type'], 'blue')
        
        result.append(f"{colorize(diff['type'].upper(), type_color)} at {colorize(path, 'blue')}")
        
        if diff['type'] == 'added':
            value_str = json.dumps(diff['new_value'], indent=2) if isinstance(diff['new_value'], (dict, list)) else str(diff['new_value'])
            result.append(f"  + {colorize(value_str, 'green')}")
            
        elif diff['type'] == 'removed':
            value_str = json.dumps(diff['old_value'], indent=2) if isinstance(diff['old_value'], (dict, list)) else str(diff['old_value'])
            result.append(f"  - {colorize(value_str, 'red')}")
            
        elif diff['type'] == 'changed':
            old_value_str = json.dumps(diff['old_value'], indent=2) if isinstance(diff['old_value'], (dict, list)) else str(diff['old_value'])
            new_value_str = json.dumps(diff['new_value'], indent=2) if isinstance(diff['new_value'], (dict, list)) else str(diff['new_value'])
            result.append(f"  - {colorize(old_value_str, 'red')}")
            result.append(f"  + {colorize(new_value_str, 'green')}")
    
    return "\n".join(result)

def _format_diff_as_table(differences: List[Dict[str, Any]], labels: Tuple[str, str]) -> str:
    """
    Format differences as a table.
    
    Args:
        differences: List of difference dictionaries
        labels: Labels for the two states
        
    Returns:
        Table representation of differences
    """
    result = []
    
    # Table statistics
    types = {}
    for diff in differences:
        types[diff['type']] = types.get(diff['type'], 0) + 1
    
    result.append(colorize("Diff Summary:", 'header'))
    result.append(f"Total differences: {len(differences)}")
    for diff_type, count in types.items():
        type_color = {'added': 'green', 'removed': 'red', 'changed': 'yellow'}.get(diff_type, 'blue')
        result.append(f"  {colorize(diff_type, type_color)}: {count}")
    
    result.append("")
    
    # Table header
    result.append(f"{'Path':<30} | {'Change':<10} | {labels[0]:<20} | {labels[1]:<20}")
    result.append(f"{'-' * 30}-+-{'-' * 10}-+-{'-' * 20}-+-{'-' * 20}")
    
    # Table rows
    for diff in differences:
        path = diff['path']
        if len(path) > 28:
            path = "..." + path[-25:]
            
        diff_type = diff['type']
        type_color = {'added': 'green', 'removed': 'red', 'changed': 'yellow'}.get(diff_type, 'blue')
        
        old_value = str(diff.get('old_value', ''))
        if len(old_value) > 20:
            old_value = old_value[:17] + "..."
            
        new_value = str(diff.get('new_value', ''))
        if len(new_value) > 20:
            new_value = new_value[:17] + "..."
            
        row = f"{path:<30} | {colorize(diff_type, type_color):<10} | {old_value:<20} | {new_value:<20}"
        result.append(row)
    
    return "\n".join(result)

def _format_diff_side_by_side(
    state1: Dict[str, Any],
    state2: Dict[str, Any],
    differences: List[Dict[str, Any]],
    labels: Tuple[str, str]
) -> str:
    """
    Format states side by side with differences highlighted.
    
    Args:
        state1: First state
        state2: Second state
        differences: List of difference dictionaries
        labels: Labels for the two states
        
    Returns:
        Side-by-side comparison of states
    """
    result = []
    max_width = 40  # Max width for each side
    
    # Create the header
    separator = f"+{'-' * max_width}+{'-' * max_width}+"
    result.append(separator)
    result.append(f"| {colorize(labels[0], 'bold'):<{max_width-2}} | {colorize(labels[1], 'bold'):<{max_width-2}} |")
    result.append(separator)
    
    # Create set of paths for quick lookup
    diff_paths = {diff['path'] for diff in differences}
    
    # Build a list of all paths in both states
    all_paths = set()
    
    def collect_paths(obj, current_path=""):
        if isinstance(obj, dict):
            for key, value in obj.items():
                path = f"{current_path}.{key}" if current_path else key
                all_paths.add(path)
                if isinstance(value, (dict, list)):
                    collect_paths(value, path)
        elif isinstance(obj, list):
            for i, value in enumerate(obj):
                path = f"{current_path}[{i}]"
                all_paths.add(path)
                if isinstance(value, (dict, list)):
                    collect_paths(value, path)
    
    collect_paths(state1)
    collect_paths(state2)
    
    # Sort paths for consistent order
    sorted_paths = sorted(all_paths)
    
    # Display each path with values from both states
    for path in sorted_paths:
        # Get values from each state
        parts = []
        current_path = ""
        for part in path.split('.'):
            if '[' in part:  # Handle array indices
                key, idx_str = part.split('[', 1)
                idx = int(idx_str.rstrip(']'))
                parts.append((key, idx))
            else:
                parts.append((part, None))
        
        # Extract values
        value1 = state1
        value2 = state2
        valid1 = True
        valid2 = True
        
        for key, idx in parts:
            if not key:
                continue
                
            if idx is not None:
                # Handle array index
                try:
                    if valid1 and key in value1 and isinstance(value1[key], list) and 0 <= idx < len(value1[key]):
                        value1 = value1[key][idx]
                    else:
                        valid1 = False
                except (KeyError, IndexError, TypeError):
                    valid1 = False
                    
                try:
                    if valid2 and key in value2 and isinstance(value2[key], list) and 0 <= idx < len(value2[key]):
                        value2 = value2[key][idx]
                    else:
                        valid2 = False
                except (KeyError, IndexError, TypeError):
                    valid2 = False
            else:
                # Handle regular key
                try:
                    if valid1 and key in value1:
                        value1 = value1[key]
                    else:
                        valid1 = False
                except (KeyError, TypeError):
                    valid1 = False
                    
                try:
                    if valid2 and key in value2:
                        value2 = value2[key]
                    else:
                        valid2 = False
                except (KeyError, TypeError):
                    valid2 = False
        
        # Skip this path if it's too deeply nested or both values are complex
        if (isinstance(value1, (dict, list)) and len(str(value1)) > max_width - 5 and 
            isinstance(value2, (dict, list)) and len(str(value2)) > max_width - 5):
            continue
        
        # Format values
        value1_str = "N/A" if not valid1 else str(value1)
        value2_str = "N/A" if not valid2 else str(value2)
        
        # Truncate if too long
        if len(value1_str) > max_width - 5:
            value1_str = value1_str[:max_width-8] + "..."
        if len(value2_str) > max_width - 5:
            value2_str = value2_str[:max_width-8] + "..."
        
        # Highlight if different
        is_different = path in diff_paths
        
        if is_different:
            # Determine difference type
            diff_type = None
            for diff in differences:
                if diff['path'] == path:
                    diff_type = diff['type']
                    break
            
            if diff_type == 'added':
                value1_str = colorize("N/A", 'red')
                value2_str = colorize(value2_str, 'green')
            elif diff_type == 'removed':
                value1_str = colorize(value1_str, 'red')
                value2_str = colorize("N/A", 'red')
            else:  # changed
                value1_str = colorize(value1_str, 'red')
                value2_str = colorize(value2_str, 'green')
                
            # Add the path and values
            path_display = path
            if len(path_display) > max_width - 5:
                path_display = "..." + path_display[-(max_width-8):]
            
            result.append(f"| {path_display:<{max_width-2}} |")
            result.append(f"| {value1_str:<{max_width-2}} | {value2_str:<{max_width-2}} |")
            result.append(separator)
    
    return "\n".join(result)

# Execution Replay Visualization

def create_execution_replay_visualization(
    execution_history: List[Dict[str, Any]],
    current_index: int = 0,
    graph: Optional[nx.DiGraph] = None,
    display_state: bool = True,
    format: str = 'text'
) -> str:
    """
    Create visualization for replaying an execution step by step.
    
    Args:
        execution_history: List of execution history entries
        current_index: Index of the current step to display
        graph: The graph structure for visualization
        display_state: Whether to include state information
        format: Display format ('text' or 'graphical')
        
    Returns:
        Visualization string or path to saved visualization
    """
    if not execution_history:
        return "No execution history available."
    
    # Validate index
    if current_index < 0 or current_index >= len(execution_history):
        return f"Invalid step index. Valid range: 0-{len(execution_history) - 1}"
    
    # Get current step
    step = execution_history[current_index]
    
    # Get node name from the step, handling different formats
    node_name = None
    if "node_name" in step:
        node_name = step["node_name"]
    elif "node" in step:
        node_name = step["node"]
    else:
        # Try to infer from keys
        for key in step.keys():
            if key.lower().endswith('_node') or key.lower().endswith('node'):
                node_name = step[key]
                break
        
        # If still not found, use a default
        if not node_name:
            node_name = f"Step {current_index + 1}"
    
    # Create execution path for visualization
    execution_path = []
    for i, entry in enumerate(execution_history[:current_index + 1]):
        entry_node = None
        if "node_name" in entry:
            entry_node = entry["node_name"]
        elif "node" in entry:
            entry_node = entry["node"]
        else:
            # Use the same logic as above for consistency
            for key in entry.keys():
                if key.lower().endswith('_node') or key.lower().endswith('node'):
                    entry_node = entry[key]
                    break
            
            if not entry_node:
                entry_node = f"Step {i + 1}"
        
        execution_path.append(entry_node)
    
    # For graphical format, create a visualization
    if format == 'graphical' and graph:
        try:
            # Create a graph visualization highlighting the current node
            fig = visualize_graph_with_execution(
                graph=graph,
                execution_path=execution_path,
                title=f"Execution Step {current_index + 1}/{len(execution_history)}: {node_name}",
                highlight_current=True,
                current_node_index=current_index
            )
            
            # Save the visualization
            output_file = save_visualization(fig, prefix="replay")
            
            # If displaying state, add state information
            if display_state:
                # Extract state from step
                state_data = None
                if 'state' in step:
                    state_data = step['state']
                elif isinstance(step, dict) and all(k != 'node_name' and k != 'node' for k in step.keys()):
                    # If the step itself looks like a state, use it
                    state_data = {k: v for k, v in step.items() if k != 'node_name' and k != 'node'}
                
                if state_data:
                    state_info = format_rich_state(state_data, format_type='pretty', max_depth=2)
                    return f"Graph visualization saved to: {output_file}\n\nCurrent State:\n{state_info}"
                else:
                    return f"Graph visualization saved to: {output_file}"
            else:
                return f"Graph visualization saved to: {output_file}"
        except Exception as e:
            rich_viz_logger.error(f"Error creating graphical replay: {str(e)}")
            # Fall back to text format
            format = 'text'
    
    # Text format (default)
    result = []
    
    # Create header with navigation info
    result.append(colorize(f"Execution Step ({current_index + 1}/{len(execution_history)})", 'header'))
    result.append(f"Node: {colorize(node_name, 'blue')}")
    
    if 'timestamp' in step:
        result.append(f"Time: {step['timestamp']}")
    
    if 'duration' in step:
        duration = step['duration']
        color = 'green' if duration < 0.2 else 'yellow' if duration < 0.5 else 'red'
        result.append(f"Duration: {colorize(f'{duration:.3f}s', color)}")
    
    # Show execution path
    result.append("\nExecution Path:")
    path_str = " → ".join([
        f"{colorize(node, 'bold' if i == current_index else '')}" 
        for i, node in enumerate(execution_path)
    ])
    result.append(path_str)
    
    # Show state if requested
    if display_state:
        result.append("\nState:")
        
        # Extract state from step
        state_data = None
        if 'state' in step:
            state_data = step['state']
        elif isinstance(step, dict) and all(k != 'node_name' and k != 'node' for k in step.keys()):
            # If the step itself looks like a state, use it
            state_data = {k: v for k, v in step.items() if k != 'node_name' and k != 'node'}
        
        if state_data:
            state_info = format_rich_state(state_data, format_type='pretty', max_depth=2)
            result.append(state_info)
        else:
            result.append("No state information available.")
    
    # Navigation help
    result.append("\nNavigation: Use '/lg replay --step=N' to move to step N")
    
    return "\n".join(result)

def show_execution_timeline(
    execution_history: List[Dict[str, Any]],
    width: int = 80,
    include_states: bool = False
) -> str:
    """
    Create a timeline visualization of the execution.
    
    Args:
        execution_history: List of execution history entries
        width: Width of the timeline in characters
        include_states: Whether to include state summaries
        
    Returns:
        Timeline visualization string
    """
    if not execution_history:
        return "No execution history available."
    
    result = []
    
    # Create header
    result.append(colorize("Execution Timeline", 'header'))
    result.append(f"Total steps: {len(execution_history)}")
    
    # Get total duration if available
    total_duration = 0
    has_durations = True
    
    for step in execution_history:
        if 'duration' in step:
            total_duration += step['duration']
        else:
            has_durations = False
            break
    
    if has_durations:
        result.append(f"Total duration: {total_duration:.3f}s")
    
    # Create the timeline
    result.append("\nTimeline:")
    
    # Calculate time scale if timestamps are available
    timeline_bars = []
    
    if all('timestamp' in step for step in execution_history):
        # Convert timestamps to datetime objects
        try:
            timestamps = [datetime.fromisoformat(step['timestamp'].replace('Z', '+00:00')) 
                         for step in execution_history]
            
            # Calculate total time span
            time_start = min(timestamps)
            time_end = max(timestamps)
            time_span = (time_end - time_start).total_seconds()
            
            # Create a bar for each step
            for i, step in enumerate(execution_history):
                position = ((timestamps[i] - time_start).total_seconds() / time_span) if time_span > 0 else 0
                position_chars = int(position * (width - 20))
                
                # Create the bar
                bar = " " * position_chars + colorize("●", 'blue') + " " + step['node_name']
                timeline_bars.append(bar)
            
            # Add time scale
            result.append(f"{time_start.strftime('%H:%M:%S')} {'-' * (width - 20)} {time_end.strftime('%H:%M:%S')}")
            
        except Exception as e:
            rich_viz_logger.error(f"Error creating timeline with timestamps: {str(e)}")
            timeline_bars = []
    
    # If timestamp-based timeline failed, create a simple sequential timeline
    if not timeline_bars:
        step_width = (width - 10) // len(execution_history)
        
        timeline = ""
        for i in range(len(execution_history)):
            if i == 0:
                timeline += colorize("●", 'blue')
            else:
                timeline += "-" * (step_width - 1) + colorize("●", 'blue')
        
        result.append(timeline)
        
        # Add node names below markers
        node_names = ""
        for i, step in enumerate(execution_history):
            name = step['node_name']
            if len(name) > step_width:
                name = name[:step_width-2] + ".."
            
            spacing = max(0, step_width - len(node_names) % width)
            node_names += " " * spacing + name
        
        # Break node names into multiple lines if needed
        for i in range(0, len(node_names), width):
            result.append(node_names[i:i+width])
    else:
        # Add the timestamp-based bars
        result.extend(timeline_bars)
    
    # Include state transitions if requested
    if include_states:
        result.append("\nState Transitions:")
        
        for i, step in enumerate(execution_history):
            node_name = step['node_name']
            result.append(f"{i:2d}: {colorize(node_name, 'blue')}")
            
            if 'state' in step:
                # Show compact state summary
                state_summary = format_rich_state(step['state'], format_type='compact')
                result.append(f"    {state_summary}")
    
    return "\n".join(result) 