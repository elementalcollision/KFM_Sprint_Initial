"""Test script for error display in print_execution_summary."""

import sys
import os
import traceback

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.langgraph_nodes import format_error_info, print_execution_summary

def main():
    """Test the error display functionality."""
    try:
        # Generate a test error
        raise ValueError('Test error for display')
    except Exception as e:
        # Format the error with traceback
        error_json = format_error_info(
            error_type='ValueError',
            message=str(e),
            component='test_component',
            category='Test error category',
            traceback_info=traceback.format_exc(),
            recoverable=False
        )
        
        # Create a mock state
        state = {
            'task_name': 'test_task',
            'kfm_action': {'action': 'test', 'component': 'test_component'},
            'error': error_json
        }
        
        # Display error summary
        print("\nTesting error display with traceback:\n")
        print_execution_summary(state)
        
        print("\n\nOriginal error JSON for reference:")
        print(error_json)

if __name__ == "__main__":
    main() 