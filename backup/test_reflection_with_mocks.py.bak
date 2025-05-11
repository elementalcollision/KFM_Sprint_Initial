#!/usr/bin/env python3

"""
Test script for validating the call_llm_for_reflection function using mocks to avoid real API calls.
This script tests various scenarios including successful calls and error cases.
"""

import logging
from test_reflection_mock import mock_call_llm_for_reflection, mock_error_case

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MockTest")

# Create mock state
def create_mock_state():
    """Create a mock KFM agent state for testing."""
    return {
        'kfm_action': {
            'action': 'keep',
            'component': 'data_processor',
            'reason': 'Performance metrics within acceptable thresholds'
        },
        'active_component': 'data_processor',
        'result': {
            'processed_items': 145,
            'errors': 3,
            'status': 'completed'
        },
        'execution_performance': {
            'latency': 1.2,
            'accuracy': 0.92,
            'memory_usage_mb': 245.6
        },
        'task_name': 'data_processing_task',
        'done': True
    }

def test_successful_call():
    """Test a successful call to the reflection function."""
    logger.info("=== Testing successful call case ===")
    mock_state = create_mock_state()
    
    logger.info("Calling mock_call_llm_for_reflection...")
    result = mock_call_llm_for_reflection(mock_state)
    
    if result and isinstance(result, str):
        if "ERROR" not in result:
            logger.info("✅ Success: Received a valid reflection")
            logger.info(f"First 50 chars: {result[:50]}...")
            return True
        else:
            logger.error(f"❌ Error: {result}")
            return False
    else:
        logger.error(f"❌ Error: Unexpected result type: {type(result)}")
        return False

def test_error_cases():
    """Test various error cases to ensure they're handled properly."""
    logger.info("\n=== Testing error cases ===")
    mock_state = create_mock_state()
    
    error_types = [
        "connection", 
        "value", 
        "timeout", 
        "configuration", 
        "general"
    ]
    
    success = True
    
    for error_type in error_types:
        logger.info(f"\nTesting error type: {error_type}")
        result = mock_error_case(mock_state, error_type=error_type)
        
        if result and isinstance(result, str):
            if "[LLM REFLECTION ERROR]" in result:
                logger.info(f"✅ Success: Error case handled correctly for {error_type}")
                logger.info(f"First 50 chars: {result[:50]}...")
            else:
                logger.error(f"❌ Error: Expected error message not found for {error_type}")
                logger.error(f"Result: {result}")
                success = False
        else:
            logger.error(f"❌ Error: Unexpected result type: {type(result)}")
            success = False
    
    return success

def main():
    """Run all the tests."""
    success_test = test_successful_call()
    error_tests = test_error_cases()
    
    logger.info("\n=== Test Summary ===")
    logger.info(f"Successful call test: {'PASSED' if success_test else 'FAILED'}")
    logger.info(f"Error cases tests: {'PASSED' if error_tests else 'FAILED'}")
    
    if success_test and error_tests:
        logger.info("\n✅ All tests passed! The implementation works correctly with appropriate mocking.")
        return 0
    else:
        logger.error("\n❌ Some tests failed. See above for details.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    exit(exit_code) 