#!/usr/bin/env python3
"""
Visualization Helper for State Verification Framework.

This module provides enhanced visualization capabilities for the
State Verification Framework at different verbosity levels.
"""

import os
import sys
import json
import time
import datetime
import argparse
from typing import Dict, Any, List, Optional, Tuple

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.state_verification import (
    VERIFICATION_LEVEL_BASIC,
    VERIFICATION_LEVEL_STANDARD,
    VERIFICATION_LEVEL_DETAILED,
    VERIFICATION_LEVEL_DIAGNOSTIC
)
from src.logger import setup_logger

# Setup logger
logger = setup_logger('VerificationViz')

def get_level_name(level: int) -> str:
    """
    Convert verification level constant to name.
    
    Args:
        level: Verification level constant
        
    Returns:
        str: Level name
    """
    level_map = {
        VERIFICATION_LEVEL_BASIC: "BASIC",
        VERIFICATION_LEVEL_STANDARD: "STANDARD",
        VERIFICATION_LEVEL_DETAILED: "DETAILED",
        VERIFICATION_LEVEL_DIAGNOSTIC: "DIAGNOSTIC"
    }
    
    return level_map.get(level, f"UNKNOWN ({level})")

def generate_state_diagram(
    output_dir: str,
    history_data: List[Dict[str, Any]],
    level: int,
    include_timestamps: bool = True,
    include_validation: bool = True
) -> str:
    """
    Generate a detailed state flow diagram in HTML format.
    
    Args:
        output_dir: Directory to save the diagram
        history_data: State history data
        level: Verification level used
        include_timestamps: Whether to include timestamps in the diagram
        include_validation: Whether to include validation results
        
    Returns:
        str: Path to the generated diagram
    """
    import html
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # HTML template
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>State Verification Flow Diagram</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .container { display: flex; flex-direction: column; }
            .header { background-color: #4b8bf4; color: white; padding: 10px; border-radius: 5px 5px 0 0; }
            .timestamp { color: #aaa; font-size: 0.8em; margin-top: 5px; }
            .node { border: 1px solid #ddd; margin-bottom: 20px; border-radius: 5px; box-shadow: 2px 2px 8px rgba(0,0,0,0.1); overflow: hidden; }
            .node-content { padding: 10px; font-family: monospace; white-space: pre-wrap; }
            .node-title { font-weight: bold; margin-bottom: 10px; }
            .state-diff { margin-top: 10px; background-color: #f5f5f5; padding: 5px; border-radius: 3px; }
            .validation { margin-top: 10px; }
            .validation-pass { color: green; }
            .validation-fail { color: red; }
            .transition { display: flex; align-items: center; margin: 10px 0; }
            .arrow { flex-grow: 0; margin: 0 10px; color: #666; }
            .summary { background-color: #f0f0f0; padding: 10px; margin-bottom: 20px; border-radius: 5px; }
            .level-basic { border-left: 5px solid #4CAF50; }
            .level-standard { border-left: 5px solid #2196F3; }
            .level-detailed { border-left: 5px solid #FF9800; }
            .level-diagnostic { border-left: 5px solid #F44336; }
            .error { background-color: #ffebee; color: #d32f2f; padding: 5px; border-radius: 3px; margin-top: 5px; }
        </style>
    </head>
    <body>
        <h1>State Verification Flow Diagram</h1>
        <div class="summary">
            <h2>Verification Summary</h2>
            <p><strong>Verification Level:</strong> {level_name}</p>
            <p><strong>Total Nodes:</strong> {total_nodes}</p>
            <p><strong>Validation Errors:</strong> {total_errors}</p>
            <p><strong>Generated:</strong> {timestamp}</p>
        </div>
        <div class="container">
            {nodes}
        </div>
        <script>
            function toggleSection(id) {
                var section = document.getElementById(id);
                if (section.style.display === "none") {
                    section.style.display = "block";
                } else {
                    section.style.display = "none";
                }
            }
        </script>
    </body>
    </html>
    """
    
    level_name = get_level_name(level)
    level_class = f"level-{level_name.lower()}"
    
    # Process nodes
    nodes_html = ""
    total_errors = 0
    
    for i, entry in enumerate(history_data):
        node_name = entry.get("node_name", f"Node {i}")
        
        # Node header
        node_html = f"""
        <div class="node {level_class}">
            <div class="header">
                <div>{node_name}</div>
        """
        
        # Add timestamp if available and requested
        if include_timestamps and "timestamp" in entry:
            node_html += f'<div class="timestamp">{entry["timestamp"]}</div>'
        
        node_html += "</div><div class='node-content'>"
        
        # Show state content based on level
        if level >= VERIFICATION_LEVEL_STANDARD:
            # Filter out internal verification fields
            state_content = {k: v for k, v in entry.items() if not k.startswith("_verification")}
            node_html += f"<div class='node-title'>State:</div>"
            
            # For diagnostic level, show full state
            if level >= VERIFICATION_LEVEL_DIAGNOSTIC:
                node_html += html.escape(json.dumps(state_content, indent=2))
            else:
                # For other levels, show key fields only
                key_fields = ["task_name", "active_component", "error"]
                key_state = {k: v for k, v in state_content.items() if k in key_fields}
                node_html += html.escape(json.dumps(key_state, indent=2))
                
                # Show state size if detailed or higher
                if level >= VERIFICATION_LEVEL_DETAILED and "_verification_state_size" in entry:
                    node_html += f"\n\nState Size: {entry['_verification_state_size']} bytes"
        
        # Show validation results if requested and available
        if include_validation and "_verification_errors" in entry:
            errors = entry.get("_verification_errors", [])
            if errors:
                total_errors += len(errors)
                node_html += f"<div class='validation'>"
                node_html += f"<div class='node-title validation-fail'>Validation Errors ({len(errors)}):</div>"
                for error in errors:
                    node_html += f"<div class='error'>{html.escape(str(error))}</div>"
                node_html += "</div>"
        
        if include_validation and "_verification_results" in entry:
            results = entry.get("_verification_results", {})
            if results:
                node_html += f"<div class='validation'>"
                node_html += f"<div class='node-title'>Validation Results:</div>"
                for name, result in results.items():
                    status = "✓" if result else "✗"
                    status_class = "validation-pass" if result else "validation-fail"
                    node_html += f"<div class='{status_class}'>{status} {html.escape(name)}</div>"
                node_html += "</div>"
        
        node_html += "</div></div>"
        
        # Add transition arrow if not the last node
        if i < len(history_data) - 1:
            node_html += """
            <div class="transition">
                <div class="arrow">↓</div>
            </div>
            """
        
        nodes_html += node_html
    
    # Format the HTML
    html_content = html_template.format(
        level_name=level_name,
        total_nodes=len(history_data),
        total_errors=total_errors,
        timestamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        nodes=nodes_html
    )
    
    # Write to file
    output_path = os.path.join(output_dir, "state_flow_diagram.html")
    with open(output_path, "w") as f:
        f.write(html_content)
    
    logger.info(f"State flow diagram generated: {output_path}")
    return output_path

def generate_performance_graphs(
    output_dir: str,
    history_data: List[Dict[str, Any]],
    include_timestamps: bool = True
) -> Optional[str]:
    """
    Generate performance graphs from state history.
    
    Args:
        output_dir: Directory to save the graphs
        history_data: State history data
        include_timestamps: Whether to include timestamps
        
    Returns:
        Optional[str]: Path to the generated graphs, or None if matplotlib not available
    """
    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        logger.warning("Matplotlib not available, skipping performance graphs")
        return None
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Extract timestamps and performance metrics
    timestamps = []
    latencies = []
    accuracies = []
    memory_usages = []
    
    for entry in history_data:
        # Track timestamps if available and requested
        if include_timestamps and "timestamp" in entry:
            timestamps.append(entry["timestamp"])
        else:
            # Use simple sequence if timestamps not available
            timestamps.append(len(timestamps) + 1)
        
        # Extract performance metrics if available
        if "execution_performance" in entry:
            perf = entry["execution_performance"]
            latencies.append(perf.get("latency", 0))
            accuracies.append(perf.get("accuracy", 0))
            
            # Extract memory usage if available
            if "resource_usage" in perf and "memory" in perf["resource_usage"]:
                memory_usages.append(perf["resource_usage"]["memory"])
            else:
                memory_usages.append(0)
    
    # Skip if no performance metrics found
    if not latencies or all(l == 0 for l in latencies):
        logger.warning("No performance metrics found in state history")
        return None
    
    # Create figure with subplots
    fig, axs = plt.subplots(3, 1, figsize=(10, 12))
    
    # Plot latency
    axs[0].plot(timestamps, latencies, marker='o', linestyle='-', color='blue')
    axs[0].set_title('Latency Over Time')
    axs[0].set_xlabel('Time' if include_timestamps else 'Sequence')
    axs[0].set_ylabel('Latency (s)')
    axs[0].grid(True)
    
    # Plot accuracy
    axs[1].plot(timestamps, accuracies, marker='s', linestyle='-', color='green')
    axs[1].set_title('Accuracy Over Time')
    axs[1].set_xlabel('Time' if include_timestamps else 'Sequence')
    axs[1].set_ylabel('Accuracy')
    axs[1].grid(True)
    
    # Plot memory usage if available
    if any(m > 0 for m in memory_usages):
        axs[2].plot(timestamps, memory_usages, marker='^', linestyle='-', color='red')
        axs[2].set_title('Memory Usage Over Time')
        axs[2].set_xlabel('Time' if include_timestamps else 'Sequence')
        axs[2].set_ylabel('Memory Usage')
        axs[2].grid(True)
    else:
        axs[2].text(0.5, 0.5, 'No memory usage data available', 
                    horizontalalignment='center', verticalalignment='center',
                    transform=axs[2].transAxes)
    
    # Adjust layout and save
    plt.tight_layout()
    output_path = os.path.join(output_dir, "performance_graphs.png")
    plt.savefig(output_path)
    plt.close()
    
    logger.info(f"Performance graphs generated: {output_path}")
    return output_path

def enhance_verification_report(
    report_path: str,
    level: int,
    output_dir: Optional[str] = None
) -> Tuple[str, Optional[str]]:
    """
    Enhance the verification report with additional visualizations.
    
    Args:
        report_path: Path to the verification report JSON
        level: Verification level used
        output_dir: Directory to save enhanced visualizations
        
    Returns:
        Tuple[str, Optional[str]]: Paths to the generated diagram and performance graphs
    """
    if output_dir is None:
        output_dir = os.path.dirname(report_path)
    
    # Load the report
    try:
        with open(report_path, 'r') as f:
            report_data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.error(f"Error loading report file: {e}")
        return None, None
    
    # Extract state history
    history_data = report_data.get("state_history", [])
    if not history_data:
        logger.error("No state history found in report")
        return None, None
    
    # Generate enhanced diagram
    include_timestamps = level >= VERIFICATION_LEVEL_STANDARD
    include_validation = level >= VERIFICATION_LEVEL_STANDARD
    
    diagram_path = generate_state_diagram(
        output_dir=output_dir,
        history_data=history_data,
        level=level,
        include_timestamps=include_timestamps,
        include_validation=include_validation
    )
    
    # Generate performance graphs for DETAILED and above
    performance_path = None
    if level >= VERIFICATION_LEVEL_DETAILED:
        performance_path = generate_performance_graphs(
            output_dir=output_dir,
            history_data=history_data,
            include_timestamps=include_timestamps
        )
    
    return diagram_path, performance_path

def main():
    """Main function for the visualization helper."""
    parser = argparse.ArgumentParser(description="State Verification Visualization Helper")
    parser.add_argument("--report", required=True, help="Path to verification report JSON file")
    parser.add_argument("--level", type=int, default=VERIFICATION_LEVEL_STANDARD, 
                      help="Verification level (1=Basic, 2=Standard, 3=Detailed, 4=Diagnostic)")
    parser.add_argument("--output", help="Directory to save enhanced visualizations")
    args = parser.parse_args()
    
    # Enhance the report
    diagram_path, performance_path = enhance_verification_report(
        report_path=args.report,
        level=args.level,
        output_dir=args.output
    )
    
    if diagram_path:
        print(f"Enhanced state flow diagram generated: {diagram_path}")
    
    if performance_path:
        print(f"Performance graphs generated: {performance_path}")

if __name__ == "__main__":
    main() 