#!/usr/bin/env python3
"""
Script to run all end-to-end tests for the KFM Application
and generate a comprehensive verification report.
"""

import sys
import os
import time
import json
from datetime import datetime

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.kfm_agent import create_kfm_agent_graph
from src.logger import setup_logger
from tests.test_e2e_reflection import run_e2e_test
from src.verification_utils import verify_e2e_test_results, verify_specific_test_case

# Setup logger
logger = setup_logger('E2ETestRunner')

def generate_test_report(results, output_path=None):
    """
    Generate a JSON report of all test results.
    
    Args:
        results (dict): Dictionary containing test results
        output_path (str, optional): Path to save the report to
        
    Returns:
        str: Path to the saved report
    """
    # Create report directory if it doesn't exist
    report_dir = os.path.join(project_root, 'reports')
    os.makedirs(report_dir, exist_ok=True)
    
    # Generate report filename with timestamp if not provided
    if not output_path:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = os.path.join(report_dir, f'e2e_test_report_{timestamp}.json')
    
    # Add timestamp to report
    results['timestamp'] = datetime.now().isoformat()
    results['summary'] = {
        'total_tests': len(results['tests']),
        'passed': sum(1 for test in results['tests'].values() if test.get('success')),
        'failed': sum(1 for test in results['tests'].values() if not test.get('success')),
        'error': sum(1 for test in results['tests'].values() if 'error' in test.get('verification_results', {}))
    }
    
    # Write report to file
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"Test report saved to: {output_path}")
    return output_path

def run_all_e2e_tests():
    """
    Run all end-to-end tests and generate a report.
    
    Returns:
        dict: Test report
    """
    logger.info("Starting end-to-end test suite")
    
    # Create KFM app for testing
    logger.info("Creating KFM application...")
    kfm_app, components = create_kfm_agent_graph()
    logger.info("KFM application created successfully")
    
    # Test results dictionary
    results = {
        'tests': {},
        'overall_success': True,
        'duration': 0
    }
    
    # Track start time
    start_time = time.time()
    
    # Define test cases
    test_cases = [
        {
            'name': 'Kill Decision Test',
            'initial_state': {
                'task_name': 'kill_test',
                'kfm_action': {'action': 'Kill', 'component': 'analyze_fast'},
                'active_component': 'analyze_fast',
                'result': {'type': 'fast_analysis'},
                'execution_performance': {'latency': 0.2, 'accuracy': 0.3}
            },
            'expected_values': {
                'expected_kfm_action': 'Kill',
                'expected_active_component': 'analyze_fast',
                'expected_result_type': 'fast_analysis',
                'expected_reflection_count': 1
            }
        },
        {
            'name': 'Marry Decision Test',
            'initial_state': {
                'task_name': 'marry_test',
                'kfm_action': {'action': 'Marry', 'component': 'analyze_deep'},
                'active_component': 'analyze_deep',
                'result': {'type': 'deep_analysis'},
                'execution_performance': {'latency': 1.5, 'accuracy': 0.9}
            },
            'expected_values': {
                'expected_kfm_action': 'Marry',
                'expected_active_component': 'analyze_deep',
                'expected_result_type': 'deep_analysis',
                'expected_reflection_count': 1
            }
        },
        {
            'name': 'Default Component Test',
            'initial_state': {
                'task_name': 'default_test',
                'kfm_action': {'action': 'Kill', 'component': 'analyze_balanced'},
                'active_component': 'analyze_balanced',
                'result': {'type': 'balanced_analysis'},
                'execution_performance': {'latency': 0.8, 'accuracy': 0.7}
            },
            'expected_values': {
                'expected_kfm_action': 'Kill',
                'expected_active_component': 'analyze_balanced',
                'expected_result_type': 'balanced_analysis',
                'expected_reflection_count': 1
            }
        }
    ]
    
    # Patch the LLM call for tests
    import unittest.mock
    with unittest.mock.patch('src.langgraph_nodes.call_llm_for_reflection', 
                            return_value="This is a mock reflection for testing"):
        # Run each test case
        for test_case in test_cases:
            logger.info(f"Running test: {test_case['name']}")
            
            # Run the test
            success, final_state, verification_results = run_e2e_test(
                kfm_app, 
                test_case['name'], 
                test_case['initial_state'], 
                test_case.get('expected_values')
            )
            
            # Store test results
            results['tests'][test_case['name']] = {
                'success': success,
                'verification_results': verification_results,
                'has_final_state': final_state is not None
            }
            
            # Update overall success
            if not success:
                results['overall_success'] = False
    
    # Calculate duration
    results['duration'] = time.time() - start_time
    
    # Generate report
    report_path = generate_test_report(results)
    
    # Print summary
    summary = results['summary'] if 'summary' in results else {
        'total_tests': len(results['tests']),
        'passed': sum(1 for test in results['tests'].values() if test.get('success')),
        'failed': sum(1 for test in results['tests'].values() if not test.get('success'))
    }
    
    logger.info("-" * 50)
    logger.info("TEST SUMMARY:")
    logger.info(f"Total tests: {summary['total_tests']}")
    logger.info(f"Passed: {summary['passed']}")
    logger.info(f"Failed: {summary['failed']}")
    if 'error' in summary:
        logger.info(f"Errors: {summary['error']}")
    logger.info(f"Duration: {results['duration']:.2f} seconds")
    logger.info(f"Overall success: {'✅ PASSED' if results['overall_success'] else '❌ FAILED'}")
    logger.info(f"Detailed report: {report_path}")
    logger.info("-" * 50)
    
    return results

if __name__ == "__main__":
    run_all_e2e_tests() 