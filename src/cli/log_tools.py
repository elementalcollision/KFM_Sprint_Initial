"""
Command-line interface for the enhanced logging system.

This module provides command-line tools for analyzing logs, generating
reports, and visualizing execution data.
"""

import os
import sys
import argparse
import json
import datetime
import logging
from typing import List, Dict, Any, Optional, Tuple

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.logger import setup_logger
from src.tracing import get_trace_history, create_execution_summary
from src.visualization import (
    visualize_timeline, 
    visualize_state_changes,
    create_execution_report
)

# Setup logger
cli_logger = setup_logger("log_tools_cli")

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Log analysis and visualization tools"
    )
    
    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Create 'analyze' command
    analyze_parser = subparsers.add_parser(
        "analyze", help="Analyze log files and generate reports"
    )
    analyze_parser.add_argument(
        "--log-dir", "-d", 
        help="Directory containing log files to analyze",
        default="logs"
    )
    analyze_parser.add_argument(
        "--output", "-o",
        help="Path to save the analysis report",
        default="logs/analysis_report.html"
    )
    analyze_parser.add_argument(
        "--format", "-f",
        help="Format of the report (html, json, or text)",
        choices=["html", "json", "text"],
        default="html"
    )
    
    # Create 'visualize' command
    visualize_parser = subparsers.add_parser(
        "visualize", help="Visualize execution data"
    )
    visualize_parser.add_argument(
        "--log-file", "-l", 
        help="Log file or trace file to visualize",
        required=True
    )
    visualize_parser.add_argument(
        "--output", "-o",
        help="Path to save the visualization",
        default=None
    )
    visualize_parser.add_argument(
        "--type", "-t",
        help="Type of visualization (timeline, state, report)",
        choices=["timeline", "state", "report"],
        default="timeline"
    )
    
    # Create 'monitor' command
    monitor_parser = subparsers.add_parser(
        "monitor", help="Monitor log files in real-time"
    )
    monitor_parser.add_argument(
        "--log-file", "-l", 
        help="Log file to monitor",
        required=True
    )
    monitor_parser.add_argument(
        "--interval", "-i",
        help="Refresh interval in seconds",
        type=float,
        default=1.0
    )
    
    # Create 'summary' command
    summary_parser = subparsers.add_parser(
        "summary", help="Generate a summary of execution logs"
    )
    summary_parser.add_argument(
        "--run-dir", "-r", 
        help="Directory containing run data",
        required=True
    )
    summary_parser.add_argument(
        "--output", "-o",
        help="Path to save the summary report",
        default=None
    )
    
    return parser.parse_args()

def find_log_files(log_dir: str, pattern: str = "*.log") -> List[str]:
    """
    Find log files in the given directory matching the pattern.
    
    Args:
        log_dir: Directory to search for log files
        pattern: File pattern to match
        
    Returns:
        List of file paths
    """
    import glob
    
    log_files = []
    
    # Find all files matching the pattern
    search_path = os.path.join(log_dir, "**", pattern)
    log_files.extend(glob.glob(search_path, recursive=True))
    
    return log_files

def load_trace_file(file_path: str) -> List[Dict[str, Any]]:
    """
    Load a trace file containing execution traces.
    
    Args:
        file_path: Path to the trace file
        
    Returns:
        List of trace entries
    """
    try:
        if file_path.endswith(".json"):
            with open(file_path, "r") as f:
                return json.load(f)
        elif file_path.endswith(".jsonl"):
            traces = []
            with open(file_path, "r") as f:
                for line in f:
                    if line.strip():
                        traces.append(json.loads(line))
            return traces
        else:
            cli_logger.error(f"Unsupported file format: {file_path}")
            return []
    except Exception as e:
        cli_logger.error(f"Error loading trace file: {e}")
        return []

def analyze_logs(log_dir: str, output_path: str, format: str = "html") -> bool:
    """
    Analyze log files and generate a report.
    
    Args:
        log_dir: Directory containing log files
        output_path: Path to save the analysis report
        format: Format of the report (html, json, or text)
        
    Returns:
        True if successful, False otherwise
    """
    cli_logger.info(f"Analyzing logs in {log_dir}...")
    
    # Find log files
    log_files = find_log_files(log_dir)
    
    if not log_files:
        cli_logger.warning(f"No log files found in {log_dir}")
        return False
    
    cli_logger.info(f"Found {len(log_files)} log files")
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Load and analyze logs
    analysis_data = {
        "summary": {
            "total_files": len(log_files),
            "analysis_date": datetime.datetime.now().isoformat(),
            "log_directory": os.path.abspath(log_dir)
        },
        "files": {},
        "errors": {},
        "performance": {}
    }
    
    # Process each log file
    for log_file in log_files:
        file_name = os.path.basename(log_file)
        
        # Extract log type from filename
        log_type = "unknown"
        if "node" in file_name:
            log_type = "node"
        elif "error" in file_name:
            log_type = "error"
        elif "trace" in file_name:
            log_type = "trace"
        elif "performance" in file_name:
            log_type = "performance"
            
        analysis_data["files"][file_name] = {
            "path": log_file,
            "type": log_type,
            "size": os.path.getsize(log_file),
            "last_modified": datetime.datetime.fromtimestamp(
                os.path.getmtime(log_file)
            ).isoformat()
        }
        
        # Count errors in error logs
        if log_type == "error":
            error_count = 0
            with open(log_file, "r") as f:
                for line in f:
                    if "ERROR" in line:
                        error_count += 1
            analysis_data["errors"][file_name] = error_count
            
        # Extract performance data from performance logs
        if log_type == "performance":
            try:
                with open(log_file, "r") as f:
                    performance_data = json.load(f)
                analysis_data["performance"][file_name] = performance_data
            except Exception as e:
                cli_logger.warning(f"Error parsing performance data from {file_name}: {e}")
    
    # Generate report based on format
    try:
        if format == "json":
            with open(output_path, "w") as f:
                json.dump(analysis_data, f, indent=2)
        elif format == "text":
            with open(output_path, "w") as f:
                f.write("Log Analysis Report\n")
                f.write("===================\n\n")
                f.write(f"Analysis Date: {analysis_data['summary']['analysis_date']}\n")
                f.write(f"Log Directory: {analysis_data['summary']['log_directory']}\n")
                f.write(f"Total Files: {analysis_data['summary']['total_files']}\n\n")
                
                f.write("Log Files:\n")
                for file_name, file_info in analysis_data["files"].items():
                    f.write(f"- {file_name} ({file_info['type']})\n")
                    f.write(f"  Size: {file_info['size']} bytes\n")
                    f.write(f"  Last Modified: {file_info['last_modified']}\n\n")
                
                if analysis_data["errors"]:
                    f.write("Errors:\n")
                    for file_name, error_count in analysis_data["errors"].items():
                        f.write(f"- {file_name}: {error_count} errors\n")
        else:  # default: html
            with open(output_path, "w") as f:
                f.write("""<!DOCTYPE html>
<html>
<head>
    <title>Log Analysis Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1, h2, h3 { color: #333; }
        .summary { background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
        table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        .error { color: red; }
    </style>
</head>
<body>
    <h1>Log Analysis Report</h1>
    
    <div class="summary">
        <h2>Summary</h2>
        <p><strong>Analysis Date:</strong> {}</p>
        <p><strong>Log Directory:</strong> {}</p>
        <p><strong>Total Files:</strong> {}</p>
    </div>
""".format(
                    analysis_data["summary"]["analysis_date"],
                    analysis_data["summary"]["log_directory"],
                    analysis_data["summary"]["total_files"]
                ))
                
                # Add file table
                f.write("""
    <h2>Log Files</h2>
    <table>
        <tr>
            <th>File Name</th>
            <th>Type</th>
            <th>Size (bytes)</th>
            <th>Last Modified</th>
        </tr>
""")
                
                for file_name, file_info in analysis_data["files"].items():
                    f.write(f"""
        <tr>
            <td>{file_name}</td>
            <td>{file_info['type']}</td>
            <td>{file_info['size']}</td>
            <td>{file_info['last_modified']}</td>
        </tr>
""")
                
                f.write("    </table>")
                
                # Add error section if any
                if analysis_data["errors"]:
                    f.write("""
    <h2>Errors</h2>
    <table>
        <tr>
            <th>File Name</th>
            <th>Error Count</th>
        </tr>
""")
                    
                    for file_name, error_count in analysis_data["errors"].items():
                        f.write(f"""
        <tr>
            <td>{file_name}</td>
            <td class="error">{error_count}</td>
        </tr>
""")
                    
                    f.write("    </table>")
                
                # Close HTML
                f.write("""
</body>
</html>
""")
                
        cli_logger.info(f"Analysis report saved to {output_path}")
        return True
    except Exception as e:
        cli_logger.error(f"Error generating analysis report: {e}")
        return False

def visualize_logs(log_file: str, output_path: str, viz_type: str = "timeline") -> bool:
    """
    Visualize log data based on the specified type.
    
    Args:
        log_file: Log file to visualize
        output_path: Path to save the visualization
        viz_type: Type of visualization (timeline, state, report)
        
    Returns:
        True if successful, False otherwise
    """
    cli_logger.info(f"Visualizing {log_file} as {viz_type}...")
    
    # Load trace data
    trace_data = load_trace_file(log_file)
    
    if not trace_data:
        cli_logger.warning(f"No trace data found in {log_file}")
        return False
    
    # Create output directory if it doesn't exist and output_path is specified
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
    else:
        # Generate default output path
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = "logs/visualizations"
        os.makedirs(output_dir, exist_ok=True)
        
        if viz_type == "timeline":
            output_path = os.path.join(output_dir, f"timeline_{timestamp}.png")
        elif viz_type == "state":
            output_path = os.path.join(output_dir, f"state_{timestamp}.png")
        elif viz_type == "report":
            output_path = os.path.join(output_dir, f"report_{timestamp}.html")
    
    # Generate visualization based on type
    try:
        if viz_type == "timeline":
            visualize_timeline(trace_data, output_path)
            cli_logger.info(f"Timeline visualization saved to {output_path}")
        elif viz_type == "state":
            # For state visualization, we need a before and after state
            # Use the first and last trace entry states
            if len(trace_data) >= 2:
                before_state = trace_data[0].get("input_state", {})
                after_state = trace_data[-1].get("output_state", {})
                visualize_state_changes(before_state, after_state, output_path)
                cli_logger.info(f"State changes visualization saved to {output_path}")
            else:
                cli_logger.warning("Need at least two trace entries for state visualization")
                return False
        elif viz_type == "report":
            create_execution_report(trace_data, output_path)
            cli_logger.info(f"Execution report saved to {output_path}")
            
        return True
    except Exception as e:
        cli_logger.error(f"Error creating visualization: {e}")
        return False

def monitor_logs(log_file: str, interval: float = 1.0) -> None:
    """
    Monitor a log file in real-time and display updates.
    
    Args:
        log_file: Log file to monitor
        interval: Refresh interval in seconds
    """
    import time
    import curses
    
    def display_monitor(stdscr):
        # Set up curses
        curses.curs_set(0)  # Hide cursor
        stdscr.clear()
        
        # Get the window dimensions
        height, width = stdscr.getmaxyx()
        
        # Create a header window
        header = stdscr.subwin(3, width, 0, 0)
        header.box()
        header.addstr(1, 2, f"Monitoring: {log_file}")
        header.refresh()
        
        # Create a log window
        log_win = stdscr.subwin(height - 3, width, 3, 0)
        log_win.box()
        log_win.refresh()
        
        # Initialize variables
        last_position = 0
        log_lines = []
        max_lines = height - 5
        
        while True:
            try:
                # Check if the file exists
                if not os.path.exists(log_file):
                    log_win.clear()
                    log_win.box()
                    log_win.addstr(1, 2, f"Log file does not exist: {log_file}")
                    log_win.refresh()
                    time.sleep(interval)
                    continue
                
                # Read new log lines
                with open(log_file, "r") as f:
                    f.seek(last_position)
                    new_lines = f.readlines()
                    last_position = f.tell()
                
                # Add new lines to the buffer
                log_lines.extend(new_lines)
                
                # Limit the number of lines to display
                if len(log_lines) > max_lines:
                    log_lines = log_lines[-max_lines:]
                
                # Display the log lines
                log_win.clear()
                log_win.box()
                
                for i, line in enumerate(log_lines):
                    if i >= max_lines:
                        break
                    
                    # Truncate line if too long
                    if len(line) > width - 4:
                        line = line[:width - 7] + "..."
                    
                    # Format the line based on content
                    if "ERROR" in line:
                        log_win.addstr(i + 1, 2, line, curses.A_BOLD)
                    elif "WARNING" in line:
                        log_win.addstr(i + 1, 2, line)
                    else:
                        log_win.addstr(i + 1, 2, line)
                
                log_win.refresh()
                
                # Update the header with the current time
                current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                header.clear()
                header.box()
                header.addstr(1, 2, f"Monitoring: {log_file} (Last Update: {current_time})")
                header.refresh()
                
                # Sleep for the specified interval
                time.sleep(interval)
                
                # Check for key press
                key = stdscr.getch()
                if key == ord("q"):
                    break
            
            except KeyboardInterrupt:
                break
            except Exception as e:
                log_win.clear()
                log_win.box()
                log_win.addstr(1, 2, f"Error: {str(e)}")
                log_win.refresh()
                time.sleep(interval)
    
    # Start the curses application
    curses.wrapper(display_monitor)

def generate_run_summary(run_dir: str, output_path: Optional[str] = None) -> bool:
    """
    Generate a summary of a run from its log directory.
    
    Args:
        run_dir: Directory containing run data
        output_path: Path to save the summary report
        
    Returns:
        True if successful, False otherwise
    """
    cli_logger.info(f"Generating summary for run in {run_dir}...")
    
    # Check if the directory exists
    if not os.path.isdir(run_dir):
        cli_logger.error(f"Run directory does not exist: {run_dir}")
        return False
    
    # Find run data file
    run_data_file = os.path.join(run_dir, "run_data.json")
    
    if not os.path.exists(run_data_file):
        cli_logger.error(f"Run data file not found: {run_data_file}")
        return False
    
    # Load run data
    try:
        with open(run_data_file, "r") as f:
            run_data = json.load(f)
            
        # Find trace history file if available
        trace_file = os.path.join(run_dir, "trace_history.json")
        trace_data = []
        
        if os.path.exists(trace_file):
            with open(trace_file, "r") as f:
                trace_data = json.load(f)
                
        # Generate default output path if not provided
        if not output_path:
            output_dir = os.path.join(run_dir, "reports")
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, "summary.html")
            
        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Generate HTML report
        with open(output_path, "w") as f:
            f.write("""<!DOCTYPE html>
<html>
<head>
    <title>Run Summary Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1, h2, h3 { color: #333; }
        .summary { background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
        table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        .success { color: green; }
        .error { color: red; }
        .highlight { background-color: #ffffcc; }
    </style>
</head>
<body>
    <h1>Run Summary Report</h1>
    
    <div class="summary">
        <h2>Run Information</h2>
        <p><strong>Run ID:</strong> {}</p>
        <p><strong>Start Time:</strong> {}</p>
        <p><strong>End Time:</strong> {}</p>
        <p><strong>Duration:</strong> {:.4f} seconds</p>
        <p><strong>Status:</strong> <span class="{}">
          {}</span></p>
""".format(
                run_data.get("run_id", "Unknown"),
                run_data.get("start_time", "Unknown"),
                run_data.get("end_time", "Unknown"),
                run_data.get("duration", 0),
                "success" if run_data.get("success", False) else "error",
                "Successful" if run_data.get("success", False) else "Failed"
            ))
            
            # Add error details if failed
            if not run_data.get("success", False) and "error" in run_data:
                error = run_data["error"]
                f.write(f"""
        <div class="error">
            <h3>Error Details</h3>
            <p><strong>Type:</strong> {error.get('type', 'Unknown')}</p>
            <p><strong>Message:</strong> {error.get('message', 'Unknown')}</p>
        </div>
""")
            
            f.write("    </div>")
            
            # Add execution summary if available
            if "execution_summary" in run_data:
                summary = run_data["execution_summary"]
                f.write("""
    <h2>Execution Summary</h2>
    <table>
        <tr>
            <th>Metric</th>
            <th>Value</th>
        </tr>
""")
                
                # Add nodes info
                if "nodes" in summary:
                    nodes = summary["nodes"]
                    f.write(f"""
        <tr>
            <td>Total Nodes</td>
            <td>{nodes.get('total', 0)}</td>
        </tr>
        <tr>
            <td>Successful Nodes</td>
            <td class="success">{nodes.get('successful', 0)}</td>
        </tr>
        <tr>
            <td>Failed Nodes</td>
            <td class="error">{nodes.get('failed', 0)}</td>
        </tr>
""")
                
                # Add timing info
                if "timing" in summary:
                    timing = summary["timing"]
                    f.write(f"""
        <tr>
            <td>Total Duration</td>
            <td>{timing.get('total_duration', 0):.4f} seconds</td>
        </tr>
        <tr>
            <td>Average Node Duration</td>
            <td>{timing.get('average_node_duration', 0):.4f} seconds</td>
        </tr>
        <tr>
            <td>Maximum Node Duration</td>
            <td>{timing.get('maximum_node_duration', 0):.4f} seconds</td>
        </tr>
""")
                
                f.write("    </table>")
                
                # Add execution path if available
                if "execution_path" in summary:
                    path = summary["execution_path"]
                    f.write("""
    <h2>Execution Path</h2>
    <ol>
""")
                    
                    for node in path:
                        f.write(f"""
        <li>{node}</li>
""")
                    
                    f.write("    </ol>")
                
                # Add slow nodes if available
                if "slow_nodes" in summary and summary["slow_nodes"]:
                    f.write("""
    <h2>Slow Nodes</h2>
    <table>
        <tr>
            <th>Node</th>
            <th>Duration (seconds)</th>
        </tr>
""")
                    
                    for node in summary["slow_nodes"]:
                        f.write(f"""
        <tr class="highlight">
            <td>{node.get('node', 'Unknown')}</td>
            <td>{node.get('duration', 0):.4f}</td>
        </tr>
""")
                    
                    f.write("    </table>")
            
            # Add trace data visualization links if available
            if trace_data:
                f.write("""
    <h2>Visualizations</h2>
    <ul>
""")
                
                # Check for existing visualizations
                timeline_file = os.path.join(run_dir, "timeline.png")
                if os.path.exists(timeline_file):
                    rel_path = os.path.relpath(timeline_file, os.path.dirname(output_path))
                    f.write(f"""
        <li><a href="{rel_path}" target="_blank">Timeline Visualization</a></li>
""")
                
                report_file = os.path.join(run_dir, "report.html")
                if os.path.exists(report_file):
                    rel_path = os.path.relpath(report_file, os.path.dirname(output_path))
                    f.write(f"""
        <li><a href="{rel_path}" target="_blank">Execution Report</a></li>
""")
                
                f.write("    </ul>")
            
            # Close HTML
            f.write("""
</body>
</html>
""")
            
        cli_logger.info(f"Run summary saved to {output_path}")
        return True
    except Exception as e:
        cli_logger.error(f"Error generating run summary: {e}")
        return False

def main():
    """Main entry point."""
    args = parse_args()
    
    if args.command == "analyze":
        analyze_logs(args.log_dir, args.output, args.format)
    elif args.command == "visualize":
        visualize_logs(args.log_file, args.output, args.type)
    elif args.command == "monitor":
        monitor_logs(args.log_file, args.interval)
    elif args.command == "summary":
        generate_run_summary(args.run_dir, args.output)
    else:
        cli_logger.info("No command specified. Use --help for usage information.")

if __name__ == "__main__":
    main() 