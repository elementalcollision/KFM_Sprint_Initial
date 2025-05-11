"""
Graph Visualization for LangGraph applications.

This module provides utilities for visualizing LangGraph applications with
advanced features such as execution path highlighting, timing information,
and interactive exploration.
"""

import os
import json
import time
import tempfile
import logging
import traceback
from typing import Dict, Any, List, Tuple, Optional, Set, Union, Callable
import uuid
import datetime
from functools import wraps

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
from matplotlib.patches import Rectangle
import networkx as nx
import numpy as np

# Try to import pyvis for interactive visualization
try:
    from pyvis.network import Network
    PYVIS_AVAILABLE = True
except ImportError:
    PYVIS_AVAILABLE = False

from langgraph.graph import StateGraph, END
from src.logger import setup_logger

# Setup logger for the visualization module
viz_logger = setup_logger('src.visualization')

# Define log directories
VIZ_LOG_DIR = "logs/visualizations"
TIMELINE_DIR = os.path.join(VIZ_LOG_DIR, "timelines")
STATE_VIZ_DIR = os.path.join(VIZ_LOG_DIR, "states")

# Make sure directories exist
for directory in [VIZ_LOG_DIR, TIMELINE_DIR, STATE_VIZ_DIR]:
    os.makedirs(directory, exist_ok=True)

# Constants for visualization
NODE_COLORS = {
    'normal': '#66BBFF',
    'start': '#99CC99',
    'end': '#CC9999',
    'executed': '#88CC88',
    'current': '#FFCC66',
    'error': '#FF8888',
    'breakpoint': '#FF99CC',
    'skipped': '#CCCCCC'
}

EDGE_COLORS = {
    'normal': '#999999',
    'executed': '#44AA44',
    'current': '#FFAA00',
    'error': '#DD4444'
}

# Layout algorithms
LAYOUT_ALGORITHMS = {
    'spring': nx.spring_layout,
    'kamada_kawai': nx.kamada_kawai_layout,
    'planar': nx.planar_layout,
    'shell': nx.shell_layout,
    'spiral': nx.spiral_layout,
    'spectral': nx.spectral_layout,
    'circular': nx.circular_layout,
    'random': nx.random_layout,
}

def extract_graph_structure(graph: StateGraph) -> nx.DiGraph:
    """
    Extract the graph structure from a LangGraph StateGraph.
    
    Args:
        graph: The LangGraph StateGraph
        
    Returns:
        nx.DiGraph: A NetworkX directed graph representing the structure
    """
    G = nx.DiGraph()
    
    try:
        # Get nodes from the graph
        nodes = list(graph.graph.nodes)
        
        # Add nodes to the graph
        for node in nodes:
            if node == END:
                G.add_node(node, node_type='end')
            else:
                G.add_node(node, node_type='normal')
        
        # Add edges between nodes
        for node in nodes:
            if node == END:
                continue
                
            # Get the next nodes (edges out)
            next_nodes = []
            
            node_info = graph.graph.get_node(node)
            if node_info and 'branches' in node_info:
                for branch, condition in node_info['branches'].items():
                    if branch != END:
                        next_nodes.append(branch)
                        G.add_edge(node, branch, condition=str(condition))
                    else:
                        G.add_edge(node, END, condition=str(condition))
            
            # If no explicit branches, check for default edges
            if not next_nodes and node != END:
                # Look for default edge
                default_next = graph.graph.get_next_node(node)
                if default_next:
                    G.add_edge(node, default_next)
        
        viz_logger.debug(f"Extracted graph with {len(G.nodes)} nodes and {len(G.edges)} edges")
        return G
        
    except Exception as e:
        viz_logger.error(f"Error extracting graph structure: {e}")
        viz_logger.debug(traceback.format_exc())
        # Return an empty graph on error
        return nx.DiGraph()

def get_node_execution_status(node_name: str, execution_path: List[str], 
                           current_node: Optional[str] = None,
                           error_nodes: Optional[List[str]] = None) -> str:
    """
    Determine the execution status of a node.
    
    Args:
        node_name: Name of the node to check
        execution_path: List of executed node names in order
        current_node: Name of the currently executing node (if any)
        error_nodes: List of nodes that encountered errors (if any)
        
    Returns:
        str: Status of the node ('normal', 'executed', 'current', 'error', etc.)
    """
    # Check if this is the end node
    if node_name == END:
        if execution_path and execution_path[-1] == END:
            return 'executed'
        return 'normal'
    
    # Check for error node
    if error_nodes and node_name in error_nodes:
        return 'error'
    
    # Check if this is the currently executing node
    if current_node and node_name == current_node:
        return 'current'
    
    # Check if this node has been executed
    if node_name in execution_path:
        return 'executed'
    
    # Default status
    return 'normal'

def apply_hierarchical_layout(G: nx.DiGraph, vertical: bool = True, 
                           layer_spacing: float = 2.0, node_spacing: float = 1.0) -> Dict[str, Tuple[float, float]]:
    """
    Apply a hierarchical layout to the graph.
    
    Args:
        G: NetworkX directed graph
        vertical: Whether to use vertical (True) or horizontal (False) layout
        layer_spacing: Spacing between layers
        node_spacing: Spacing between nodes in the same layer
        
    Returns:
        Dict mapping node names to (x, y) positions
    """
    # Handle empty graph case
    if len(G.nodes) == 0:
        viz_logger.warning("Empty graph provided to apply_hierarchical_layout")
        return {}
    
    # Create a topological sort of the graph
    try:
        layers = list(nx.topological_generations(G))
        
        # Handle empty layers case
        if not layers:
            viz_logger.warning("No layers found in graph, falling back to default layout")
            return nx.spring_layout(G)
            
        pos = {}
        max_nodes_per_layer = max(len(layer) for layer in layers) if layers else 0
        
        for i, layer in enumerate(layers):
            nodes_in_layer = len(layer)
            for j, node in enumerate(sorted(layer)):
                if vertical:
                    # Vertical layout (top to bottom)
                    y = -i * layer_spacing
                    x = (j - (nodes_in_layer - 1)/2) * node_spacing
                else:
                    # Horizontal layout (left to right)
                    x = i * layer_spacing
                    y = (j - (nodes_in_layer - 1)/2) * node_spacing
                
                pos[node] = (x, y)
        
        return pos
        
    except nx.NetworkXUnfeasible:
        # Graph has cycles, fallback to shell layout
        viz_logger.warning("Graph has cycles, falling back to shell layout")
        return nx.shell_layout(G)

def apply_circular_layout(G: nx.DiGraph, node_groups: Optional[Dict[str, List[str]]] = None) -> Dict[str, Tuple[float, float]]:
    """
    Apply a circular layout to the graph, optionally organizing nodes into groups.
    
    Args:
        G: NetworkX directed graph
        node_groups: Optional dict mapping group names to lists of node names
        
    Returns:
        Dict mapping node names to (x, y) positions
    """
    if node_groups:
        # Create a dict for scale and center parameters
        nlist = [list(group) for group in node_groups.values()]
        return nx.shell_layout(G, nlist=nlist)
    else:
        return nx.circular_layout(G)

def apply_force_directed_layout(G: nx.DiGraph, iterations: int = 100, 
                             scale: float = 1.0) -> Dict[str, Tuple[float, float]]:
    """
    Apply a force-directed layout to the graph.
    
    Args:
        G: NetworkX directed graph
        iterations: Number of iterations to run the layout algorithm
        scale: Scale factor for the layout
        
    Returns:
        Dict mapping node names to (x, y) positions
    """
    try:
        # For large graphs, Kamada-Kawai can be more stable
        if len(G.nodes) > 50:
            return nx.kamada_kawai_layout(G, scale=scale)
        # Spring layout is good for smaller graphs
        return nx.spring_layout(G, k=scale, iterations=iterations)
    except Exception as e:
        viz_logger.warning(f"Force-directed layout failed: {e}, falling back to spectral layout")
        return nx.spectral_layout(G, scale=scale)

def visualize_graph(graph: Union[StateGraph, nx.DiGraph], 
                  layout: Union[str, Dict[str, Tuple[float, float]]] = 'hierarchical',
                  title: Optional[str] = None,
                  node_size: int = 800,
                  node_colors: Optional[Dict[str, str]] = None,
                  edge_colors: Optional[Dict[str, str]] = None,
                  show_labels: bool = True,
                  label_font_size: int = 10,
                  figsize: Tuple[int, int] = (12, 8),
                  dpi: int = 100) -> plt.Figure:
    """
    Visualize a LangGraph graph structure.
    
    Args:
        graph: The LangGraph StateGraph or NetworkX DiGraph
        layout: Layout algorithm to use or a dict mapping nodes to positions
        title: Optional title for the visualization
        node_size: Size of nodes in the visualization
        node_colors: Optional dict of node colors by type
        edge_colors: Optional dict of edge colors by type
        show_labels: Whether to show node labels
        label_font_size: Font size for node labels
        figsize: Size of the figure (width, height) in inches
        dpi: Resolution of the figure
        
    Returns:
        matplotlib.pyplot.Figure: The visualization figure
    """
    # Use default colors if not provided
    if node_colors is None:
        node_colors = NODE_COLORS
    if edge_colors is None:
        edge_colors = EDGE_COLORS
    
    # Create figure and axis
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    
    try:
        # Convert to NetworkX graph if needed
        if isinstance(graph, nx.DiGraph):
            G = graph
        else:
            try:
                G = extract_graph_structure(graph)
            except Exception as e:
                viz_logger.warning(f"Failed to extract graph structure: {e}. Creating minimal graph.")
                G = nx.DiGraph()
                
                # Try to get nodes from the graph object using various attributes
                nodes = []
                if hasattr(graph, 'nodes'):
                    nodes = graph.nodes
                elif hasattr(graph, 'graph') and hasattr(graph.graph, 'nodes'):
                    nodes = graph.graph.nodes
                
                # Add basic nodes if needed
                if not nodes:
                    nodes = ["start", "process", "end"]
                
                for node in nodes:
                    G.add_node(node)
                
                # Add basic edges
                if len(nodes) > 1:
                    for i in range(len(nodes) - 1):
                        G.add_edge(nodes[i], nodes[i+1])
        
        # Handle empty graph case
        if len(G.nodes) == 0:
            ax.text(0.5, 0.5, "Empty Graph", ha='center', va='center', fontsize=14)
            ax.set_xlim(-1, 1)
            ax.set_ylim(-1, 1)
            ax.axis('off')
            if title:
                ax.set_title(title)
            return fig
            
        # Get node positions
        try:
            if isinstance(layout, dict):
                # Use provided positions
                pos = layout
            elif layout == 'hierarchical':
                # Use custom hierarchical layout
                pos = apply_hierarchical_layout(G)
            elif layout in LAYOUT_ALGORITHMS:
                # Use NetworkX built-in layout
                pos = LAYOUT_ALGORITHMS[layout](G)
            else:
                # Default to spring layout
                viz_logger.warning(f"Unknown layout '{layout}', using spring layout")
                pos = nx.spring_layout(G)
                
            # Handle layout failure
            if not pos:
                viz_logger.warning(f"Layout algorithm '{layout}' failed, falling back to spring layout")
                pos = nx.spring_layout(G)
        except Exception as layout_error:
            viz_logger.warning(f"Error applying layout: {layout_error}. Falling back to spring layout.")
            pos = nx.spring_layout(G)
        
        # Draw the graph
        # 1. Draw nodes
        for node, node_pos in pos.items():
            # Determine node type
            if node == END:
                node_type = 'end'
            elif G.in_degree(node) == 0:
                node_type = 'start'
            else:
                node_type = 'normal'
            
            # Draw the node
            ax.scatter(
                node_pos[0], node_pos[1],
                s=node_size,
                c=node_colors[node_type],
                edgecolors='black',
                zorder=2
            )
            
            # Draw the label if requested
            if show_labels:
                ax.text(
                    node_pos[0], node_pos[1],
                    str(node),
                    fontsize=label_font_size,
                    ha='center', va='center',
                    bbox=dict(facecolor='white', alpha=0.7, boxstyle='round,pad=0.2'),
                    zorder=3
                )
        
        # 2. Draw edges
        drawn_edges = set()  # Keep track of drawn edges to avoid duplicates
        for u, v in G.edges():
            if (u, v) not in drawn_edges:
                # Get edge properties
                edge_type = 'normal'
                edge_color = edge_colors[edge_type]
                
                # Get node positions
                if u in pos and v in pos:
                    u_pos, v_pos = pos[u], pos[v]
                    
                    # Draw the edge
                    ax.annotate(
                        "",
                        xy=v_pos, xycoords='data',
                        xytext=u_pos, textcoords='data',
                        arrowprops=dict(
                            arrowstyle="->",
                            color=edge_color,
                            lw=1.5,
                            connectionstyle="arc3,rad=0.1",
                            alpha=0.7
                        ),
                        zorder=1
                    )
                    
                    # Mark edge as drawn
                    drawn_edges.add((u, v))
                    
                    # If there's a condition on this edge, show it
                    edge_data = G.get_edge_data(u, v)
                    if edge_data and 'condition' in edge_data:
                        condition = edge_data['condition']
                        # Calculate midpoint of the edge for the label
                        mid_x = (u_pos[0] + v_pos[0]) / 2
                        mid_y = (u_pos[1] + v_pos[1]) / 2
                        # Add a slight offset
                        mid_x += 0.1
                        mid_y += 0.1
                        
                        # Show the condition
                        cond_text = str(condition)
                        # Truncate if too long
                        if len(cond_text) > 30:
                            cond_text = cond_text[:27] + "..."
                            
                        ax.text(
                            mid_x, mid_y,
                            cond_text,
                            fontsize=label_font_size-2,
                            ha='center', va='center',
                            bbox=dict(facecolor='white', alpha=0.7, boxstyle='round,pad=0.1'),
                            zorder=1
                        )
        
        # Set title if provided
        if title:
            ax.set_title(title)
            
        # Turn off axis
        ax.axis('off')
        
        # Adjust layout
        plt.tight_layout()
        
        return fig
        
    except Exception as e:
        viz_logger.exception(f"Error in visualize_graph: {e}")
        
        # Create a basic error figure
        ax.text(0.5, 0.5, f"Error visualizing graph: {str(e)}", ha='center', va='center', fontsize=12, wrap=True)
        ax.set_xlim(-1, 1)
        ax.set_ylim(-1, 1)
        ax.axis('off')
        
        if title:
            ax.set_title(title)
            
        return fig

def save_visualization(fig: plt.Figure, output_path: str, 
                    format: str = 'png', dpi: int = 300) -> bool:
    """
    Save a visualization to a file.
    
    Args:
        fig: Matplotlib figure object
        output_path: Path to save the file
        format: File format ('png', 'svg', 'pdf', etc.)
        dpi: Resolution in dots per inch (for raster formats)
        
    Returns:
        bool: True if the file was saved successfully, False otherwise
    """
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        
        # Save the figure
        fig.savefig(output_path, format=format, dpi=dpi, bbox_inches='tight')
        viz_logger.info(f"Visualization saved to {output_path}")
        return True
    except Exception as e:
        viz_logger.error(f"Error saving visualization: {e}")
        viz_logger.debug(traceback.format_exc())
        return False 

def visualize_graph_with_execution(graph: Union[StateGraph, nx.DiGraph],
                               execution_path: List[str],
                               current_node: Optional[str] = None,
                               error_nodes: Optional[List[str]] = None,
                               layout: Union[str, Dict[str, Tuple[float, float]]] = 'hierarchical',
                               title: Optional[str] = None,
                               node_size: int = 800,
                               show_labels: bool = True,
                               label_font_size: int = 10,
                               figsize: Tuple[int, int] = (12, 8),
                               dpi: int = 100) -> plt.Figure:
    """
    Visualize a graph with execution path highlighted.
    
    Args:
        graph: LangGraph StateGraph or NetworkX DiGraph
        execution_path: List of node names in execution order
        current_node: Optional name of the currently executing node
        error_nodes: Optional list of nodes that encountered errors
        layout: Layout algorithm name or pre-computed positions
        title: Optional title for the visualization
        node_size: Size of nodes in the visualization
        show_labels: Whether to show node labels
        label_font_size: Font size for node labels
        figsize: Figure size as (width, height) in inches
        dpi: Resolution in dots per inch
        
    Returns:
        matplotlib.figure.Figure: Figure object for the visualization
    """
    # Convert to NetworkX graph if needed
    if isinstance(graph, StateGraph):
        G = extract_graph_structure(graph)
    else:
        G = graph
    
    # Create figure
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    
    # Get node positions based on specified layout
    pos = None
    if isinstance(layout, dict):
        # Use provided layout
        pos = layout
    elif layout == 'hierarchical':
        pos = apply_hierarchical_layout(G)
    elif layout == 'circular':
        pos = apply_circular_layout(G)
    elif layout == 'force':
        pos = apply_force_directed_layout(G)
    elif layout in LAYOUT_ALGORITHMS:
        pos = LAYOUT_ALGORITHMS[layout](G)
    else:
        viz_logger.warning(f"Unknown layout '{layout}', falling back to hierarchical")
        pos = apply_hierarchical_layout(G)
    
    # Group nodes by status for batch drawing
    nodes_by_status = {
        'normal': [],
        'executed': [],
        'current': [],
        'error': [],
        'end': []
    }
    
    for node in G.nodes():
        # Determine node status
        if node == END:
            status = 'end'
        else:
            status = get_node_execution_status(
                node, 
                execution_path, 
                current_node, 
                error_nodes
            )
        
        # Add to appropriate group
        if status in nodes_by_status:
            nodes_by_status[status].append(node)
    
    # Draw nodes by status groups
    for status, nodes in nodes_by_status.items():
        if not nodes:
            continue
            
        nx.draw_networkx_nodes(
            G, pos,
            nodelist=nodes,
            node_size=node_size,
            node_color=NODE_COLORS[status],
            edgecolors='black',
            alpha=0.9,
            ax=ax
        )
    
    # Group edges by status for batch drawing
    edges_normal = []
    edges_executed = []
    
    # Create set of executed node pairs for quick lookup
    executed_pairs = set()
    for i in range(len(execution_path) - 1):
        executed_pairs.add((execution_path[i], execution_path[i+1]))
    
    # Group edges
    for u, v in G.edges():
        if (u, v) in executed_pairs:
            edges_executed.append((u, v))
        else:
            edges_normal.append((u, v))
    
    # Draw normal edges
    if edges_normal:
        nx.draw_networkx_edges(
            G, pos,
            edgelist=edges_normal,
            edge_color=EDGE_COLORS['normal'],
            width=1.5,
            arrowsize=15,
            arrowstyle='-|>',
            connectionstyle='arc3,rad=0.1',
            alpha=0.4,
            ax=ax
        )
    
    # Draw executed edges
    if edges_executed:
        nx.draw_networkx_edges(
            G, pos,
            edgelist=edges_executed,
            edge_color=EDGE_COLORS['executed'],
            width=2.5,
            arrowsize=20,
            arrowstyle='-|>',
            connectionstyle='arc3,rad=0.1',
            alpha=1.0,
            ax=ax
        )
    
    # Add labels if requested
    if show_labels:
        labels = {node: node for node in G.nodes()}
        nx.draw_networkx_labels(
            G, pos,
            labels=labels,
            font_size=label_font_size,
            font_weight='bold',
            font_color='black',
            ax=ax
        )
    
    # Add title if provided
    if title:
        plt.title(title, fontsize=14, pad=20)
    else:
        plt.title("Graph Execution Visualization", fontsize=14, pad=20)
    
    # Add legend
    legend_elements = [
        mpatches.Patch(color=NODE_COLORS['normal'], label='Pending'),
        mpatches.Patch(color=NODE_COLORS['executed'], label='Executed'),
    ]
    
    if any(node == current_node for node in G.nodes()):
        legend_elements.append(mpatches.Patch(color=NODE_COLORS['current'], label='Current'))
        
    if error_nodes and any(node in error_nodes for node in G.nodes()):
        legend_elements.append(mpatches.Patch(color=NODE_COLORS['error'], label='Error'))
    
    legend_elements.append(mpatches.Patch(color=NODE_COLORS['end'], label='End'))
    
    ax.legend(handles=legend_elements, loc='upper right', fontsize=10)
    
    # Remove axis
    plt.axis('off')
    
    # Adjust layout
    plt.tight_layout()
    
    return fig

def visualize_graph_with_timing(graph: Union[StateGraph, nx.DiGraph],
                             execution_data: List[Dict[str, Any]],
                             layout: Union[str, Dict[str, Tuple[float, float]]] = 'hierarchical',
                             title: Optional[str] = None,
                             node_size: int = 800,
                             show_labels: bool = True,
                             label_font_size: int = 10,
                             figsize: Tuple[int, int] = (12, 8),
                             dpi: int = 100,
                             highlight_slow: bool = True,
                             timing_threshold: float = 0.5) -> plt.Figure:
    """
    Visualize a graph with execution timing information.
    
    Args:
        graph: LangGraph StateGraph or NetworkX DiGraph
        execution_data: List of dicts with node execution data (must contain 'node' and 'duration' keys)
        layout: Layout algorithm name or pre-computed positions
        title: Optional title for the visualization
        node_size: Size of nodes in the visualization
        show_labels: Whether to show node labels
        label_font_size: Font size for node labels
        figsize: Figure size as (width, height) in inches
        dpi: Resolution in dots per inch
        highlight_slow: Whether to highlight slow nodes
        timing_threshold: Threshold in seconds for considering a node "slow"
        
    Returns:
        matplotlib.figure.Figure: Figure object for the visualization
    """
    # Convert to NetworkX graph if needed
    if isinstance(graph, StateGraph):
        G = extract_graph_structure(graph)
    else:
        G = graph
        
    # Extract execution path and create timing map
    execution_path = []
    node_timings = {}
    error_nodes = []
    
    for entry in execution_data:
        node_name = entry.get('node')
        if not node_name:
            continue
            
        execution_path.append(node_name)
        
        # Store timing information
        if 'duration' in entry:
            node_timings[node_name] = entry['duration']
            
        # Track error nodes
        if entry.get('success') is False:
            error_nodes.append(node_name)
    
    # Create a colormap for timing visualization
    if node_timings:
        min_time = min(node_timings.values())
        max_time = max(node_timings.values())
        
        if max_time > min_time:
            # Create a normalized colormap
            norm = mcolors.Normalize(vmin=min_time, vmax=max_time)
            cmap = plt.cm.coolwarm
            
            # Create a ScalarMappable for colormap
            sm = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
            sm.set_array([])
        else:
            # If all times are the same, use a fixed color
            norm = None
            cmap = None
            sm = None
    else:
        norm = None
        cmap = None
        sm = None
    
    # Create figure
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    
    # Get node positions based on specified layout
    pos = None
    if isinstance(layout, dict):
        # Use provided layout
        pos = layout
    elif layout == 'hierarchical':
        pos = apply_hierarchical_layout(G)
    elif layout == 'circular':
        pos = apply_circular_layout(G)
    elif layout == 'force':
        pos = apply_force_directed_layout(G)
    elif layout in LAYOUT_ALGORITHMS:
        pos = LAYOUT_ALGORITHMS[layout](G)
    else:
        viz_logger.warning(f"Unknown layout '{layout}', falling back to hierarchical")
        pos = apply_hierarchical_layout(G)
    
    # Group nodes by different categories
    normal_nodes = []
    timed_nodes = []
    slow_nodes = []
    error_nodes_list = error_nodes.copy()
    end_nodes = [END] if END in G.nodes() else []
    
    for node in G.nodes():
        if node in end_nodes:
            continue
        elif node in error_nodes_list:
            continue
        elif node in node_timings:
            if highlight_slow and node_timings[node] > timing_threshold:
                slow_nodes.append(node)
            else:
                timed_nodes.append(node)
        else:
            normal_nodes.append(node)
    
    # Draw normal nodes
    if normal_nodes:
        nx.draw_networkx_nodes(
            G, pos,
            nodelist=normal_nodes,
            node_size=node_size,
            node_color=NODE_COLORS['normal'],
            edgecolors='black',
            alpha=0.4,
            ax=ax
        )
    
    # Draw timed nodes with color based on timing
    if timed_nodes and sm is not None:
        # Get colors from colormap for each node
        node_colors = [sm.to_rgba(node_timings[node]) for node in timed_nodes]
        
        nx.draw_networkx_nodes(
            G, pos,
            nodelist=timed_nodes,
            node_size=node_size,
            node_color=node_colors,
            edgecolors='black',
            alpha=0.9,
            ax=ax
        )
    elif timed_nodes:
        # If no colormap available, use default executed color
        nx.draw_networkx_nodes(
            G, pos,
            nodelist=timed_nodes,
            node_size=node_size,
            node_color=NODE_COLORS['executed'],
            edgecolors='black',
            alpha=0.9,
            ax=ax
        )
    
    # Draw slow nodes with special color
    if slow_nodes:
        nx.draw_networkx_nodes(
            G, pos,
            nodelist=slow_nodes,
            node_size=node_size * 1.2,  # Make slightly larger
            node_color='#FF6600',  # Orange for slow nodes
            edgecolors='black',
            alpha=0.9,
            ax=ax
        )
    
    # Draw error nodes
    if error_nodes_list:
        nx.draw_networkx_nodes(
            G, pos,
            nodelist=error_nodes_list,
            node_size=node_size,
            node_color=NODE_COLORS['error'],
            edgecolors='black',
            alpha=0.9,
            ax=ax
        )
    
    # Draw end nodes
    if end_nodes:
        nx.draw_networkx_nodes(
            G, pos,
            nodelist=end_nodes,
            node_size=node_size,
            node_color=NODE_COLORS['end'],
            edgecolors='black',
            alpha=0.9,
            ax=ax
        )
    
    # Draw edges
    nx.draw_networkx_edges(
        G, pos,
        edge_color=EDGE_COLORS['normal'],
        width=1.5,
        arrowsize=15,
        arrowstyle='-|>',
        connectionstyle='arc3,rad=0.1',
        alpha=0.6,
        ax=ax
    )
    
    # Add labels if requested
    if show_labels:
        # Create labels with timing information
        labels = {}
        for node in G.nodes():
            if node in node_timings:
                # Format with node name and timing
                time_str = f"{node_timings[node]:.3f}s"
                labels[node] = f"{node}\n{time_str}"
            else:
                labels[node] = node
        
        nx.draw_networkx_labels(
            G, pos,
            labels=labels,
            font_size=label_font_size,
            font_weight='bold',
            font_color='black',
            ax=ax
        )
    
    # Add title if provided
    if title:
        plt.title(title, fontsize=14, pad=20)
    else:
        plt.title("Graph Execution Timing Visualization", fontsize=14, pad=20)
    
    # Add colorbar if using colormap
    if sm is not None:
        cbar = plt.colorbar(sm, ax=ax, orientation='vertical', pad=0.1)
        cbar.set_label('Execution Time (seconds)', fontsize=10)
    
    # Add legend for slow and error nodes
    legend_elements = []
    
    if slow_nodes:
        legend_elements.append(mpatches.Patch(color='#FF6600', label=f'Slow (>{timing_threshold}s)'))
    
    if error_nodes_list:
        legend_elements.append(mpatches.Patch(color=NODE_COLORS['error'], label='Error'))
        
    if end_nodes:
        legend_elements.append(mpatches.Patch(color=NODE_COLORS['end'], label='End'))
        
    if legend_elements:
        ax.legend(handles=legend_elements, loc='upper right', fontsize=10)
    
    # Remove axis
    plt.axis('off')
    
    # Adjust layout
    plt.tight_layout()
    
    return fig

def visualize_execution_path(trace_history: List[Dict[str, Any]], 
                          graph: Optional[Union[StateGraph, nx.DiGraph]] = None,
                          layout: str = 'hierarchical',
                          title: Optional[str] = None,
                          show_timing: bool = True,
                          figsize: Tuple[int, int] = (12, 8),
                          dpi: int = 100) -> plt.Figure:
    """
    Visualize the execution path from trace history.
    
    Args:
        trace_history: Execution trace history from the tracer
        graph: Optional graph structure (if None, extracted from trace history)
        layout: Layout algorithm name
        title: Optional title for the visualization
        show_timing: Whether to show timing information
        figsize: Figure size as (width, height) in inches
        dpi: Resolution in dots per inch
        
    Returns:
        matplotlib.figure.Figure: Figure object for the visualization
    """
    if not trace_history:
        viz_logger.warning("Empty trace history, cannot visualize execution path")
        fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
        ax.text(0.5, 0.5, "No trace history available", 
                ha='center', va='center', fontsize=14)
        plt.axis('off')
        return fig
    
    # Extract execution data
    execution_data = []
    for entry in trace_history:
        # Create a standardized entry
        node_data = {
            'node': entry.get('node', ''),
            'success': entry.get('success', True),
            'duration': entry.get('duration', 0),
            'error': entry.get('error', None)
        }
        execution_data.append(node_data)
    
    # Create or extract graph
    if graph is None:
        # Create a graph from trace history
        G = nx.DiGraph()
        
        # Add nodes from execution path
        for entry in execution_data:
            node_name = entry.get('node')
            if node_name:
                G.add_node(node_name)
        
        # Add edges following execution sequence
        for i in range(len(execution_data) - 1):
            current = execution_data[i].get('node')
            next_node = execution_data[i+1].get('node')
            if current and next_node:
                G.add_edge(current, next_node)
    else:
        # Use provided graph
        if isinstance(graph, StateGraph):
            G = extract_graph_structure(graph)
        else:
            G = graph
    
    # Determine if we should show timing based on available data
    has_timing = any('duration' in entry and entry['duration'] is not None 
                   for entry in execution_data)
    
    if show_timing and has_timing:
        return visualize_graph_with_timing(
            G, 
            execution_data,
            layout=layout,
            title=title or "Execution Path with Timing",
            figsize=figsize,
            dpi=dpi
        )
    else:
        # Extract execution path and error nodes
        execution_path = [entry.get('node') for entry in execution_data 
                        if entry.get('node')]
        
        error_nodes = [entry.get('node') for entry in execution_data 
                     if not entry.get('success', True) and entry.get('node')]
        
        return visualize_graph_with_execution(
            G,
            execution_path,
            error_nodes=error_nodes,
            layout=layout,
            title=title or "Execution Path",
            figsize=figsize,
            dpi=dpi
        ) 

def create_interactive_visualization(graph: Union[StateGraph, nx.DiGraph],
                                  execution_path: Optional[List[str]] = None,
                                  current_node: Optional[str] = None,
                                  error_nodes: Optional[List[str]] = None,
                                  node_timings: Optional[Dict[str, float]] = None,
                                  output_path: Optional[str] = None,
                                  title: Optional[str] = None,
                                  height: str = "600px",
                                  width: str = "100%",
                                  notebook: bool = False) -> Optional[str]:
    """
    Create an interactive graph visualization using Pyvis.
    
    Args:
        graph: LangGraph StateGraph or NetworkX DiGraph
        execution_path: Optional list of nodes in execution order
        current_node: Optional name of the currently executing node
        error_nodes: Optional list of nodes that encountered errors
        node_timings: Optional dict mapping node names to execution times
        output_path: Optional path to save the HTML visualization
        title: Optional title for the visualization
        height: Height of the visualization
        width: Width of the visualization
        notebook: Whether this is being used in a Jupyter notebook
        
    Returns:
        str: Path to the HTML file if saved, or HTML string if notebook=True
    """
    if not PYVIS_AVAILABLE:
        viz_logger.error("Pyvis is not available. Install with 'pip install pyvis'")
        return None
    
    # Convert to NetworkX graph if needed
    if isinstance(graph, StateGraph):
        G = extract_graph_structure(graph)
    else:
        G = graph
        
    # Create a Pyvis network
    net = Network(height=height, width=width, notebook=notebook, directed=True)
    
    # Set options for better visualization
    net.set_options("""
    {
      "nodes": {
        "font": {
          "size": 14,
          "face": "arial"
        },
        "borderWidth": 2,
        "shadow": true
      },
      "edges": {
        "arrows": {
          "to": {
            "enabled": true,
            "scaleFactor": 0.5
          }
        },
        "smooth": {
          "type": "curvedCW",
          "roundness": 0.2
        },
        "shadow": true
      },
      "physics": {
        "solver": "forceAtlas2Based",
        "maxVelocity": 50,
        "minVelocity": 0.1,
        "timestep": 0.5,
        "stabilization": {
          "enabled": true,
          "iterations": 1000
        }
      },
      "interaction": {
        "hover": true,
        "navigationButtons": true,
        "tooltipDelay": 100
      }
    }
    """)
    
    # Process execution path information
    node_status = {}
    if execution_path:
        for node in G.nodes():
            node_status[node] = get_node_execution_status(
                node, execution_path, current_node, error_nodes)
            
    # Create a set of executed edges
    executed_edges = set()
    if execution_path:
        for i in range(len(execution_path) - 1):
            executed_edges.add((execution_path[i], execution_path[i+1]))
    
    # Add nodes to the visualization
    for node in G.nodes():
        # Set node attributes based on status
        status = node_status.get(node, 'normal')
        
        # Base node attributes
        node_title = node
        node_color = NODE_COLORS[status]
        node_border = "#000000"
        node_size = 30
        
        # Check if this is the END node
        if node == END:
            node_shape = "diamond"
        else:
            node_shape = "dot"
            
        # Add timing information if available
        if node_timings and node in node_timings:
            node_title = f"{node}<br>Time: {node_timings[node]:.3f}s"
            
            # Adjust size based on timing (larger for slower nodes)
            node_size = min(50, 30 + node_timings[node] * 3)
        
        # Add error information
        if error_nodes and node in error_nodes:
            node_title = f"{node}<br>ERROR"
            node_border = "#FF0000"
            node_shape = "star"
        
        # Add current node indicator
        if current_node and node == current_node:
            node_border = "#FF9900"
            node_title = f"{node}<br>(CURRENT)"
            
        # Add the node to the network
        net.add_node(
            node, 
            label=node, 
            title=node_title,
            color=node_color,
            border_color=node_border,
            shape=node_shape,
            size=node_size
        )
    
    # Add edges to the visualization
    for u, v in G.edges():
        edge_color = EDGE_COLORS['normal']
        edge_width = 1
        edge_dashes = False
        
        # Check if this edge was executed
        if (u, v) in executed_edges:
            edge_color = EDGE_COLORS['executed']
            edge_width = 3
        
        # Get condition if available
        edge_title = f"{u} → {v}"
        if 'condition' in G.edges[u, v]:
            condition = G.edges[u, v]['condition']
            edge_title = f"{edge_title}<br>Condition: {condition}"
        
        net.add_edge(
            u, v,
            title=edge_title,
            color=edge_color,
            width=edge_width,
            dashes=edge_dashes
        )
    
    # Set title if provided
    if title:
        net.heading = title
    
    # Determine output method
    if output_path:
        # Create directory if needed
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        
        # Save to file
        net.save_graph(output_path)
        viz_logger.info(f"Interactive visualization saved to {output_path}")
        return output_path
    elif notebook:
        # Return HTML for notebook display
        return net.generate_html()
    else:
        # Save to a temporary file
        temp_dir = tempfile.gettempdir()
        temp_file = os.path.join(temp_dir, f"graph_viz_{uuid.uuid4().hex}.html")
        net.save_graph(temp_file)
        viz_logger.info(f"Interactive visualization saved to {temp_file}")
        return temp_file

def visualize_breakpoints(graph: Union[StateGraph, nx.DiGraph],
                       breakpoints: List[Dict[str, Any]],
                       output_path: Optional[str] = None,
                       title: str = "Graph with Breakpoints",
                       layout: str = 'hierarchical',
                       interactive: bool = False,
                       figsize: Tuple[int, int] = (12, 8),
                       dpi: int = 100) -> Union[plt.Figure, str]:
    """
    Visualize a graph with breakpoints highlighted.
    
    Args:
        graph: LangGraph StateGraph or NetworkX DiGraph
        breakpoints: List of breakpoint info dictionaries
        output_path: Optional path to save the visualization
        title: Title for the visualization
        layout: Layout algorithm name
        interactive: Whether to create an interactive visualization
        figsize: Figure size as (width, height) in inches
        dpi: Resolution in dots per inch
        
    Returns:
        Union[plt.Figure, str]: Figure object or path to HTML file
    """
    # Convert to NetworkX graph if needed
    if isinstance(graph, StateGraph):
        G = extract_graph_structure(graph)
    else:
        G = graph
    
    # Create a set of nodes with breakpoints
    breakpoint_nodes = set()
    breakpoint_conditions = {}
    
    for bp in breakpoints:
        node_name = bp.get('node')
        if not node_name:
            continue
            
        breakpoint_nodes.add(node_name)
        
        if 'condition' in bp and bp['condition']:
            breakpoint_conditions[node_name] = bp['condition']
    
    if interactive and PYVIS_AVAILABLE:
        # Create an interactive visualization
        net = Network(height="600px", width="100%", directed=True)
        
        # Set options
        net.set_options("""
        {
          "nodes": {
            "font": {
              "size": 14,
              "face": "arial"
            },
            "borderWidth": 2,
            "shadow": true
          },
          "edges": {
            "arrows": {
              "to": {
                "enabled": true,
                "scaleFactor": 0.5
              }
            },
            "smooth": {
              "type": "curvedCW",
              "roundness": 0.2
            }
          },
          "physics": {
            "stabilization": true
          }
        }
        """)
        
        # Add nodes
        for node in G.nodes():
            node_color = NODE_COLORS['normal']
            node_border = "#000000"
            node_title = node
            node_shape = "dot"
            
            if node == END:
                node_color = NODE_COLORS['end']
                node_shape = "diamond"
                
            if node in breakpoint_nodes:
                node_color = NODE_COLORS['breakpoint']
                node_border = "#FF00FF"
                
                if node in breakpoint_conditions:
                    node_title = f"{node}<br>Breakpoint Condition:<br>{breakpoint_conditions[node]}"
                else:
                    node_title = f"{node}<br>Unconditional Breakpoint"
            
            net.add_node(
                node, 
                label=node, 
                title=node_title,
                color=node_color,
                border_color=node_border,
                shape=node_shape
            )
        
        # Add edges
        for u, v in G.edges():
            edge_title = f"{u} → {v}"
            if 'condition' in G.edges[u, v]:
                condition = G.edges[u, v]['condition']
                edge_title = f"{edge_title}<br>Condition: {condition}"
                
            net.add_edge(u, v, title=edge_title)
        
        # Set title
        net.heading = title
        
        # Determine output method
        if output_path:
            # Create directory if needed
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            
            # Save to file
            net.save_graph(output_path)
            viz_logger.info(f"Interactive breakpoint visualization saved to {output_path}")
            return output_path
        else:
            # Save to a temporary file
            temp_dir = tempfile.gettempdir()
            temp_file = os.path.join(temp_dir, f"breakpoint_viz_{uuid.uuid4().hex}.html")
            net.save_graph(temp_file)
            viz_logger.info(f"Interactive breakpoint visualization saved to {temp_file}")
            return temp_file
    else:
        # Create a static visualization
        # Get node positions based on specified layout
        pos = None
        if layout == 'hierarchical':
            pos = apply_hierarchical_layout(G)
        elif layout == 'circular':
            pos = apply_circular_layout(G)
        elif layout == 'force':
            pos = apply_force_directed_layout(G)
        elif layout in LAYOUT_ALGORITHMS:
            pos = LAYOUT_ALGORITHMS[layout](G)
        else:
            viz_logger.warning(f"Unknown layout '{layout}', falling back to hierarchical")
            pos = apply_hierarchical_layout(G)
        
        # Create figure
        fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
        
        # Group nodes by status
        normal_nodes = []
        bp_nodes = []
        end_nodes = []
        
        for node in G.nodes():
            if node == END:
                end_nodes.append(node)
            elif node in breakpoint_nodes:
                bp_nodes.append(node)
            else:
                normal_nodes.append(node)
        
        # Draw normal nodes
        if normal_nodes:
            nx.draw_networkx_nodes(
                G, pos,
                nodelist=normal_nodes,
                node_size=800,
                node_color=NODE_COLORS['normal'],
                edgecolors='black',
                alpha=0.9,
                ax=ax
            )
        
        # Draw breakpoint nodes
        if bp_nodes:
            nx.draw_networkx_nodes(
                G, pos,
                nodelist=bp_nodes,
                node_size=900,  # Slightly larger
                node_color=NODE_COLORS['breakpoint'],
                edgecolors='#FF00FF',  # Magenta border
                linewidths=2.5,
                alpha=0.9,
                ax=ax
            )
        
        # Draw end nodes
        if end_nodes:
            nx.draw_networkx_nodes(
                G, pos,
                nodelist=end_nodes,
                node_size=800,
                node_color=NODE_COLORS['end'],
                edgecolors='black',
                alpha=0.9,
                ax=ax
            )
        
        # Draw edges
        nx.draw_networkx_edges(
            G, pos,
            edge_color=EDGE_COLORS['normal'],
            width=1.5,
            arrowsize=15,
            arrowstyle='-|>',
            connectionstyle='arc3,rad=0.1',
            alpha=0.8,
            ax=ax
        )
        
        # Add labels
        labels = {node: node for node in G.nodes()}
        nx.draw_networkx_labels(
            G, pos,
            labels=labels,
            font_size=10,
            font_weight='bold',
            font_color='black',
            ax=ax
        )
        
        # Add legend
        legend_elements = [
            mpatches.Patch(color=NODE_COLORS['normal'], label='Normal'),
            mpatches.Patch(color=NODE_COLORS['breakpoint'], label='Breakpoint'),
            mpatches.Patch(color=NODE_COLORS['end'], label='End')
        ]
        
        ax.legend(handles=legend_elements, loc='upper right', fontsize=10)
        
        # Add title
        plt.title(title, fontsize=14, pad=20)
        
        # Remove axis
        plt.axis('off')
        
        # Adjust layout
        plt.tight_layout()
        
        # Save if output path is provided
        if output_path:
            plt.savefig(output_path, dpi=dpi, bbox_inches='tight')
            viz_logger.info(f"Breakpoint visualization saved to {output_path}")
            
        return fig 

def visualize_performance_hotspots(graph: Union[StateGraph, nx.DiGraph],
                                execution_data: List[Dict[str, Any]],
                                output_path: Optional[str] = None,
                                title: str = "Performance Hotspots",
                                layout: str = 'hierarchical',
                                interactive: bool = False,
                                highlight_threshold: float = 0.5,
                                figsize: Tuple[int, int] = (12, 8),
                                dpi: int = 100) -> Union[plt.Figure, str]:
    """
    Visualize graph performance hotspots.
    
    Args:
        graph: LangGraph StateGraph or NetworkX DiGraph
        execution_data: List of dicts with node execution data (must contain 'node' and 'duration' keys)
        output_path: Optional path to save the visualization
        title: Title for the visualization
        layout: Layout algorithm name
        interactive: Whether to create an interactive visualization
        highlight_threshold: Threshold (seconds) for highlighting slow nodes
        figsize: Figure size as (width, height) in inches
        dpi: Resolution in dots per inch
        
    Returns:
        Union[plt.Figure, str]: Figure object or path to HTML file
    """
    # Extract timing data from execution data
    node_timings = {}
    error_nodes = []
    execution_path = []
    
    for entry in execution_data:
        node_name = entry.get('node')
        if not node_name:
            continue
            
        execution_path.append(node_name)
        
        # Store timing information
        if 'duration' in entry:
            node_timings[node_name] = entry['duration']
            
        # Track error nodes
        if entry.get('success') is False:
            error_nodes.append(node_name)
    
    if interactive and PYVIS_AVAILABLE:
        # Create an interactive visualization
        return create_interactive_visualization(
            graph,
            execution_path=execution_path,
            error_nodes=error_nodes,
            node_timings=node_timings,
            output_path=output_path,
            title=title or "Performance Hotspots Visualization",
            height="600px",
            width="100%"
        )
    else:
        # Get timing data min/max for color scaling
        if node_timings:
            min_time = min(node_timings.values())
            max_time = max(node_timings.values())
            
            # Create a figure
            return visualize_graph_with_timing(
                graph,
                execution_data,
                layout=layout,
                title=title,
                highlight_slow=True,
                timing_threshold=highlight_threshold,
                figsize=figsize,
                dpi=dpi
            )
        else:
            # If no timing data, use normal execution visualization
            return visualize_graph_with_execution(
                graph,
                execution_path,
                error_nodes=error_nodes,
                layout=layout,
                title=title,
                figsize=figsize,
                dpi=dpi
            )

def visualize_graph_with_errors(graph: Union[StateGraph, nx.DiGraph],
                             error_data: Dict[str, Any],
                             output_path: Optional[str] = None,
                             title: Optional[str] = None,
                             layout: str = 'hierarchical',
                             interactive: bool = False,
                             figsize: Tuple[int, int] = (12, 8),
                             dpi: int = 100) -> Union[plt.Figure, str]:
    """
    Visualize a graph with error information.
    
    Args:
        graph: LangGraph StateGraph or NetworkX DiGraph
        error_data: Dict mapping node names to error information
        output_path: Optional path to save the visualization
        title: Optional title for the visualization
        layout: Layout algorithm name
        interactive: Whether to create an interactive visualization
        figsize: Figure size as (width, height) in inches
        dpi: Resolution in dots per inch
        
    Returns:
        Union[plt.Figure, str]: Figure object or path to HTML file
    """
    # Convert to NetworkX graph if needed
    if isinstance(graph, StateGraph):
        G = extract_graph_structure(graph)
    else:
        G = graph
    
    # Get error nodes
    error_nodes = list(error_data.keys())
    
    if interactive and PYVIS_AVAILABLE:
        # Create a Pyvis network
        net = Network(height="600px", width="100%", directed=True)
        
        # Set options for better visualization
        net.set_options("""
        {
          "nodes": {
            "font": {
              "size": 14,
              "face": "arial"
            },
            "borderWidth": 2,
            "shadow": true
          },
          "edges": {
            "arrows": {
              "to": {
                "enabled": true,
                "scaleFactor": 0.5
              }
            },
            "smooth": {
              "type": "curvedCW",
              "roundness": 0.2
            },
            "shadow": true
          },
          "physics": {
            "solver": "forceAtlas2Based",
            "stabilization": true
          }
        }
        """)
        
        # Add nodes to the visualization
        for node in G.nodes():
            # Base node attributes
            node_title = str(node)
            node_color = NODE_COLORS['normal']
            node_border = "#000000"
            node_shape = "dot"
            node_size = 30
            
            # Check if this is the END node
            if node == END:
                node_color = NODE_COLORS['end']
                node_shape = "diamond"
                
            # Check if this is an error node
            if node in error_nodes:
                node_color = NODE_COLORS['error']
                node_border = "#FF0000"
                node_shape = "star"
                node_size = 40
                
                # Add detailed error information to tooltip
                error_info = error_data[node]
                if isinstance(error_info, str):
                    node_title = f"{node}<br>Error: {error_info}"
                elif isinstance(error_info, dict):
                    error_msg = error_info.get('message', 'Unknown error')
                    error_type = error_info.get('type', 'Error')
                    node_title = f"{node}<br>Error Type: {error_type}<br>Message: {error_msg}"
                else:
                    node_title = f"{node}<br>Error: {str(error_info)}"
            
            # Add the node to the network
            net.add_node(
                node, 
                label=node, 
                title=node_title,
                color=node_color,
                border_color=node_border,
                shape=node_shape,
                size=node_size
            )
        
        # Add edges to the visualization
        for u, v in G.edges():
            edge_color = EDGE_COLORS['normal']
            edge_width = 1
            
            # Add warning color if edge leads to an error node
            if v in error_nodes:
                edge_color = EDGE_COLORS['error']
                edge_width = 2
            
            # Get condition if available
            edge_title = f"{u} → {v}"
            if 'condition' in G.edges[u, v]:
                condition = G.edges[u, v]['condition']
                edge_title = f"{edge_title}<br>Condition: {condition}"
            
            net.add_edge(
                u, v,
                title=edge_title,
                color=edge_color,
                width=edge_width
            )
        
        # Set title if provided
        if title:
            net.heading = title
        else:
            net.heading = "Graph Error Visualization"
        
        # Determine output method
        if output_path:
            # Create directory if needed
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            
            # Save to file
            net.save_graph(output_path)
            viz_logger.info(f"Interactive error visualization saved to {output_path}")
            return output_path
        else:
            # Save to a temporary file
            temp_dir = tempfile.gettempdir()
            temp_file = os.path.join(temp_dir, f"error_viz_{uuid.uuid4().hex}.html")
            net.save_graph(temp_file)
            viz_logger.info(f"Interactive error visualization saved to {temp_file}")
            return temp_file
    else:
        # Create a static visualization using matplotlib
        # Get node positions based on specified layout
        pos = None
        if layout == 'hierarchical':
            pos = apply_hierarchical_layout(G)
        elif layout == 'circular':
            pos = apply_circular_layout(G)
        elif layout == 'force':
            pos = apply_force_directed_layout(G)
        elif layout in LAYOUT_ALGORITHMS:
            pos = LAYOUT_ALGORITHMS[layout](G)
        else:
            viz_logger.warning(f"Unknown layout '{layout}', falling back to hierarchical")
            pos = apply_hierarchical_layout(G)
        
        # Create figure
        fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
        
        # Group nodes by status
        normal_nodes = []
        error_nodes_list = error_nodes.copy()
        end_nodes = []
        
        for node in G.nodes():
            if node == END:
                end_nodes.append(node)
            elif node in error_nodes_list:
                continue  # Will be drawn separately
            else:
                normal_nodes.append(node)
        
        # Draw normal nodes
        if normal_nodes:
            nx.draw_networkx_nodes(
                G, pos,
                nodelist=normal_nodes,
                node_size=800,
                node_color=NODE_COLORS['normal'],
                edgecolors='black',
                alpha=0.9,
                ax=ax
            )
        
        # Draw end nodes
        if end_nodes:
            nx.draw_networkx_nodes(
                G, pos,
                nodelist=end_nodes,
                node_size=800,
                node_color=NODE_COLORS['end'],
                edgecolors='black',
                alpha=0.9,
                ax=ax
            )
        
        # Draw error nodes
        if error_nodes_list:
            nx.draw_networkx_nodes(
                G, pos,
                nodelist=error_nodes_list,
                node_size=1000,  # Larger to emphasize errors
                node_color=NODE_COLORS['error'],
                edgecolors='#FF0000',  # Red border
                linewidths=2.5,
                alpha=1.0,
                ax=ax
            )
        
        # Group edges by status
        normal_edges = []
        error_edges = []
        
        for u, v in G.edges():
            if v in error_nodes_list:
                error_edges.append((u, v))
            else:
                normal_edges.append((u, v))
        
        # Draw normal edges
        if normal_edges:
            nx.draw_networkx_edges(
                G, pos,
                edgelist=normal_edges,
                edge_color=EDGE_COLORS['normal'],
                width=1.5,
                arrowsize=15,
                arrowstyle='-|>',
                connectionstyle='arc3,rad=0.1',
                alpha=0.8,
                ax=ax
            )
        
        # Draw error edges
        if error_edges:
            nx.draw_networkx_edges(
                G, pos,
                edgelist=error_edges,
                edge_color=EDGE_COLORS['error'],
                width=2.5,
                arrowsize=20,
                arrowstyle='-|>',
                connectionstyle='arc3,rad=0.1',
                alpha=1.0,
                ax=ax
            )
        
        # Add labels
        labels = {node: node for node in G.nodes()}
        nx.draw_networkx_labels(
            G, pos,
            labels=labels,
            font_size=10,
            font_weight='bold',
            font_color='black',
            ax=ax
        )
        
        # Add legend
        legend_elements = [
            mpatches.Patch(color=NODE_COLORS['normal'], label='Normal'),
            mpatches.Patch(color=NODE_COLORS['error'], label='Error'),
            mpatches.Patch(color=NODE_COLORS['end'], label='End')
        ]
        
        ax.legend(handles=legend_elements, loc='upper right', fontsize=10)
        
        # Add title
        plt.title(title or "Graph Error Visualization", fontsize=14, pad=20)
        
        # Remove axis
        plt.axis('off')
        
        # Adjust layout
        plt.tight_layout()
        
        # Save if output path is provided
        if output_path:
            plt.savefig(output_path, dpi=dpi, bbox_inches='tight')
            viz_logger.info(f"Error visualization saved to {output_path}")
            
        return fig 

def visualize_timeline(trace_history: List[Dict[str, Any]], 
                      output_path: Optional[str] = None,
                      width: int = 12, height: int = 6) -> Optional[str]:
    """
    Generate a timeline visualization of the execution flow.
    
    Args:
        trace_history: List of trace entries
        output_path: Path to save the visualization (None for auto-generated)
        width: Figure width in inches
        height: Figure height in inches
        
    Returns:
        Path to the saved visualization file or None if failed
    """
    if not trace_history:
        viz_logger.warning("No trace history to visualize")
        return None
        
    try:
        # Create figure
        fig, ax = plt.subplots(figsize=(width, height))
        
        # Extract data
        node_names = []
        start_times = []
        durations = []
        colors = []
        
        # Set the reference start time
        if trace_history:
            reference_time = min(entry.get('timestamp', 0) for entry in trace_history)
        else:
            reference_time = 0
            
        # Process each entry
        for i, entry in enumerate(trace_history):
            node_name = entry.get('node', f'Node{i}')
            start_time = entry.get('timestamp', 0) - reference_time
            duration = entry.get('duration', 0)
            success = entry.get('success', True)
            
            node_names.append(node_name)
            start_times.append(start_time)
            durations.append(duration)
            colors.append('green' if success else 'red')
            
        # Plot bars
        y_positions = range(len(node_names))
        ax.barh(y_positions, durations, left=start_times, color=colors, alpha=0.7)
        
        # Add labels
        ax.set_yticks(y_positions)
        ax.set_yticklabels(node_names)
        ax.set_xlabel('Time (seconds)')
        ax.set_ylabel('Node')
        ax.set_title('Execution Timeline')
        
        # Add legend
        handles = [Rectangle((0,0), 1, 1, color='green'), Rectangle((0,0), 1, 1, color='red')]
        ax.legend(handles, ['Success', 'Failure'])
        
        # Generate output path if not provided
        if output_path is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(TIMELINE_DIR, f"timeline_{timestamp}.png")
            
        # Save the figure
        plt.tight_layout()
        plt.savefig(output_path)
        plt.close(fig)
        
        viz_logger.info(f"Timeline visualization saved to {output_path}")
        return output_path
        
    except Exception as e:
        viz_logger.error(f"Error visualizing timeline: {e}")
        viz_logger.debug(traceback.format_exc())
        return None

def visualize_state_changes(state_before: Dict[str, Any], 
                           state_after: Dict[str, Any],
                           output_path: Optional[str] = None) -> Optional[str]:
    """
    Visualize the changes between two states.
    
    Args:
        state_before: State before changes
        state_after: State after changes
        output_path: Path to save the visualization (None for auto-generated)
        
    Returns:
        Path to the saved visualization file or None if failed
    """
    try:
        # Import identify_state_changes
        from src.tracing import _identify_state_changes
        
        # Get changes
        changes = _identify_state_changes(state_before, state_after)
        
        if not changes:
            viz_logger.warning("No changes to visualize")
            return None
            
        # Create figure
        fig, ax = plt.subplots(figsize=(10, 8))
        ax.axis('off')  # Hide the axes
        
        # Format changes as text
        text_lines = ["State Changes:"]
        text_lines.append("=" * 40)
        
        for path, change in changes.items():
            change_type = change.get('change_type', 'unknown')
            before_val = change.get('before', 'N/A')
            after_val = change.get('after', 'N/A')
            
            if change_type == 'added':
                text_lines.append(f"+ Added: {path} = {after_val}")
            elif change_type == 'removed':
                text_lines.append(f"- Removed: {path} = {before_val}")
            else:
                text_lines.append(f"~ Changed: {path}")
                text_lines.append(f"  Before: {before_val}")
                text_lines.append(f"  After:  {after_val}")
                
        text = "\n".join(text_lines)
        
        # Add text to figure
        ax.text(0.05, 0.95, text, transform=ax.transAxes, 
               fontsize=10, verticalalignment='top', family='monospace')
        
        # Generate output path if not provided
        if output_path is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(STATE_VIZ_DIR, f"state_changes_{timestamp}.png")
            
        # Save the figure
        plt.tight_layout()
        plt.savefig(output_path)
        plt.close(fig)
        
        viz_logger.info(f"State changes visualization saved to {output_path}")
        return output_path
        
    except Exception as e:
        viz_logger.error(f"Error visualizing state changes: {e}")
        viz_logger.debug(traceback.format_exc())
        return None

def create_execution_report(trace_history: List[Dict[str, Any]], 
                           output_path: Optional[str] = None) -> Optional[str]:
    """
    Create a simple HTML report of the execution.
    
    Args:
        trace_history: List of trace entries
        output_path: Path to save the report (None for auto-generated)
        
    Returns:
        Path to the saved report file or None if failed
    """
    if not trace_history:
        viz_logger.warning("No trace history for report")
        return None
        
    try:
        # Generate output path if not provided
        if output_path is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(VIZ_LOG_DIR, f"report_{timestamp}.html")
            
        # Create timeline visualization
        timeline_img = visualize_timeline(trace_history)
        timeline_rel_path = os.path.relpath(timeline_img, os.path.dirname(output_path))
        
        # Calculate basic statistics
        total_nodes = len(trace_history)
        successful_nodes = sum(1 for entry in trace_history if entry.get('success', True))
        failed_nodes = total_nodes - successful_nodes
        total_time = sum(entry.get('duration', 0) for entry in trace_history)
        
        # Create HTML content
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Execution Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1, h2 {{ color: #333; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .success {{ color: green; }}
                .failure {{ color: red; }}
                .viz {{ margin: 20px 0; }}
                .viz img {{ max-width: 100%; border: 1px solid #ddd; }}
                .summary {{ display: flex; justify-content: space-around; }}
                .stat {{ padding: 15px; background-color: #f9f9f9; border-radius: 5px;
                       border: 1px solid #ddd; margin: 10px; min-width: 150px; text-align: center; }}
            </style>
        </head>
        <body>
            <h1>Execution Report</h1>
            <p>Generated on {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            
            <div class="summary">
                <div class="stat">
                    <h3>Total Nodes</h3>
                    <p>{total_nodes}</p>
                </div>
                <div class="stat">
                    <h3>Successful</h3>
                    <p class="success">{successful_nodes}</p>
                </div>
                <div class="stat">
                    <h3>Failed</h3>
                    <p class="failure">{failed_nodes}</p>
                </div>
                <div class="stat">
                    <h3>Total Time</h3>
                    <p>{total_time:.4f}s</p>
                </div>
            </div>
            
            <h2>Execution Timeline</h2>
            <div class="viz">
                <img src="{timeline_rel_path}" alt="Execution Timeline">
            </div>
            
            <h2>Execution Details</h2>
            <table>
                <tr>
                    <th>#</th>
                    <th>Node</th>
                    <th>Status</th>
                    <th>Duration</th>
                </tr>
        """
        
        # Add rows for each node execution
        for i, entry in enumerate(trace_history):
            node_name = entry.get('node', f'Node{i}')
            success = entry.get('success', True)
            duration = entry.get('duration', 0)
            status_class = "success" if success else "failure"
            status_text = "Success" if success else "Failed"
            
            html += f"""
                <tr>
                    <td>{i+1}</td>
                    <td>{node_name}</td>
                    <td class="{status_class}">{status_text}</td>
                    <td>{duration:.4f}s</td>
                </tr>
            """
            
        # Close HTML
        html += """
            </table>
        </body>
        </html>
        """
        
        # Write to file
        with open(output_path, 'w') as f:
            f.write(html)
            
        viz_logger.info(f"Execution report saved to {output_path}")
        return output_path
        
    except Exception as e:
        viz_logger.error(f"Error creating execution report: {e}")
        viz_logger.debug(traceback.format_exc())
        return None 