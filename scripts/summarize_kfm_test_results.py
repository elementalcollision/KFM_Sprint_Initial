#!/usr/bin/env python3
"""
KFM Test Results Summarizer

This script generates a human-readable summary of KFM rule condition test results,
combining data from multiple test runs and providing insights into test coverage,
pass rates, and performance trends.
"""

import os
import sys
import json
import glob
import argparse
import datetime
from typing import Dict, List, Any, Optional
import matplotlib.pyplot as plt
import numpy as np

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Summarize KFM test results')
    
    parser.add_argument(
        '--report-dir',
        type=str,
        default=os.path.join(project_root, 'test_reports', 'kfm_rules'),
        help='Directory containing test reports'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        default='test_summary.md',
        help='Output file for the summary report (markdown format)'
    )
    
    parser.add_argument(
        '--last-n',
        type=int,
        default=5,
        help='Include only the last N test runs in the summary'
    )

    parser.add_argument(
        '--html',
        action='store_true',
        help='Generate HTML output instead of markdown'
    )
    
    return parser.parse_args()

def find_test_reports(report_dir: str, last_n: int = 5) -> List[str]:
    """
    Find test report files in the specified directory.
    
    Args:
        report_dir: Directory containing test reports
        last_n: Include only the last N test runs
        
    Returns:
        List of paths to test report files
    """
    # Find all test_results_*.json files
    report_files = glob.glob(os.path.join(report_dir, 'test_results_*.json'))
    
    # Sort by modification time (newest first)
    report_files.sort(key=os.path.getmtime, reverse=True)
    
    # Limit to last N
    return report_files[:last_n]

def load_report(file_path: str) -> Dict[str, Any]:
    """Load a test report file."""
    with open(file_path, 'r') as f:
        return json.load(f)

def extract_summary_stats(reports: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract summary statistics from test reports."""
    if not reports:
        return {}
    
    # Initialize summary stats
    summary = {
        'total_tests': 0,
        'passed_tests': 0,
        'failed_tests': 0,
        'total_duration': 0,
        'categories': {
            'kill': {'total': 0, 'passed': 0, 'failed': 0, 'duration': 0},
            'marry': {'total': 0, 'passed': 0, 'failed': 0, 'duration': 0},
            'no_action': {'total': 0, 'passed': 0, 'failed': 0, 'duration': 0},
        },
        'test_cases': {}
    }
    
    # Process each report
    for report in reports:
        for result in report:
            # Skip if not a test result (e.g., summary)
            if not isinstance(result, dict) or 'name' not in result:
                continue
                
            test_name = result['name']
            status = result.get('status', 'UNKNOWN')
            duration = result.get('duration', 0)
            category = result.get('category', 'uncategorized').lower()
            
            # Update overall stats
            summary['total_tests'] += 1
            if status == 'PASS':
                summary['passed_tests'] += 1
            else:
                summary['failed_tests'] += 1
            summary['total_duration'] += duration
            
            # Update category stats
            if category in summary['categories']:
                cat_stats = summary['categories'][category]
                cat_stats['total'] += 1
                if status == 'PASS':
                    cat_stats['passed'] += 1
                else:
                    cat_stats['failed'] += 1
                cat_stats['duration'] += duration
            
            # Track individual test cases
            if test_name not in summary['test_cases']:
                summary['test_cases'][test_name] = {
                    'runs': 0,
                    'passed': 0,
                    'failed': 0,
                    'avg_duration': 0,
                    'category': category
                }
            
            test_stats = summary['test_cases'][test_name]
            test_stats['runs'] += 1
            if status == 'PASS':
                test_stats['passed'] += 1
            else:
                test_stats['failed'] += 1
                
            # Update average duration
            total_dur = test_stats['avg_duration'] * (test_stats['runs'] - 1) + duration
            test_stats['avg_duration'] = total_dur / test_stats['runs']
    
    # Calculate pass rates
    if summary['total_tests'] > 0:
        summary['pass_rate'] = summary['passed_tests'] / summary['total_tests']
    else:
        summary['pass_rate'] = 0
        
    for category, stats in summary['categories'].items():
        if stats['total'] > 0:
            stats['pass_rate'] = stats['passed'] / stats['total']
        else:
            stats['pass_rate'] = 0
            
    for test_name, stats in summary['test_cases'].items():
        if stats['runs'] > 0:
            stats['pass_rate'] = stats['passed'] / stats['runs']
        else:
            stats['pass_rate'] = 0
    
    return summary

def generate_markdown_summary(summary: Dict[str, Any], report_files: List[str]) -> str:
    """Generate a markdown summary report."""
    if not summary:
        return "No test reports found."
    
    # Convert timestamp to readable format
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Build the markdown report
    lines = [
        "# KFM Rule Condition Test Summary",
        "",
        f"Generated: {timestamp}",
        "",
        f"This summary includes data from the last {len(report_files)} test runs.",
        "",
        "## Overall Statistics",
        "",
        f"- **Total Tests**: {summary['total_tests']}",
        f"- **Passed**: {summary['passed_tests']} ({summary['pass_rate']:.1%})",
        f"- **Failed**: {summary['failed_tests']} ({1 - summary['pass_rate']:.1%})",
        f"- **Total Duration**: {summary['total_duration']:.2f} seconds",
        "",
        "## Category Statistics",
        "",
        "| Category | Tests | Passed | Failed | Pass Rate | Avg Duration |",
        "|----------|-------|--------|--------|-----------|--------------|",
    ]
    
    # Add category stats
    for category, stats in summary['categories'].items():
        if stats['total'] > 0:
            avg_duration = stats['duration'] / stats['total'] if stats['total'] > 0 else 0
            lines.append(
                f"| {category.title()} | {stats['total']} | {stats['passed']} | {stats['failed']} "
                f"| {stats['pass_rate']:.1%} | {avg_duration:.2f}s |"
            )
    
    # Add individual test case stats
    lines.extend([
        "",
        "## Test Case Details",
        "",
        "| Test | Category | Runs | Pass Rate | Avg Duration |",
        "|------|----------|------|-----------|--------------|",
    ])
    
    # Group test cases by category
    for category in ['kill', 'marry', 'no_action']:
        for test_name, stats in summary['test_cases'].items():
            if stats['category'] == category:
                lines.append(
                    f"| {test_name} | {category.title()} | {stats['runs']} | "
                    f"{stats['pass_rate']:.1%} | {stats['avg_duration']:.2f}s |"
                )
    
    # Add report file details
    lines.extend([
        "",
        "## Included Reports",
        "",
    ])
    
    for i, file_path in enumerate(report_files):
        file_name = os.path.basename(file_path)
        timestamp = datetime.datetime.fromtimestamp(os.path.getmtime(file_path)).strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"{i+1}. {file_name} (Generated: {timestamp})")
    
    return "\n".join(lines)

def generate_html_summary(summary: Dict[str, Any], report_files: List[str]) -> str:
    """Generate an HTML summary report."""
    if not summary:
        return "<html><body><h1>No test reports found.</h1></body></html>"
    
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Create HTML report
    html = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        "    <title>KFM Rule Condition Test Summary</title>",
        "    <style>",
        "        body { font-family: Arial, sans-serif; margin: 20px; }",
        "        table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }",
        "        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }",
        "        th { background-color: #f2f2f2; }",
        "        tr:nth-child(even) { background-color: #f9f9f9; }",
        "        .pass-rate-good { color: green; }",
        "        .pass-rate-medium { color: orange; }",
        "        .pass-rate-bad { color: red; }",
        "        .summary-box { background-color: #f0f0f0; border-radius: 5px; padding: 15px; margin-bottom: 20px; }",
        "    </style>",
        "</head>",
        "<body>",
        f"    <h1>KFM Rule Condition Test Summary</h1>",
        f"    <p>Generated: {timestamp}</p>",
        f"    <p>This summary includes data from the last {len(report_files)} test runs.</p>",
        "    <div class='summary-box'>",
        "        <h2>Overall Statistics</h2>",
        f"        <p><b>Total Tests:</b> {summary['total_tests']}</p>",
        f"        <p><b>Passed:</b> {summary['passed_tests']} ({summary['pass_rate']:.1%})</p>",
        f"        <p><b>Failed:</b> {summary['failed_tests']} ({1 - summary['pass_rate']:.1%})</p>",
        f"        <p><b>Total Duration:</b> {summary['total_duration']:.2f} seconds</p>",
        "    </div>",
        "    <h2>Category Statistics</h2>",
        "    <table>",
        "        <tr>",
        "            <th>Category</th>",
        "            <th>Tests</th>",
        "            <th>Passed</th>",
        "            <th>Failed</th>",
        "            <th>Pass Rate</th>",
        "            <th>Avg Duration</th>",
        "        </tr>",
    ]
    
    # Add category stats
    for category, stats in summary['categories'].items():
        if stats['total'] > 0:
            avg_duration = stats['duration'] / stats['total'] if stats['total'] > 0 else 0
            pass_rate_class = ""
            if stats['pass_rate'] >= 0.9:
                pass_rate_class = "pass-rate-good"
            elif stats['pass_rate'] >= 0.7:
                pass_rate_class = "pass-rate-medium"
            else:
                pass_rate_class = "pass-rate-bad"
                
            html.append("        <tr>")
            html.append(f"            <td>{category.title()}</td>")
            html.append(f"            <td>{stats['total']}</td>")
            html.append(f"            <td>{stats['passed']}</td>")
            html.append(f"            <td>{stats['failed']}</td>")
            html.append(f"            <td class='{pass_rate_class}'>{stats['pass_rate']:.1%}</td>")
            html.append(f"            <td>{avg_duration:.2f}s</td>")
            html.append("        </tr>")
    
    # Add individual test case stats
    html.extend([
        "    </table>",
        "    <h2>Test Case Details</h2>",
        "    <table>",
        "        <tr>",
        "            <th>Test</th>",
        "            <th>Category</th>",
        "            <th>Runs</th>",
        "            <th>Pass Rate</th>",
        "            <th>Avg Duration</th>",
        "        </tr>",
    ])
    
    # Group test cases by category
    for category in ['kill', 'marry', 'no_action']:
        for test_name, stats in summary['test_cases'].items():
            if stats['category'] == category:
                pass_rate_class = ""
                if stats['pass_rate'] >= 0.9:
                    pass_rate_class = "pass-rate-good"
                elif stats['pass_rate'] >= 0.7:
                    pass_rate_class = "pass-rate-medium"
                else:
                    pass_rate_class = "pass-rate-bad"
                    
                html.append("        <tr>")
                html.append(f"            <td>{test_name}</td>")
                html.append(f"            <td>{category.title()}</td>")
                html.append(f"            <td>{stats['runs']}</td>")
                html.append(f"            <td class='{pass_rate_class}'>{stats['pass_rate']:.1%}</td>")
                html.append(f"            <td>{stats['avg_duration']:.2f}s</td>")
                html.append("        </tr>")
    
    # Add report file details
    html.extend([
        "    </table>",
        "    <h2>Included Reports</h2>",
        "    <ul>",
    ])
    
    for i, file_path in enumerate(report_files):
        file_name = os.path.basename(file_path)
        timestamp = datetime.datetime.fromtimestamp(os.path.getmtime(file_path)).strftime("%Y-%m-%d %H:%M:%S")
        html.append(f"        <li>{file_name} (Generated: {timestamp})</li>")
    
    html.extend([
        "    </ul>",
        "</body>",
        "</html>",
    ])
    
    return "\n".join(html)

def generate_summary_visualizations(summary: Dict[str, Any], output_dir: str) -> None:
    """Generate summary visualizations."""
    if not summary or summary['total_tests'] == 0:
        return
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Create a figure with 2 subplots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 7))
    
    # Plot pass/fail by category
    categories = ['Kill', 'Marry', 'No Action']
    passed = [summary['categories']['kill']['passed'], summary['categories']['marry']['passed'], 
              summary['categories']['no_action']['passed']]
    failed = [summary['categories']['kill']['failed'], summary['categories']['marry']['failed'], 
              summary['categories']['no_action']['failed']]
    
    x = np.arange(len(categories))
    width = 0.35
    
    ax1.bar(x - width/2, passed, width, label='Passed', color='green')
    ax1.bar(x + width/2, failed, width, label='Failed', color='red')
    
    ax1.set_xlabel('Category')
    ax1.set_ylabel('Count')
    ax1.set_title('Test Results by Category')
    ax1.set_xticks(x)
    ax1.set_xticklabels(categories)
    ax1.legend()
    
    # Plot average duration by category
    avg_durations = []
    for category in ['kill', 'marry', 'no_action']:
        stats = summary['categories'][category]
        avg_dur = stats['duration'] / stats['total'] if stats['total'] > 0 else 0
        avg_durations.append(avg_dur)
    
    ax2.bar(categories, avg_durations, color='blue')
    ax2.set_xlabel('Category')
    ax2.set_ylabel('Average Duration (s)')
    ax2.set_title('Average Execution Time by Category')
    
    plt.tight_layout()
    
    # Save the figure
    timestamp = int(datetime.datetime.now().timestamp())
    plt.savefig(os.path.join(output_dir, f"summary_viz_{timestamp}.png"))
    plt.close()

def main():
    """Run the KFM test results summarizer."""
    args = parse_args()
    
    # Find test report files
    report_files = find_test_reports(args.report_dir, args.last_n)
    
    if not report_files:
        print(f"No test reports found in {args.report_dir}")
        return
    
    # Load reports
    reports = [load_report(file) for file in report_files]
    
    # Extract summary stats
    summary = extract_summary_stats(reports)
    
    # Generate visualizations
    generate_summary_visualizations(summary, args.report_dir)
    
    # Generate summary report
    if args.html:
        output = generate_html_summary(summary, report_files)
        output_file = args.output if args.output.endswith('.html') else args.output + '.html'
    else:
        output = generate_markdown_summary(summary, report_files)
        output_file = args.output if args.output.endswith('.md') else args.output + '.md'
    
    # Save summary report
    with open(os.path.join(args.report_dir, output_file), 'w') as f:
        f.write(output)
    
    print(f"Summary report generated: {os.path.join(args.report_dir, output_file)}")

if __name__ == "__main__":
    main() 