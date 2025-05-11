#!/usr/bin/env python3
"""
KFM Rule Condition Test Runner

This script runs all the KFM rule condition tests and generates comprehensive
reports and visualizations. It can be used in CI environments to validate
that the KFM agent correctly applies "Kill", "Marry", and "No Action" rules
based on component performance metrics.
"""

import sys
import os
import unittest
import argparse
import datetime
import json
import subprocess

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from tests.test_e2e_kfm_rules import TestKillActionScenarios, TestMarryActionScenarios, TestNoActionScenarios
from tests.test_utils.test_reporter import create_test_reporter

"""
KFM Rule Condition Test Runner - Command Line Interface

This script provides a command-line interface for running the KFM rule condition
end-to-end tests. It allows users to selectively run specific test categories,
generate visualizations, and run in CI mode.

Test Categories:
- Kill Action: Tests the KFM agent's ability to identify and remove underperforming components
- Marry Action: Tests the KFM agent's ability to identify and exclusively use excellent components
- No Action: Tests the KFM agent's ability to determine when no action is needed

Features:
- Selective test execution by category
- Detailed test reporting with timestamps
- Visualization generation for easy analysis
- CI integration for automated testing
- Summary report generation with statistics

Command Line Options:
--output-dir PATH    Directory to save test reports (default: test_reports/kfm_rules)
--ci-mode            Run in CI mode, generating CI-friendly reports
--test-category CAT  Which test category to run (kill, marry, no_action, all)
--visualize          Generate visualizations of test results

Example Usage:
python run_kfm_rule_tests.py                             # Run all tests
python run_kfm_rule_tests.py --test-category kill        # Run only Kill tests
python run_kfm_rule_tests.py --visualize                 # Run all tests with visualizations
python run_kfm_rule_tests.py --ci-mode                   # Run in CI mode

For detailed documentation on the test suite and test cases, see:
../docs/testing/kfm_rule_tests.md
"""

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Run KFM rule condition tests')
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default=os.path.join(project_root, 'test_reports', 'kfm_rules'),
        help='Directory to save test reports and visualizations'
    )
    
    parser.add_argument(
        '--ci-mode',
        action='store_true',
        help='Run in CI mode, which generates a CI-friendly report'
    )
    
    parser.add_argument(
        '--test-category',
        type=str,
        choices=['kill', 'marry', 'no_action', 'all'],
        default='all',
        help='Which test category to run'
    )
    
    parser.add_argument(
        '--visualize',
        action='store_true',
        help='Generate visualizations of test results'
    )
    
    parser.add_argument(
        '--summarize',
        action='store_true',
        help='Generate a summary report of test results'
    )
    
    parser.add_argument(
        '--html-summary',
        action='store_true',
        help='Generate an HTML summary report instead of markdown'
    )
    
    parser.add_argument(
        '--last-n',
        type=int,
        default=5,
        help='Include only the last N test runs in the summary'
    )
    
    return parser.parse_args()


def get_test_suite(test_category):
    """
    Create a test suite based on the specified category.
    
    Args:
        test_category: Category of tests to run ('kill', 'marry', 'no_action', or 'all')
        
    Returns:
        unittest.TestSuite: Suite of tests to run
    """
    suite = unittest.TestSuite()
    
    if test_category in ['kill', 'all']:
        suite.addTest(unittest.makeSuite(TestKillActionScenarios))
    
    if test_category in ['marry', 'all']:
        suite.addTest(unittest.makeSuite(TestMarryActionScenarios))
    
    if test_category in ['no_action', 'all']:
        suite.addTest(unittest.makeSuite(TestNoActionScenarios))
    
    return suite


def run_tests(test_suite, output_dir, ci_mode=False, visualize=False):
    """
    Run the test suite and generate reports.
    
    Args:
        test_suite: unittest.TestSuite instance
        output_dir: Directory to save reports
        ci_mode: Whether to run in CI mode
        visualize: Whether to generate visualizations
        
    Returns:
        bool: True if all tests passed, False otherwise
    """
    # Create test reporter
    reporter = create_test_reporter(output_dir)
    
    # Create test runner
    runner = unittest.TextTestRunner(verbosity=2)
    
    # Run tests and capture results
    start_time = datetime.datetime.now()
    result = runner.run(test_suite)
    end_time = datetime.datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # Process test results
    all_tests_passed = result.wasSuccessful()
    test_count = result.testsRun
    error_count = len(result.errors)
    failure_count = len(result.failures)
    
    # Add results to the reporter
    test_details = {
        'test_count': test_count,
        'errors': error_count,
        'failures': failure_count,
        'all_passed': all_tests_passed
    }
    
    reporter.add_test_result(
        test_name='KFM Rule Conditions',
        status=all_tests_passed,
        details=test_details,
        duration=duration,
        category='all'
    )
    
    # Generate reports
    summary_report_path = reporter.save_summary_report()
    results_path = reporter.save_test_results()
    
    print(f"\nTest Summary Report saved to: {summary_report_path}")
    print(f"Detailed Test Results saved to: {results_path}")
    
    if ci_mode:
        ci_report_path = reporter.save_ci_report()
        print(f"CI Report saved to: {ci_report_path}")
    
    if visualize:
        viz_path = reporter.generate_visualization()
        print(f"Test Visualization saved to: {viz_path}")
    
    # Print summary to console
    print("\n--- TEST SUMMARY ---")
    print(f"Tests Run: {test_count}")
    print(f"Errors: {error_count}")
    print(f"Failures: {failure_count}")
    print(f"Duration: {duration:.2f} seconds")
    print(f"All Tests Passed: {all_tests_passed}")
    
    return all_tests_passed


def generate_summary_report(output_dir, last_n=5, html=False):
    """
    Generate a summary report of test results.
    
    Args:
        output_dir: Directory containing test reports
        last_n: Include only the last N test runs
        html: Whether to generate HTML output instead of markdown
    """
    # Build the command to run the summarizer script
    cmd = [
        sys.executable,
        os.path.join(project_root, 'scripts', 'summarize_kfm_test_results.py'),
        f'--report-dir={output_dir}',
        f'--last-n={last_n}'
    ]
    
    if html:
        cmd.append('--html')
    
    # Run the summarizer script
    try:
        subprocess.run(cmd, check=True)
        print(f"\nSummary report generated in: {output_dir}")
    except subprocess.CalledProcessError as e:
        print(f"Error generating summary report: {e}")


def main():
    """Run the test suite and generate reports."""
    args = parse_args()
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Get test suite
    test_suite = get_test_suite(args.test_category)
    
    # Run tests
    all_passed = run_tests(
        test_suite=test_suite,
        output_dir=args.output_dir,
        ci_mode=args.ci_mode,
        visualize=args.visualize
    )
    
    # Generate summary report if requested
    if args.summarize:
        generate_summary_report(
            output_dir=args.output_dir,
            last_n=args.last_n,
            html=args.html_summary
        )
    
    # Exit with appropriate status code for CI
    sys.exit(0 if all_passed else 1)


if __name__ == '__main__':
    main() 