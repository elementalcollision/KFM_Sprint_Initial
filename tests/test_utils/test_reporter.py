import os
import json
import time
import datetime
from typing import Dict, Any, List, Optional, Union
import matplotlib.pyplot as plt
import numpy as np

"""
KFM Rule Test Reporter

This module provides utilities for generating detailed reports and visualizations
for KFM rule condition tests. It is designed to be used with the end-to-end tests
in test_e2e_kfm_rules.py.

The TestReporter class handles:
1. Collection of test results with detailed metadata
2. Generation of summary reports with statistics
3. Creation of visualizations (charts and graphs)
4. Integration with CI systems through standardized reports

Key Features:
- JSON-based reports for machine readability
- Timestamps for tracking test runs over time
- Categorization of tests for better organization
- Visualization tools for quick analysis
- CI-friendly reporting for integration with CI/CD pipelines

Usage:
    # Create a reporter
    reporter = create_test_reporter(output_dir='my_reports')
    
    # Add test results
    reporter.add_test_result(
        test_name='test_1',
        status=True,  # Passed
        details={'action': 'kill', 'component': 'component_a'},
        duration=1.5,
        logs="Log output...",
        category="kill"
    )
    
    # Generate reports
    reporter.save_summary_report()
    reporter.save_test_results()
    reporter.generate_visualization()
    
    # For CI integration
    reporter.save_ci_report()

For detailed documentation on the test suite and test cases, see:
docs/testing/kfm_rule_tests.md
"""

class TestReporter:
    """
    Generates detailed reports for KFM rule condition tests.
    
    This class provides utilities for:
    1. Creating individual test result reports
    2. Generating summary reports across multiple test runs
    3. Creating visualizations of test results
    4. Integrating with CI systems
    
    Test results are saved in JSON format with timestamps for easy tracking
    and analysis.
    """
    
    def __init__(self, output_dir: str = 'test_reports'):
        """
        Initialize the TestReporter.
        
        Args:
            output_dir: Directory where test reports will be saved
        """
        self.output_dir = output_dir
        self.test_results = []
        os.makedirs(output_dir, exist_ok=True)
        
        # Initialize CI integration stats
        self.ci_stats = {
            'total_tests': 0,
            'passed_tests': 0,
            'failed_tests': 0,
            'total_duration': 0,
            'start_time': time.time(),
            'test_categories': {}
        }
    
    def add_test_result(self, test_name: str, status: bool, details: Dict[str, Any], 
                         duration: float, logs: str = "", category: str = "uncategorized") -> None:
        """
        Add a test result to the report.
        
        Args:
            test_name: Name of the test
            status: True if test passed, False if failed
            details: Dict containing test details and results
            duration: Test execution time in seconds
            logs: Log output from the test
            category: Category of the test (e.g., "kill", "marry", "no_action")
        """
        timestamp = time.time()
        
        result = {
            'name': test_name,
            'status': 'PASS' if status else 'FAIL',
            'duration': duration,
            'timestamp': timestamp,
            'timestamp_iso': datetime.datetime.fromtimestamp(timestamp).isoformat(),
            'details': details,
            'logs': logs,
            'category': category
        }
        
        self.test_results.append(result)
        
        # Update CI stats
        self.ci_stats['total_tests'] += 1
        if status:
            self.ci_stats['passed_tests'] += 1
        else:
            self.ci_stats['failed_tests'] += 1
        self.ci_stats['total_duration'] += duration
        
        # Update category stats
        if category not in self.ci_stats['test_categories']:
            self.ci_stats['test_categories'][category] = {
                'total': 0, 'passed': 0, 'failed': 0, 'duration': 0
            }
        
        cat_stats = self.ci_stats['test_categories'][category]
        cat_stats['total'] += 1
        if status:
            cat_stats['passed'] += 1
        else:
            cat_stats['failed'] += 1
        cat_stats['duration'] += duration
    
    def generate_summary_report(self) -> Dict[str, Any]:
        """
        Generate a summary report of all test results.
        
        Returns:
            Dict containing summary statistics
        """
        if not self.test_results:
            return {'error': 'No test results available'}
        
        # Calculate summary stats
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r['status'] == 'PASS')
        failed_tests = total_tests - passed_tests
        total_duration = sum(r['duration'] for r in self.test_results)
        
        # Categorize tests
        categories = {}
        for result in self.test_results:
            category = result.get('category', 'uncategorized')
            if category not in categories:
                categories[category] = {'total': 0, 'passed': 0, 'failed': 0, 'duration': 0}
            
            cat_stats = categories[category]
            cat_stats['total'] += 1
            if result['status'] == 'PASS':
                cat_stats['passed'] += 1
            else:
                cat_stats['failed'] += 1
            cat_stats['duration'] += result['duration']
        
        summary = {
            'timestamp': time.time(),
            'timestamp_iso': datetime.datetime.now().isoformat(),
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': failed_tests,
            'pass_rate': passed_tests / total_tests if total_tests > 0 else 0,
            'total_duration': total_duration,
            'average_duration': total_duration / total_tests if total_tests > 0 else 0,
            'categories': categories
        }
        
        return summary
    
    def save_summary_report(self, filename: Optional[str] = None) -> str:
        """
        Save the summary report to a file.
        
        Args:
            filename: Name of the file to save the report to
                     If None, a default name with timestamp will be used
        
        Returns:
            Path to the saved report file
        """
        summary = self.generate_summary_report()
        
        if filename is None:
            timestamp = int(time.time())
            filename = f"test_summary_{timestamp}.json"
        
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(summary, f, indent=2)
        
        return filepath
    
    def save_test_results(self, filename: Optional[str] = None) -> str:
        """
        Save all test results to a file.
        
        Args:
            filename: Name of the file to save the results to
                     If None, a default name with timestamp will be used
        
        Returns:
            Path to the saved results file
        """
        if not self.test_results:
            return ""
        
        if filename is None:
            timestamp = int(time.time())
            filename = f"test_results_{timestamp}.json"
        
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(self.test_results, f, indent=2)
        
        return filepath
    
    def generate_visualization(self, filename: Optional[str] = None) -> str:
        """
        Generate a visualization of test results.
        
        Args:
            filename: Name of the file to save the visualization to
                     If None, a default name with timestamp will be used
        
        Returns:
            Path to the saved visualization file
        """
        if not self.test_results:
            return ""
        
        if filename is None:
            timestamp = int(time.time())
            filename = f"test_visualization_{timestamp}.png"
        
        filepath = os.path.join(self.output_dir, filename)
        
        # Create a figure with 2 subplots
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 7))
        
        # Prepare data for the first subplot (pass/fail by category)
        categories = {}
        for result in self.test_results:
            category = result.get('category', 'uncategorized')
            if category not in categories:
                categories[category] = {'passed': 0, 'failed': 0}
            
            if result['status'] == 'PASS':
                categories[category]['passed'] += 1
            else:
                categories[category]['failed'] += 1
        
        # Plot pass/fail by category
        category_names = list(categories.keys())
        passed_counts = [categories[cat]['passed'] for cat in category_names]
        failed_counts = [categories[cat]['failed'] for cat in category_names]
        
        x = np.arange(len(category_names))
        width = 0.35
        
        ax1.bar(x - width/2, passed_counts, width, label='Passed', color='green')
        ax1.bar(x + width/2, failed_counts, width, label='Failed', color='red')
        
        ax1.set_xlabel('Category')
        ax1.set_ylabel('Count')
        ax1.set_title('Test Results by Category')
        ax1.set_xticks(x)
        ax1.set_xticklabels(category_names)
        ax1.legend()
        
        # Prepare data for the second subplot (execution time by category)
        durations = {}
        for result in self.test_results:
            category = result.get('category', 'uncategorized')
            if category not in durations:
                durations[category] = []
            
            durations[category].append(result['duration'])
        
        # Plot execution time by category
        category_names = list(durations.keys())
        avg_durations = [sum(durations[cat]) / len(durations[cat]) for cat in category_names]
        
        ax2.bar(category_names, avg_durations, color='blue')
        ax2.set_xlabel('Category')
        ax2.set_ylabel('Average Execution Time (s)')
        ax2.set_title('Average Execution Time by Category')
        
        plt.tight_layout()
        plt.savefig(filepath)
        plt.close()
        
        return filepath
    
    def generate_ci_report(self) -> Dict[str, Any]:
        """
        Generate a report suitable for CI integration.
        
        Returns:
            Dict containing CI-friendly summary statistics
        """
        self.ci_stats['end_time'] = time.time()
        self.ci_stats['total_duration'] = self.ci_stats['end_time'] - self.ci_stats['start_time']
        
        # Add pass rate and overall status
        pass_rate = (self.ci_stats['passed_tests'] / self.ci_stats['total_tests'] 
                     if self.ci_stats['total_tests'] > 0 else 0)
        self.ci_stats['pass_rate'] = pass_rate
        self.ci_stats['status'] = 'PASS' if pass_rate == 1.0 else 'FAIL'
        
        # Add timestamp
        self.ci_stats['timestamp'] = time.time()
        self.ci_stats['timestamp_iso'] = datetime.datetime.now().isoformat()
        
        return self.ci_stats
    
    def save_ci_report(self, filename: Optional[str] = None) -> str:
        """
        Save the CI report to a file.
        
        Args:
            filename: Name of the file to save the report to
                     If None, a default name will be used
        
        Returns:
            Path to the saved report file
        """
        ci_report = self.generate_ci_report()
        
        if filename is None:
            filename = "ci_report.json"
        
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(ci_report, f, indent=2)
        
        return filepath
    
    def clear_results(self) -> None:
        """Clear all test results."""
        self.test_results = []
        
        # Reset CI stats
        self.ci_stats = {
            'total_tests': 0,
            'passed_tests': 0,
            'failed_tests': 0,
            'total_duration': 0,
            'start_time': time.time(),
            'test_categories': {}
        }


def create_test_reporter(output_dir: str = None) -> TestReporter:
    """
    Factory function to create a TestReporter instance.
    
    Args:
        output_dir: Directory where test reports will be saved
    
    Returns:
        TestReporter instance
    """
    # Use default output directory if none provided
    if output_dir is None:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
        output_dir = os.path.join(project_root, "test_reports", "kfm_rule_tests")
    
    # Create the output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    return TestReporter(output_dir) 